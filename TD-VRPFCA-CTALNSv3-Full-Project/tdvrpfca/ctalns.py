"""Component-Tailored Adaptive Large Neighborhood Search for TD-VRPFCA.

The optimizer reuses the shared problem evaluator. Partial customer coverage is
allowed only during repair scoring; final candidates must satisfy full coverage.
This remains a research prototype until the evaluator is aligned with the paper.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import math
import random
import time

from .model import Instance, Solution, evaluate_solution
from .bwo import BWOOptimizer


@dataclass
class OperatorStats:
    uses: int = 0
    score: float = 0.0
    reward_sum: float = 0.0
    accepted: int = 0
    improving: int = 0


class CTALNSOptimizer:
    """Adaptive neighborhoods for route, crew, and departure-time decisions."""

    def __init__(
        self,
        instance: Instance,
        *,
        seed: int | None = None,
        return_leg_mode: str = "source",
        initial_time_mode: str = "per_vehicle",
        initial_population: int = 20,
        removal_fraction: float = 0.08,
        reaction: float = 0.2,
        cooling_rate: float = 0.995,
        initial_temperature_fraction: float = 0.08,
        insertion_positions_per_vehicle: int = 2,
    ):
        if not 0.02 <= removal_fraction <= 0.5:
            raise ValueError("removal_fraction must be between 0.02 and 0.5")
        if not 0 < reaction <= 1:
            raise ValueError("reaction must be in (0, 1]")
        if not 0 < cooling_rate <= 1:
            raise ValueError("cooling_rate must be in (0, 1]")
        if initial_population < 2:
            raise ValueError("initial_population must be >= 2")
        if insertion_positions_per_vehicle < 1:
            raise ValueError("insertion_positions_per_vehicle must be >= 1")

        self.inst = instance
        self.rng = random.Random(seed)
        self.seed = seed
        self.return_leg_mode = return_leg_mode
        self.removal_fraction = removal_fraction
        self.reaction = reaction
        self.cooling_rate = cooling_rate
        self.initial_temperature_fraction = initial_temperature_fraction
        self.insertion_positions_per_vehicle = insertion_positions_per_vehicle
        self.vehicle_ids = sorted(instance.vehicles)
        self.customer_set = set(instance.customers)
        self.operator_names = [
            "random_destroy_repair",
            "worst_destroy_repair",
            "related_destroy_repair",
            "critical_destroy_repair",
            "rush_hour_destroy_repair",
            "regret2_destroy_repair",
            "relocate",
            "swap",
            "crew_reassignment",
            "time_retiming",
            "joint_crew_time",
            "critical_crew_time",
        ]
        self.weights = {name: 1.0 for name in self.operator_names}
        self.stats = {name: OperatorStats() for name in self.operator_names}

        # Use a population of 20 by default to match the BWO experiment's
        # initial population size. The best feasible initializer is selected.
        builder = BWOOptimizer(
            instance,
            npop=initial_population,
            seed=seed,
            time_mode=initial_time_mode,
            return_leg_mode=return_leg_mode,
        )
        population = builder.initialize_population()  # sorted by fitness
        feasible = []
        for individual in population:
            solution = builder.decode_chromosome(individual.chromosome)
            value = self._value(solution)
            if math.isfinite(value):
                feasible.append((value, solution))
        if not feasible:
            raise RuntimeError("No feasible CT-ALNS initial solution was found")
        self.current_value, self.current = min(feasible, key=lambda x: x[0])
        self.best_value = self.current_value
        self.best = self._copy(self.current)

    def _evaluate(self, solution: Solution, *, partial: bool = False) -> dict:
        return evaluate_solution(
            self.inst,
            solution,
            return_leg_mode=self.return_leg_mode,
            check_customer_coverage=not partial,
        )

    def _value(self, solution: Solution, *, partial: bool = False) -> float:
        result = self._evaluate(solution, partial=partial)
        return float(result["T_MAX"]) if result["feasible"] else float("inf")

    @staticmethod
    def _copy(solution: Solution) -> Solution:
        return Solution(
            routes={k: list(v) for k, v in solution.routes.items()},
            crew=dict(solution.crew),
            start_intervals=dict(solution.start_intervals),
        )

    def _arc_distance(self, a: int, b: int) -> float:
        d = self.inst.distance.get((a, b))
        if d is None:
            d = self.inst.distance.get((b, a), float("inf"))
        return float(d)

    def _can_insert(self, sol: Solution, vehicle: int, customer: int) -> bool:
        load = sum(self.inst.demand.get(c, 0.0) for c in sol.routes[vehicle])
        return load + self.inst.demand.get(customer, 0.0) <= self.inst.vehicles[vehicle].capacity + 1e-9

    def _remove_customers(self, sol: Solution, count: int, mode: str) -> list[int]:
        served = [(k, c) for k in self.vehicle_ids for c in sol.routes[k]]
        if not served:
            return []
        count = min(max(1, count), len(served))
        if mode == "random":
            chosen = self.rng.sample(served, count)
        elif mode == "worst":
            def marginal(pair):
                k, c = pair
                route = sol.routes[k]
                idx = route.index(c)
                prev = self.inst.depot_start if idx == 0 else route[idx - 1]
                nxt = self.inst.depot_end if idx == len(route) - 1 else route[idx + 1]
                return self._arc_distance(prev, c) + self._arc_distance(c, nxt) - self._arc_distance(prev, nxt)
            chosen = sorted(served, key=marginal, reverse=True)[:count]
        else:
            # Related removal uses pairwise customer distance, not distance-from-depot.
            _, seed_customer = self.rng.choice(served)
            def related(pair):
                customer = pair[1]
                if customer == seed_customer:
                    return -1.0
                return min(self._arc_distance(seed_customer, customer), self._arc_distance(customer, seed_customer))
            chosen = sorted(served, key=related)[:count]

        removed = []
        for vehicle, customer in chosen:
            if customer in sol.routes[vehicle]:
                sol.routes[vehicle].remove(customer)
                removed.append(customer)
        return removed

    def _critical_vehicle(self, sol: Solution) -> int | None:
        """Return the vehicle currently determining makespan."""
        result = self._evaluate(sol)
        route_results = result.get("route_results", [])
        if not route_results:
            return None
        return max(route_results, key=lambda r: r["completion_time"])["vehicle"]

    def _remove_critical_customers(self, sol: Solution, count: int) -> list[int]:
        """Destroy customers on the bottleneck route first, then fill globally."""
        critical = self._critical_vehicle(sol)
        if critical is None or not sol.routes.get(critical):
            return self._remove_customers(sol, count, "worst")

        removed: list[int] = []
        route = sol.routes[critical]
        ranked = []
        for customer in route:
            idx = route.index(customer)
            prev = self.inst.depot_start if idx == 0 else route[idx - 1]
            nxt = self.inst.depot_end if idx == len(route) - 1 else route[idx + 1]
            marginal = (self._arc_distance(prev, customer)
                        + self._arc_distance(customer, nxt)
                        - self._arc_distance(prev, nxt))
            ranked.append((marginal, customer))
        ranked.sort(reverse=True)
        for _, customer in ranked[:count]:
            if customer in sol.routes[critical]:
                sol.routes[critical].remove(customer)
                removed.append(customer)

        remaining = count - len(removed)
        if remaining > 0:
            extra = self._remove_customers(sol, remaining, "worst")
            removed.extend(extra)
        return removed

    def _remove_rush_hour_customers(self, sol: Solution, count: int) -> list[int]:
        """Time-dependent destroy: prioritize removing customers encountered during low-speed congestion intervals."""
        critical = self._critical_vehicle(sol)
        congested_candidates = []

        for vehicle in self.vehicle_ids:
            route = sol.routes.get(vehicle, [])
            if not route:
                continue
            crew_id = sol.crew.get(vehicle, min(self.inst.crew))
            start_interval = sol.start_intervals.get(vehicle, min(self.inst.intervals))
            current = float(self.inst.lower[start_interval])
            full_route = [self.inst.depot_start] + route + [self.inst.depot_end]

            for a, b in zip(full_route, full_route[1:]):
                if a not in (self.inst.depot_start, self.inst.depot_end):
                    st = self.inst.service.get((a, crew_id, start_interval), 0.0)
                    current += st

                if self.return_leg_mode == "physical" and self.inst.depot_end == 101 and b == self.inst.depot_end:
                    dist = self.inst.distance.get((a, self.inst.depot_start), self.inst.distance.get((self.inst.depot_start, a), 0.0))
                    spd = self.inst.speed.get((a, self.inst.depot_start, start_interval), 1.0)
                else:
                    dist = self.inst.distance.get((a, b), 0.0)
                    spd = self.inst.speed.get((a, b, start_interval), 1.0)

                tt = (float(dist) / float(spd)) * self.inst.travel_time_factor if spd and spd > 0 else 0.0
                current += tt
                while start_interval < max(self.inst.intervals) and current > self.inst.upper[start_interval]:
                    start_interval += 1

                if b in self.customer_set:
                    is_crit = 1 if vehicle == critical else 0
                    congested_candidates.append((is_crit, -float(spd if spd is not None else 1.0), float(tt), vehicle, b))

        if not congested_candidates:
            return self._remove_customers(sol, count, "worst")

        # Sort: critical vehicle first, then lowest speed (highest congestion), then largest travel time
        congested_candidates.sort(reverse=True, key=lambda x: (x[0], x[1], x[2]))

        removed = []
        for _, _, _, vehicle, customer in congested_candidates[:count]:
            if customer in sol.routes[vehicle]:
                sol.routes[vehicle].remove(customer)
                removed.append(customer)

        remaining = count - len(removed)
        if remaining > 0:
            extra = self._remove_customers(sol, remaining, "worst")
            removed.extend(extra)
        return removed

    def _insertion_delta(self, route: list[int], customer: int) -> float:
        best = float("inf")
        full = [self.inst.depot_start] + route + [self.inst.depot_end]
        for i in range(len(full) - 1):
            prev, nxt = full[i], full[i + 1]
            delta = self._arc_distance(prev, customer) + self._arc_distance(customer, nxt) - self._arc_distance(prev, nxt)
            best = min(best, delta)
        return best

    def _greedy_reinsert(self, sol: Solution, customers: list[int]) -> Solution | None:
        """Reinsert all removed customers; partial coverage is allowed only here."""
        for customer in customers:
            candidates = []
            for vehicle in self.vehicle_ids:
                if not self._can_insert(sol, vehicle, customer):
                    continue
                route = sol.routes[vehicle]
                full = [self.inst.depot_start] + route + [self.inst.depot_end]
                positions = []
                for pos in range(len(route) + 1):
                    prev, nxt = full[pos], full[pos + 1]
                    delta = self._arc_distance(prev, customer) + self._arc_distance(customer, nxt) - self._arc_distance(prev, nxt)
                    positions.append((delta, pos))
                positions.sort(key=lambda item: item[0])
                # Limit expensive full evaluator calls while retaining multiple
                # promising insertion positions per vehicle.
                for _, pos in positions[:self.insertion_positions_per_vehicle]:
                    trial = self._copy(sol)
                    trial.routes[vehicle].insert(pos, customer)
                    value = self._value(trial, partial=True)
                    if math.isfinite(value):
                        candidates.append((value, trial))
            if not candidates:
                return None
            candidates.sort(key=lambda item: item[0])
            best_value = candidates[0][0]
            ties = [item for item in candidates if item[0] <= best_value + 1e-9]
            sol = self.rng.choice(ties)[1]

        # Final acceptance always uses the strict full evaluator.
        if not math.isfinite(self._value(sol)):
            return None
        return sol

    def _regret2_reinsert(self, sol: Solution, customers: list[int]) -> Solution | None:
        """Regret-2 insertion: prioritize customers whose second-best insertion
        is substantially worse than their best insertion. Candidate scoring uses
        the common evaluator with partial customer coverage disabled only during
        repair; final output is checked strictly.
        """
        pending = list(customers)
        while pending:
            choices = []
            for customer in pending:
                options = []
                for vehicle in self.vehicle_ids:
                    if not self._can_insert(sol, vehicle, customer):
                        continue
                    route = sol.routes[vehicle]
                    full = [self.inst.depot_start] + route + [self.inst.depot_end]
                    positions = []
                    for pos in range(len(route) + 1):
                        prev, nxt = full[pos], full[pos + 1]
                        delta = (self._arc_distance(prev, customer)
                                 + self._arc_distance(customer, nxt)
                                 - self._arc_distance(prev, nxt))
                        positions.append((delta, pos))
                    positions.sort(key=lambda x: x[0])
                    for delta, pos in positions[:self.insertion_positions_per_vehicle]:
                        trial = self._copy(sol)
                        trial.routes[vehicle].insert(pos, customer)
                        value = self._value(trial, partial=True)
                        if math.isfinite(value):
                            options.append((value, delta, vehicle, pos, trial))
                options.sort(key=lambda x: (x[0], x[1]))
                if not options:
                    continue
                best = options[0]
                # Use the objective gap where available; distance gap breaks ties
                # because makespan can be unchanged for many insertions.
                second = options[1] if len(options) > 1 else None
                objective_regret = (second[0] - best[0]) if second else 0.0
                distance_regret = (second[1] - best[1]) if second else 0.0
                regret = objective_regret + 1e-6 * max(0.0, distance_regret)
                choices.append((regret, -best[0], -best[1], customer, best[4]))
            if not choices:
                return None
            choices.sort(reverse=True, key=lambda x: (x[0], x[1], x[2]))
            _, _, _, customer, chosen_trial = choices[0]
            sol = chosen_trial
            pending.remove(customer)

        return sol if math.isfinite(self._value(sol)) else None

    def _critical_crew_time(self, sol: Solution) -> Solution:
        """Enumerate crew × start-interval assignments on the bottleneck route."""
        critical = self._critical_vehicle(sol)
        if critical is None or not sol.routes.get(critical):
            return self._joint_move(sol)
        best = self._copy(sol)
        best_value = self._value(best)
        old_crew = best.crew.get(critical)
        old_interval = best.start_intervals.get(critical)
        for crew_id in sorted(self.inst.crew):
            for interval in self.inst.intervals:
                if crew_id == old_crew and interval == old_interval:
                    continue
                trial = self._copy(sol)
                trial.crew[critical] = crew_id
                trial.start_intervals[critical] = interval
                value = self._value(trial)
                if math.isfinite(value) and value < best_value - 1e-9:
                    best, best_value = trial, value
        return best

    def _route_relocate(self, sol: Solution) -> Solution:
        candidate = self._copy(sol)
        served = [(k, c) for k in self.vehicle_ids for c in candidate.routes[k]]
        if not served:
            return candidate
        source, customer = self.rng.choice(served)
        candidate.routes[source].remove(customer)
        destinations = self.vehicle_ids[:]
        self.rng.shuffle(destinations)
        for dest in destinations:
            if not self._can_insert(candidate, dest, customer):
                continue
            positions = list(range(len(candidate.routes[dest]) + 1))
            self.rng.shuffle(positions)
            for pos in positions[:min(3, len(positions))]:
                trial = self._copy(candidate)
                trial.routes[dest].insert(pos, customer)
                if math.isfinite(self._value(trial)):
                    return trial
        return sol

    def _route_swap(self, sol: Solution) -> Solution:
        candidate = self._copy(sol)
        served = [(k, i) for k in self.vehicle_ids for i in range(len(candidate.routes[k]))]
        if len(served) < 2:
            return candidate
        for _ in range(12):
            (k1, i1), (k2, i2) = self.rng.sample(served, 2)
            if k1 == k2 and i1 == i2:
                continue
            trial = self._copy(candidate)
            trial.routes[k1][i1], trial.routes[k2][i2] = trial.routes[k2][i2], trial.routes[k1][i1]
            if math.isfinite(self._value(trial)):
                return trial
        return sol

    def _crew_move(self, sol: Solution) -> Solution:
        candidate = self._copy(sol)
        if not self.vehicle_ids:
            return candidate
        vehicle = self.rng.choice(self.vehicle_ids)
        old = candidate.crew.get(vehicle)
        options = [cid for cid in self.inst.crew if cid != old]
        self.rng.shuffle(options)
        if not options:
            return candidate
        # Return a genuine neighbor; simulated annealing decides acceptance.
        candidate.crew[vehicle] = options[0]
        return candidate

    def _time_move(self, sol: Solution) -> Solution:
        candidate = self._copy(sol)
        if not self.vehicle_ids:
            return candidate
        vehicle = self.rng.choice(self.vehicle_ids)
        old = candidate.start_intervals.get(vehicle)
        options = [interval for interval in self.inst.intervals if interval != old]
        if options:
            candidate.start_intervals[vehicle] = self.rng.choice(options)
        return candidate

    def _joint_move(self, sol: Solution) -> Solution:
        candidate = self._crew_move(sol)
        return self._time_move(candidate)

    def _apply_operator(self, name: str, current: Solution) -> Solution | None:
        candidate = self._copy(current)
        if name in {"random_destroy_repair", "worst_destroy_repair", "related_destroy_repair",
                    "critical_destroy_repair", "regret2_destroy_repair", "rush_hour_destroy_repair"}:
            count = max(1, int(len(self.inst.customers) * self.removal_fraction))
            if name == "critical_destroy_repair":
                removed = self._remove_critical_customers(candidate, count)
            elif name == "rush_hour_destroy_repair":
                removed = self._remove_rush_hour_customers(candidate, count)
            else:
                mode = {
                    "random_destroy_repair": "random",
                    "worst_destroy_repair": "worst",
                    "related_destroy_repair": "related",
                    "regret2_destroy_repair": "worst",
                }[name]
                removed = self._remove_customers(candidate, count, mode)
            self.rng.shuffle(removed)
            if not removed:
                return None
            if name in {"regret2_destroy_repair", "rush_hour_destroy_repair"}:
                return self._regret2_reinsert(candidate, removed)
            return self._greedy_reinsert(candidate, removed)
        if name == "relocate":
            return self._route_relocate(candidate)
        if name == "swap":
            return self._route_swap(candidate)
        if name == "crew_reassignment":
            return self._crew_move(candidate)
        if name == "time_retiming":
            return self._time_move(candidate)
        if name == "critical_crew_time":
            return self._critical_crew_time(candidate)
        return self._joint_move(candidate)

    def _choose_operator(self) -> str:
        total = sum(self.weights.values())
        point = self.rng.random() * total
        running = 0.0
        for name, weight in self.weights.items():
            running += weight
            if point <= running:
                return name
        return self.operator_names[-1]

    def run(self, iterations: int = 100) -> tuple[Solution, list[float], float, dict]:
        if iterations < 1:
            raise ValueError("iterations must be at least 1")
        started = time.perf_counter()
        history = [self.best_value]
        current_history = [self.current_value]
        temperature = max(1e-9, abs(self.current_value) * self.initial_temperature_fraction)
        reward_best, reward_improve, reward_accept = 5.0, 3.0, 1.0

        for _ in range(iterations):
            name = self._choose_operator()
            candidate = self._apply_operator(name, self.current)
            value = float("inf") if candidate is None else self._value(candidate)
            old_value = self.current_value
            reward = 0.0
            accepted = False

            if math.isfinite(value):
                delta = value - old_value
                if delta <= 0 or self.rng.random() < math.exp(-delta / max(temperature, 1e-12)):
                    self.current = self._copy(candidate)
                    self.current_value = value
                    accepted = True
                    reward = reward_improve if delta < -1e-9 else reward_accept
                if value < self.best_value - 1e-9:
                    self.best = self._copy(candidate)
                    self.best_value = value
                    reward = reward_best

            stat = self.stats[name]
            stat.uses += 1
            stat.reward_sum += reward
            stat.accepted += int(accepted)
            stat.improving += int(math.isfinite(value) and value < old_value - 1e-9)
            stat.score = (1 - self.reaction) * stat.score + self.reaction * reward
            self.weights[name] = max(
                0.05,
                (1 - self.reaction) * self.weights[name]
                + self.reaction * max(0.05, stat.score),
            )
            temperature *= self.cooling_rate
            history.append(self.best_value)
            current_history.append(self.current_value)

        elapsed = time.perf_counter() - started
        stats = {
            name: {
                "weight": self.weights[name],
                "uses": self.stats[name].uses,
                "accepted": self.stats[name].accepted,
                "improving": self.stats[name].improving,
                "reward_sum": self.stats[name].reward_sum,
                "average_reward": self.stats[name].reward_sum / max(1, self.stats[name].uses),
            }
            for name in self.operator_names
        }
        return self._copy(self.best), history, current_history, elapsed, stats
