"""Novelty 2: Multi-Objective Coordinated Time-Dependent ALNS (MO-CTALNS).

Extends the single-objective CT-ALNS to optimize both:
  f1(S) = T_MAX (Makespan / operational completion time)
  f2(S) = C_total (Total operational cost: vehicles + distance + crew + overtime)

Maintains an external Pareto Archive of non-dominated trade-off solutions,
uses multi-objective simulated annealing acceptance, and adapts operator weights
based on Pareto frontier improvements and hypervolume expansion.
"""
from __future__ import annotations

import copy
import math
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

from .model import Instance, Solution, evaluate_solution
from .ctalns import CTALNSOptimizer, OperatorStats
from .cost import CostConfig, CostBreakdown, evaluate_cost
from .pareto import ParetoPoint, ParetoArchive


class MOCTALNSOptimizer(CTALNSOptimizer):
    """Multi-Objective Adaptive Large Neighborhood Search for TD-VRPFCA."""

    def __init__(
        self,
        instance: Instance,
        *,
        cost_config: Optional[CostConfig] = None,
        archive_size: int = 50,
        seed: Optional[int] = None,
        return_leg_mode: str = "source",
        initial_time_mode: str = "per_vehicle",
        initial_population: int = 20,
        removal_fraction: float = 0.08,
        reaction: float = 0.2,
        cooling_rate: float = 0.995,
        initial_temperature: float = 100.0,
        insertion_positions_per_vehicle: int = 2,
    ):
        super().__init__(
            instance,
            seed=seed,
            return_leg_mode=return_leg_mode,
            initial_time_mode=initial_time_mode,
            initial_population=initial_population,
            removal_fraction=removal_fraction,
            reaction=reaction,
            cooling_rate=cooling_rate,
            insertion_positions_per_vehicle=insertion_positions_per_vehicle,
        )

        self.cost_config = cost_config or CostConfig()
        self.archive = ParetoArchive(max_size=archive_size)
        self.temperature = initial_temperature

        # Add cost-aware operators to the portfolio
        if "fleet_reduction_destroy_repair" not in self.operator_names:
            self.operator_names.append("fleet_reduction_destroy_repair")
        if "cost_conscious_crew_repair" not in self.operator_names:
            self.operator_names.append("cost_conscious_crew_repair")

        self.weights = {name: 1.0 for name in self.operator_names}
        self.stats = {name: OperatorStats() for name in self.operator_names}

        # Initialize the Pareto Archive with initial feasible solutions
        initial_eval = self._evaluate(self.current)
        initial_cost = evaluate_cost(
            self.inst,
            self.current,
            evaluation=initial_eval,
            cost_config=self.cost_config,
            return_leg_mode=self.return_leg_mode,
        )
        initial_point = ParetoPoint(
            solution=self._copy(self.current),
            t_max=initial_eval["T_MAX"],
            cost=initial_cost.total_cost,
            cost_breakdown=initial_cost,
            evaluation=initial_eval,
            iteration_found=0,
            operator_used="initial_bwo",
        )
        self.archive.add(initial_point)

    # -------------------------------------------------------------------------
    # Additional Novelty 2 Cost-Aware Operators
    # -------------------------------------------------------------------------

    def _operator_fleet_reduction_destroy_repair(self, sol: Solution) -> Solution:
        """Cost-reduction operator: empties the least-utilized vehicle to save fixed vehicle charge."""
        cand = self._copy(sol)
        active = [(k, len(cand.routes[k])) for k in self.vehicle_ids if cand.routes[k]]
        if len(active) <= 1:
            return cand

        # Select the vehicle with the smallest number of customers
        active.sort(key=lambda x: x[1])
        target_k, _ = active[0]
        unassigned = list(cand.routes[target_k])
        cand.routes[target_k] = []

        # Try to reinsert unassigned customers into other active vehicles
        other_vehicles = [k for k in self.vehicle_ids if k != target_k and cand.routes[k]]
        if not other_vehicles:
            return cand

        for cust in unassigned:
            best_v = None
            best_pos = None
            best_cost_delta = float("inf")

            for k in other_vehicles:
                if not self._can_insert(cand, k, cust):
                    continue
                route = cand.routes[k]
                for pos in range(len(route) + 1):
                    prev = self.inst.depot_start if pos == 0 else route[pos - 1]
                    nxt = self.inst.depot_end if pos == len(route) else route[pos]
                    dist_delta = (
                        self._arc_distance(prev, cust)
                        + self._arc_distance(cust, nxt)
                        - self._arc_distance(prev, nxt)
                    )
                    if dist_delta < best_cost_delta:
                        best_cost_delta = dist_delta
                        best_v = k
                        best_pos = pos

            if best_v is not None and best_pos is not None:
                cand.routes[best_v].insert(best_pos, cust)
            else:
                # Fallback: reinsert into original vehicle if capacity is exceeded elsewhere
                cand.routes[target_k].append(cust)

        return cand

    def _operator_cost_conscious_crew_repair(self, sol: Solution) -> Solution:
        """Crew cost-reduction operator: downscales expensive crews on light/short routes."""
        cand = self._copy(sol)
        active = [k for k in self.vehicle_ids if cand.routes[k]]
        if not active:
            return cand

        target_k = self.rng.choice(active)
        current_crew = cand.crew.get(target_k, 1)

        # Find eligible crews with lower hourly cost
        def crew_hourly_rate(c_id: int) -> float:
            return sum(
                self.cost_config.worker_hourly_wages.get(wt, 15.0) * cnt
                for wt, cnt in self.inst.crew.get(c_id, {}).items()
            )

        current_rate = crew_hourly_rate(current_crew)
        cheaper_crews = [
            c_id for c_id in self.inst.crew
            if crew_hourly_rate(c_id) <= current_rate
        ]

        if cheaper_crews:
            cand.crew[target_k] = self.rng.choice(cheaper_crews)

        return cand

    # -------------------------------------------------------------------------
    # Multi-Objective Optimization Loop
    # -------------------------------------------------------------------------

    def run_multiobjective(
        self,
        iterations: int,
        ref_point: Optional[Tuple[float, float]] = None,
        segment_length: int = 10,
    ) -> Tuple[ParetoArchive, List[Dict[str, Any]], float, Dict[str, OperatorStats]]:
        """Execute the MO-CTALNS optimization search.

        Parameters
        ----------
        iterations : int
            Total search iterations.
        ref_point : (T_ref, C_ref), optional
            Reference point for hypervolume calculation.
        segment_length : int
            Frequency of roulette-wheel weight updates.

        Returns
        -------
        ParetoArchive
            The final non-dominated Pareto front.
        List[dict]
            Per-iteration convergence history.
        float
            Wall-clock runtime in seconds.
        dict
            Operator performance diagnostics.
        """
        t0 = time.perf_counter()
        history: List[Dict[str, Any]] = []

        temp = self.temperature
        min_temp = 0.1

        for it in range(1, iterations + 1):
            # 1. Select a base solution from the Pareto Archive
            # We bias selection towards diverse/sparse points (crowding distance)
            self.archive.update_crowding_distances()
            archive_pts = self.archive.points
            if not archive_pts:
                parent_sol = self.current
            else:
                # Tournament selection among 2 candidates favoring higher crowding distance
                c1 = self.rng.choice(archive_pts)
                c2 = self.rng.choice(archive_pts)
                chosen = c1 if c1.crowding_distance >= c2.crowding_distance else c2
                parent_sol = chosen.solution

            # 2. Select operator via roulette wheel
            total_w = sum(self.weights.values())
            r_pick = self.rng.uniform(0, total_w)
            acc = 0.0
            chosen_op = self.operator_names[0]
            for op_name, w in self.weights.items():
                acc += w
                if acc >= r_pick:
                    chosen_op = op_name
                    break

            stat = self.stats[chosen_op]
            stat.uses += 1

            # 3. Apply the operator
            if chosen_op == "fleet_reduction_destroy_repair":
                cand_sol = self._operator_fleet_reduction_destroy_repair(parent_sol)
            elif chosen_op == "cost_conscious_crew_repair":
                cand_sol = self._operator_cost_conscious_crew_repair(parent_sol)
            else:
                applied = self._apply_operator(chosen_op, parent_sol)
                cand_sol = applied if applied is not None else parent_sol


            # 4. Evaluate feasibility, T_MAX, and C_total
            cand_eval = self._evaluate(cand_sol)
            accepted = False
            entered_archive = False
            reward = 0.0

            if cand_eval["feasible"]:
                cand_cost = evaluate_cost(
                    self.inst,
                    cand_sol,
                    evaluation=cand_eval,
                    cost_config=self.cost_config,
                    return_leg_mode=self.return_leg_mode,
                )
                cand_point = ParetoPoint(
                    solution=self._copy(cand_sol),
                    t_max=cand_eval["T_MAX"],
                    cost=cand_cost.total_cost,
                    cost_breakdown=cand_cost,
                    evaluation=cand_eval,
                    iteration_found=it,
                    operator_used=chosen_op,
                )

                # Count archive size before attempt
                pre_size = len(self.archive)
                # Check if candidate enters the Pareto archive
                entered = self.archive.add(cand_point)

                if entered:
                    entered_archive = True
                    accepted = True
                    post_size = len(self.archive)
                    if post_size < pre_size + 1:
                        # Pruned existing dominated points (Major Dominant Advance)
                        reward = 30.0
                        stat.improving += 1
                    else:
                        # Added new diverse non-dominated point
                        reward = 20.0
                        stat.improving += 1
                    stat.accepted += 1
                else:
                    # Candidate is dominated by the archive.
                    # Multi-objective simulated annealing acceptance:
                    # Calculate Chebyshev distance to the closest archive member
                    min_delta = float("inf")
                    for pt in self.archive.points:
                        norm_t = (cand_point.t_max - pt.t_max) / max(1.0, pt.t_max)
                        norm_c = (cand_point.cost - pt.cost) / max(1.0, pt.cost)
                        delta = max(norm_t, norm_c)
                        if delta < min_delta:
                            min_delta = delta

                    if min_delta <= 0:
                        p_accept = 1.0
                    else:
                        p_accept = math.exp(-min_delta * 100.0 / max(temp, min_temp))

                    if self.rng.random() < p_accept:
                        accepted = True
                        reward = 5.0
                        stat.accepted += 1
                    else:
                        reward = 0.0
            else:
                reward = 0.0

            # 5. Accumulate score and update temperature
            stat.reward_sum += reward
            stat.score += reward
            temp = max(min_temp, temp * self.cooling_rate)

            # 6. Periodic adaptive weight update
            if it % segment_length == 0:
                for name, s in self.stats.items():
                    if s.uses > 0:
                        avg_reward = s.reward_sum / s.uses
                        self.weights[name] = (
                            (1.0 - self.reaction) * self.weights[name]
                            + self.reaction * avg_reward
                        )
                        # Keep a positive floor to preserve operator diversity
                        self.weights[name] = max(0.1, self.weights[name])
                        s.reward_sum = 0.0

            # 7. Record iteration history
            sorted_front = self.archive.get_sorted_front()
            best_t = sorted_front[0].t_max if sorted_front else float("inf")
            best_c = min((p.cost for p in sorted_front), default=float("inf"))
            hv = self.archive.calculate_hypervolume(ref_point=ref_point)

            history.append({
                "iteration": it,
                "temperature": temp,
                "archive_size": len(self.archive),
                "best_T_MAX": best_t,
                "best_C_total": best_c,
                "hypervolume": hv,
                "operator": chosen_op,
                "accepted": accepted,
                "entered_archive": entered_archive,
                "reward": reward,
            })

        elapsed = time.perf_counter() - t0
        self.archive.update_crowding_distances()
        return self.archive, history, elapsed, self.stats
