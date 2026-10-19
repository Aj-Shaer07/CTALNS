"""Multi-Objective Black Widow Optimization (MO-BWO) for TD-VRPFCA.

Baseline multi-objective metaheuristic extending BWO with Pareto dominance,
fast non-dominated sorting, crowding-distance diversity preservation,
and an external Pareto Archive to optimize (T_MAX, C_total).
"""
from __future__ import annotations

import copy
import math
import random
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any

from .model import Instance, Solution, evaluate_solution
from .cost import CostConfig, CostBreakdown, evaluate_cost
from .pareto import ParetoPoint, ParetoArchive
from .bwo import BWOOptimizer, BWOSolution


@dataclass
class MOBWOSolution:
    chromosome: List[int]
    t_max: float
    cost: float
    cost_breakdown: Optional[CostBreakdown] = None
    feasible: bool = True
    rank: int = 0
    crowding_distance: float = 0.0

    def dominates(self, other: MOBWOSolution, eps: float = 1e-6) -> bool:
        if not self.feasible:
            return False
        if not other.feasible:
            return True
        no_worse = (self.t_max <= other.t_max + eps) and (self.cost <= other.cost + eps)
        strictly_better = (self.t_max < other.t_max - eps) or (self.cost < other.cost - eps)
        return no_worse and strictly_better


def fast_non_dominated_sort(population: List[MOBWOSolution]) -> List[List[MOBWOSolution]]:
    """Standard Deb et al. fast non-dominated sorting algorithm."""
    fronts: List[List[MOBWOSolution]] = [[]]
    domination_counts = {id(ind): 0 for ind in population}
    dominated_sets = {id(ind): [] for ind in population}

    for p in population:
        p_id = id(p)
        for q in population:
            q_id = id(q)
            if p.dominates(q):
                dominated_sets[p_id].append(q)
            elif q.dominates(p):
                domination_counts[p_id] += 1
        if domination_counts[p_id] == 0:
            p.rank = 1
            fronts[0].append(p)

    i = 0
    while i < len(fronts) and len(fronts[i]) > 0:
        next_front = []
        for p in fronts[i]:
            for q in dominated_sets[id(p)]:
                q_id = id(q)
                domination_counts[q_id] -= 1
                if domination_counts[q_id] == 0:
                    q.rank = i + 2
                    next_front.append(q)
        i += 1
        if next_front:
            fronts.append(next_front)
        else:
            break

    return [f for f in fronts if f]


def assign_crowding_distances(front: List[MOBWOSolution]) -> None:
    """Calculate NSGA-II crowding distances within a single Pareto front."""
    n = len(front)
    if n <= 2:
        for ind in front:
            ind.crowding_distance = float("inf")
        return

    for ind in front:
        ind.crowding_distance = 0.0

    # Objective 1: T_MAX
    front.sort(key=lambda x: x.t_max)
    front[0].crowding_distance = float("inf")
    front[-1].crowding_distance = float("inf")
    t_span = front[-1].t_max - front[0].t_max
    if t_span > 1e-6:
        for i in range(1, n - 1):
            front[i].crowding_distance += (front[i + 1].t_max - front[i - 1].t_max) / t_span

    # Objective 2: C_total
    front.sort(key=lambda x: x.cost)
    front[0].crowding_distance = float("inf")
    front[-1].crowding_distance = float("inf")
    c_span = front[-1].cost - front[0].cost
    if c_span > 1e-6:
        for i in range(1, n - 1):
            front[i].crowding_distance += (front[i + 1].cost - front[i - 1].cost) / c_span


class MOBWOOptimizer(BWOOptimizer):
    """Multi-Objective Black Widow Optimization baseline."""

    def __init__(
        self,
        instance: Instance,
        *,
        cost_config: Optional[CostConfig] = None,
        archive_size: int = 50,
        npop: int = 20,
        procreation_rate: float = 0.40,
        cannibalism_rate: float = 0.50,
        mutation_rate: float = 0.05,
        seed: Optional[int] = None,
        time_mode: str = "per_vehicle",
        return_leg_mode: str = "source",
    ):
        super().__init__(
            instance,
            npop=npop,
            procreation_rate=procreation_rate,
            cannibalism_rate=cannibalism_rate,
            mutation_rate=mutation_rate,
            seed=seed,
            time_mode=time_mode,
            return_leg_mode=return_leg_mode,
        )
        self.cost_config = cost_config or CostConfig()
        self.archive = ParetoArchive(max_size=archive_size)

    def evaluate_multiobjective(self, chromosome: List[int]) -> MOBWOSolution:
        """Evaluate both T_MAX and C_total for a chromosome."""
        try:
            sol = self.decode_chromosome(chromosome)
            ev = evaluate_solution(self.inst, sol, return_leg_mode=self.return_leg_mode)
            if not ev["feasible"]:
                return MOBWOSolution(chromosome, float("inf"), float("inf"), feasible=False)
            cb = evaluate_cost(
                self.inst, sol, evaluation=ev, cost_config=self.cost_config, return_leg_mode=self.return_leg_mode
            )
            return MOBWOSolution(
                chromosome=chromosome,
                t_max=ev["T_MAX"],
                cost=cb.total_cost,
                cost_breakdown=cb,
                feasible=True,
            )
        except Exception:
            return MOBWOSolution(chromosome, float("inf"), float("inf"), feasible=False)

    def _archive_candidate(self, ind: MOBWOSolution, iteration: int = 0) -> None:
        """Helper to add feasible solutions to the external Pareto archive."""
        if not ind.feasible:
            return
        sol = self.decode_chromosome(ind.chromosome)
        pt = ParetoPoint(
            solution=sol,
            t_max=ind.t_max,
            cost=ind.cost,
            cost_breakdown=ind.cost_breakdown,
            iteration_found=iteration,
            operator_used="mobwo_search",
        )
        self.archive.add(pt)

    def initialize_population_mo(self) -> List[MOBWOSolution]:
        """Generate and evaluate initial population for multi-objective search."""
        pop_single = super().initialize_population()
        mo_pop = []
        for ind in pop_single:
            mo_ind = self.evaluate_multiobjective(ind.chromosome)
            if mo_ind.feasible:
                mo_pop.append(mo_ind)
                self._archive_candidate(mo_ind, iteration=0)

        # Pad with random valid chromosomes if needed
        while len(mo_pop) < self.npop:
            chrom = self.create_random_route() + self.create_random_crew() + self._random_time_genes()
            mo_ind = self.evaluate_multiobjective(chrom)
            mo_pop.append(mo_ind)
            if mo_ind.feasible:
                self._archive_candidate(mo_ind, iteration=0)
        return mo_pop[:self.npop]

    def procreate_and_cannibalize_mo(
        self, population: List[MOBWOSolution], iteration: int
    ) -> List[MOBWOSolution]:
        """Multi-objective procreation and Pareto cannibalism."""
        survivors = list(population)
        for _ in range(self.nr // 2):
            if len(survivors) < 2:
                break
            p1_idx = self.rng.randint(0, len(survivors) - 1)
            p2_idx = self.rng.randint(0, len(survivors) - 1)
            while p1_idx == p2_idx:
                p2_idx = self.rng.randint(0, len(survivors) - 1)
            p1 = survivors[p1_idx]
            p2 = survivors[p2_idx]

            c1_chrom, c2_chrom = self.breed(p1.chromosome, p2.chromosome)
            child1 = self.evaluate_multiobjective(c1_chrom)
            child2 = self.evaluate_multiobjective(c2_chrom)

            self._archive_candidate(child1, iteration)
            self._archive_candidate(child2, iteration)

            children = [child1, child2]

            # 1. Sexual cannibalism (Pareto dominance)
            if p1.dominates(p2):
                if p2 in survivors:
                    survivors.remove(p2)
            elif p2.dominates(p1):
                if p1 in survivors:
                    survivors.remove(p1)

            # 2. Sibling cannibalism (non-dominated sorting)
            children_fronts = fast_non_dominated_sort([c for c in children if c.feasible])
            keep_children = children_fronts[0] if children_fronts else []

            # 3. Parental cannibalism
            for c in keep_children:
                if p1.feasible and c.dominates(p1) and p1 in survivors:
                    survivors.remove(p1)
                if p2.feasible and c.dominates(p2) and p2 in survivors:
                    survivors.remove(p2)

            survivors.extend(keep_children)

        return [s for s in survivors if s.feasible] or population[:1]

    def mutate_mo(self, population: List[MOBWOSolution], iteration: int) -> List[MOBWOSolution]:
        """Multi-objective mutation: random route swap with chromosome repair."""
        mutants = []
        for _ in range(self.nm):
            if not population:
                break
            parent = self.rng.choice(population).chromosome
            route = list(parent[:self.route_length])
            tail = list(parent[self.route_length:])
            if len(route) > 2:
                i = self.rng.randint(1, len(route) - 1)
                j = self.rng.randint(1, len(route) - 1)
                route[i], route[j] = route[j], route[i]
            route = self._normalize_route(route)
            if not self.is_route_feasible(route):
                route = self.create_random_route()
            chrom = route + tail
            mutant = self.evaluate_multiobjective(chrom)
            if mutant.feasible:
                self._archive_candidate(mutant, iteration)
                mutants.append(mutant)
        return mutants

    def select_next_generation(self, pool: List[MOBWOSolution]) -> List[MOBWOSolution]:
        """Environmental selection using fast non-dominated sorting and crowding distance."""
        feasible_pool = [ind for ind in pool if ind.feasible]
        if len(feasible_pool) <= self.npop:
            return feasible_pool

        fronts = fast_non_dominated_sort(feasible_pool)
        next_pop = []

        for front in fronts:
            assign_crowding_distances(front)
            if len(next_pop) + len(front) <= self.npop:
                next_pop.extend(front)
            else:
                needed = self.npop - len(next_pop)
                # Sort by crowding distance descending (favor boundary/diverse solutions)
                front.sort(key=lambda ind: ind.crowding_distance, reverse=True)
                next_pop.extend(front[:needed])
                break

        return next_pop

    def run_multiobjective(
        self, max_iter: int = 100
    ) -> Tuple[ParetoArchive, List[Dict[str, Any]], float]:
        """Execute MO-BWO search and return the final Pareto archive."""
        t0 = time.perf_counter()
        population = self.initialize_population_mo()
        history = []

        for it in range(1, max_iter + 1):
            children = self.procreate_and_cannibalize_mo(population, it)
            mutants = self.mutate_mo(population, it)
            pool = population + children + mutants
            population = self.select_next_generation(pool)

            hv = self.archive.calculate_hypervolume()
            sorted_pts = self.archive.get_sorted_front()
            best_t = sorted_pts[0].t_max if sorted_pts else float("inf")
            best_c = min((p.cost for p in sorted_pts), default=float("inf"))

            history.append({
                "iteration": it,
                "archive_size": len(self.archive),
                "best_T_MAX": best_t,
                "best_C_total": best_c,
                "hypervolume": hv,
            })

        runtime = time.perf_counter() - t0
        self.archive.update_crowding_distances()
        return self.archive, history, runtime
