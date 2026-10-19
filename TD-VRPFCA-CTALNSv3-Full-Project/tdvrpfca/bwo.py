"""Black Widow Optimization baseline, reconstructed from the friend's implementation.

The chromosome/operator mechanics follow the friend's code:
  route chromosome | crew-combination counts | start interval gene(s)
  route crossover, parent/offspring cannibalism, and route-swap mutation.

Obvious software hazards are repaired (append(None), undefined population state,
bounded feasibility retries, and final-generation best tracking). Any resulting
difference from historical results should be documented rather than hidden.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import random
import time
from typing import Dict, List, Tuple

from .model import Instance, Solution, evaluate_solution


@dataclass(eq=False)
class BWOSolution:
    chromosome: List[int]
    fitness: float = float("inf")


class BWOOptimizer:
    def __init__(
        self,
        instance: Instance,
        npop: int = 20,
        procreation_rate: float = 0.40,
        cannibalism_rate: float = 0.50,
        mutation_rate: float = 0.05,
        seed: int | None = None,
        time_mode: str = "shared",
        return_leg_mode: str = "source",
        max_generation_attempts: int = 2000,
    ):
        if npop < 2:
            raise ValueError("npop must be at least 2")
        if time_mode not in {"shared", "per_vehicle"}:
            raise ValueError("time_mode must be 'shared' or 'per_vehicle'")
        self.inst = instance
        self.npop = int(npop)
        self.procreation_rate = float(procreation_rate)
        self.cannibalism_rate = float(cannibalism_rate)
        self.mutation_rate = float(mutation_rate)
        self.seed = seed
        self.rng = random.Random(seed)
        self.time_mode = time_mode
        self.return_leg_mode = return_leg_mode
        self.max_generation_attempts = max_generation_attempts

        self.n = len(instance.customers)
        self.vehicle_ids = sorted(instance.vehicles)
        self.crew_ids = sorted(instance.crew)
        self.k = len(self.vehicle_ids)
        self.d = len(self.crew_ids)
        self.route_length = self.n + self.k + 1
        self.time_gene_count = 1 if time_mode == "shared" else self.k
        self.chromosome_length = self.route_length + self.d + self.time_gene_count
        self.nr = max(1, int(self.npop * self.procreation_rate))
        self.nm = max(1, int(self.npop * self.mutation_rate))

    # ---------- Common representation ----------
    def decode_chromosome(self, chromosome: List[int]) -> Solution:
        if len(chromosome) != self.chromosome_length:
            raise ValueError(
                f"Expected chromosome length {self.chromosome_length}, got {len(chromosome)}"
            )
        route_segment = chromosome[:self.route_length]
        crew_segment = chromosome[self.route_length:self.route_length + self.d]
        time_segment = chromosome[self.route_length + self.d:]

        routes = {k: [] for k in self.vehicle_ids}
        vehicle_pos = 0
        for node in route_segment[1:]:
            if node == 0:
                vehicle_pos += 1
                if vehicle_pos >= self.k:
                    break
            elif vehicle_pos < self.k:
                routes[self.vehicle_ids[vehicle_pos]].append(node)

        crew_assignment: Dict[int, int] = {}
        pos = 0
        for idx, crew_id in enumerate(self.crew_ids):
            count = max(0, int(crew_segment[idx]))
            for _ in range(count):
                if pos < self.k:
                    crew_assignment[self.vehicle_ids[pos]] = crew_id
                    pos += 1
        # Invalid count vectors remain invalid rather than silently inventing a
        # crew; the evaluator will mark the candidate infeasible.
        if pos != self.k:
            for vehicle_id in self.vehicle_ids[pos:]:
                crew_assignment[vehicle_id] = -1

        if self.time_mode == "shared":
            starts = {k: int(time_segment[0]) for k in self.vehicle_ids}
        else:
            starts = {k: int(time_segment[i]) for i, k in enumerate(self.vehicle_ids)}

        return Solution(routes=routes, crew=crew_assignment, start_intervals=starts)

    def evaluate(self, chromosome: List[int]) -> float:
        try:
            solution = self.decode_chromosome(chromosome)
            result = evaluate_solution(
                self.inst, solution, return_leg_mode=self.return_leg_mode
            )
            return float(result["T_MAX"]) if result["feasible"] else float("inf")
        except (ValueError, KeyError, IndexError, TypeError):
            return float("inf")

    def _crew_assignment_from_counts(self, counts: List[int]) -> Dict[int, int] | None:
        assigned = []
        for crew_id, count in zip(self.crew_ids, counts):
            assigned.extend([crew_id] * int(count))
        if len(assigned) != self.k:
            return None
        result = dict(zip(self.vehicle_ids, assigned))
        used = {wt: 0.0 for wt in self.inst.worker_availability}
        for vehicle_id, crew_id in result.items():
            if crew_id not in self.inst.crew:
                return None
            crew = self.inst.crew[crew_id]
            if sum(crew.values()) > self.inst.vehicles[vehicle_id].max_crew + 1e-9:
                return None
            for wt, count in crew.items():
                used[wt] = used.get(wt, 0.0) + count
        for wt, total in used.items():
            if wt in self.inst.worker_availability and total > self.inst.worker_availability[wt] + 1e-9:
                return None
        return result

    # ---------- Feasible initialization and repair ----------
    def is_route_feasible(self, route_segment: List[int]) -> bool:
        if len(route_segment) != self.route_length or not route_segment or route_segment[0] != 0:
            return False
        if route_segment.count(0) != self.k + 1:
            return False
        customers = [x for x in route_segment if x != 0]
        if len(customers) != self.n or set(customers) != set(self.inst.customers):
            return False
        vehicle_pos = 0
        load = 0.0
        for node in route_segment[1:]:
            if node == 0:
                if vehicle_pos < self.k:
                    if load > self.inst.vehicles[self.vehicle_ids[vehicle_pos]].capacity + 1e-9:
                        return False
                vehicle_pos += 1
                load = 0.0
            else:
                load += self.inst.demand.get(node, 0.0)
        return True

    def _normalize_route(self, raw: List[int]) -> List[int]:
        """Use the friend's simple depot-separator repair, with safety guards.

        The original implementation removes excess zero separators or appends
        missing ones. We retain that behavior, then fall back to a valid route
        if the chromosome still loses/duplicates a customer.
        """
        route = list(raw)
        if not route or route[0] != 0:
            route = [0] + route

        while len(route) > self.route_length:
            zero_index = next((i for i in range(1, len(route)) if route[i] == 0), None)
            if zero_index is not None:
                del route[zero_index]
            else:
                route.pop()

        while len(route) < self.route_length:
            route.append(0)

        if route[-1] != 0:
            # Move the last separator to the end; do not overwrite a customer.
            separator = next((i for i in range(len(route) - 2, 0, -1) if route[i] == 0), None)
            if separator is not None:
                route[separator], route[-1] = route[-1], route[separator]

        expected = set(self.inst.customers)
        actual = [x for x in route if x != 0]
        if len(actual) != self.n or set(actual) != expected or route.count(0) != self.k + 1:
            # A robust fallback is preferable to silently evaluating a malformed
            # chromosome. The original operators usually reach this only if the
            # source encoding was already malformed.
            return self.create_random_route()
        return route

    def create_random_route(self) -> List[int]:
        for _ in range(self.max_generation_attempts):
            customers = list(self.inst.customers)
            self.rng.shuffle(customers)
            inner = list(customers) + [0] * max(0, self.k - 1)
            self.rng.shuffle(inner)
            route = [0] + inner + [0]
            if self.is_route_feasible(route):
                return route

        # Guaranteed-termination fallback: randomized greedy capacity packing.
        for _ in range(100):
            order = list(self.inst.customers)
            self.rng.shuffle(order)
            bins = [[] for _ in self.vehicle_ids]
            loads = [0.0] * self.k
            feasible = True
            for customer in order:
                options = [
                    i for i, vehicle_id in enumerate(self.vehicle_ids)
                    if loads[i] + self.inst.demand[customer] <= self.inst.vehicles[vehicle_id].capacity + 1e-9
                ]
                if not options:
                    feasible = False
                    break
                chosen = self.rng.choice(options)
                bins[chosen].append(customer)
                loads[chosen] += self.inst.demand[customer]
            if feasible:
                route = [0]
                for route_customers in bins:
                    route.extend(route_customers)
                    route.append(0)
                if self.is_route_feasible(route):
                    return route
        raise RuntimeError("Could not construct a capacity-feasible route; check data and vehicle capacities")

    def create_random_crew(self) -> List[int]:
        for _ in range(self.max_generation_attempts):
            assignment = [self.rng.choice(self.crew_ids) for _ in self.vehicle_ids]
            counts = [assignment.count(c) for c in self.crew_ids]
            if self._crew_assignment_from_counts(counts) is not None:
                return counts

        # Deterministic search fallback: try crew IDs in a shuffled cyclic order.
        crew_order = list(self.crew_ids)
        self.rng.shuffle(crew_order)
        assignment = []
        used = {wt: 0.0 for wt in self.inst.worker_availability}
        for vehicle_id in self.vehicle_ids:
            options = []
            for crew_id in crew_order:
                crew = self.inst.crew[crew_id]
                if sum(crew.values()) > self.inst.vehicles[vehicle_id].max_crew + 1e-9:
                    continue
                if all(
                    used.get(wt, 0.0) + count <= self.inst.worker_availability.get(wt, float("inf")) + 1e-9
                    for wt, count in crew.items()
                ):
                    options.append(crew_id)
            if not options:
                raise RuntimeError("No feasible crew assignment found; check worker availability assumptions")
            chosen = options[0]
            assignment.append(chosen)
            for wt, count in self.inst.crew[chosen].items():
                used[wt] = used.get(wt, 0.0) + count
        return [assignment.count(c) for c in self.crew_ids]

    def _random_time_genes(self) -> List[int]:
        if self.time_mode == "shared":
            return [self.rng.choice(self.inst.intervals)]
        return [self.rng.choice(self.inst.intervals) for _ in self.vehicle_ids]

    def initialize_population(self) -> List[BWOSolution]:
        population = []
        for _ in range(self.npop):
            chromosome = self.create_random_route() + self.create_random_crew() + self._random_time_genes()
            sol = BWOSolution(chromosome)
            sol.fitness = self.evaluate(chromosome)
            population.append(sol)
        population.sort(key=lambda s: s.fitness)
        if not population or all(s.fitness == float("inf") for s in population):
            raise RuntimeError("BWO initialization produced no feasible solutions; inspect data assumptions")
        return population

    # ---------- Original BWO search operators ----------
    def breed(self, parent1: List[int], parent2: List[int]) -> Tuple[List[int], List[int]]:
        route1 = parent1[:self.route_length]
        route2 = parent2[:self.route_length]
        tail1 = parent1[self.route_length:]
        tail2 = parent2[self.route_length:]

        a = int(self.rng.random() * self.route_length)
        b = int(self.rng.random() * self.route_length)
        start, end = min(a, b), max(a, b)
        child_p1 = route1[start:end]
        child_p2 = [x for x in route2 if x == 0 or x not in child_p1]
        raw_child = child_p1 + child_p2
        child_route = self._normalize_route(raw_child)
        if not self.is_route_feasible(child_route):
            child_route = self.create_random_route()

        # The original/friend implementation shares the repaired route between
        # siblings while inheriting crew/time genes from their respective parent.
        return child_route + tail1, child_route + tail2

    def procreate_and_cannibalize(self, population: List[BWOSolution]) -> List[BWOSolution]:
        survivors = list(population)
        for _ in range(self.nr // 2):
            if len(survivors) < 2:
                break
            p1_idx = self.rng.randint(0, len(survivors) - 1)
            p2_idx = self.rng.randint(0, len(survivors) - 1)
            while p1_idx == p2_idx:
                p2_idx = self.rng.randint(0, len(survivors) - 1)
            mother, father = survivors[p1_idx], survivors[p2_idx]
            c1, c2 = self.breed(mother.chromosome, father.chromosome)
            children = [BWOSolution(c1, self.evaluate(c1)), BWOSolution(c2, self.evaluate(c2))]

            # Sexual cannibalism: the weaker parent is removed.
            if mother.fitness <= father.fitness:
                if father in survivors:
                    survivors.remove(father)
            else:
                if mother in survivors:
                    survivors.remove(mother)
                mother = father

            # Sibling cannibalism: retain the best fraction controlled by cr.
            children.sort(key=lambda s: s.fitness)
            keep = max(0, min(len(children), int(len(children) * self.cannibalism_rate)))
            children = children[:keep]

            # Parental cannibalism: the best child can replace the selected mother.
            if children and children[0].fitness < mother.fitness and mother in survivors:
                survivors.remove(mother)
            survivors.extend(children)

        if not survivors:
            survivors = list(population[:1])
        return survivors

    def mutate(self, population: List[BWOSolution]) -> List[BWOSolution]:
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
            chromosome = route + tail
            mutants.append(BWOSolution(chromosome, self.evaluate(chromosome)))
        return mutants

    def run(self, max_iter: int = 100):
        if max_iter < 1:
            raise ValueError("max_iter must be at least 1")
        start_time = time.perf_counter()
        population = self.initialize_population()
        best = copy.deepcopy(population[0])
        history = [best.fitness]

        for _ in range(max_iter):
            population = self.procreate_and_cannibalize(population)
            population.extend(self.mutate(population))
            population.sort(key=lambda s: s.fitness)
            population = population[:self.npop]
            if population and population[0].fitness < best.fitness:
                best = copy.deepcopy(population[0])
            history.append(best.fitness)

        runtime = time.perf_counter() - start_time
        return best, history, runtime
