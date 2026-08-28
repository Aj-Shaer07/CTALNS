from __future__ import annotations

from typing import Dict, List, Tuple

from .model import Evaluation, Instance, RouteEvaluation, Solution


class TDVRPFCAEvaluator:
    """Evaluate a TD-VRPFCA solution in hours.

    Repository t.txt service values are minute-valued; the evaluator converts
    them to hours by default. Travel distance/speed is already evaluated in
    hours (distance divided by speed).
    """

    def __init__(self, instance: Instance, *, service_scale: float = 1.0 / 60.0):
        self.instance = instance
        self.service_scale = service_scale

    def _speed_for_arc(self, i: int, j: int, interval: int) -> float:
        key = (i, j, interval)
        if key in self.instance.speed:
            return self.instance.speed[key]

        # The repository small-instance v.txt omits arcs involving the
        # depot/return node. For that instance, every available arc has the
        # same speed for a given time interval, so the missing depot-arc
        # speed is recoverable directly from the supplied interval data.
        candidates = {
            speed
            for (a, b, l), speed in self.instance.speed.items()
            if l == interval
        }
        if len(candidates) == 1:
            return next(iter(candidates))

        raise ValueError(f"missing speed for arc ({i},{j}), interval {interval}")

    def _travel_time(self, i: int, j: int, interval: int) -> float:
        speed = self._speed_for_arc(i, j, interval)
        if speed <= 0:
            raise ValueError(f"Non-positive speed on arc ({i},{j}) interval {interval}")
        return round(self.instance.distance[(i, j)] / speed, 3)

    def _update_interval(self, time: float, interval: int) -> int:
        """Advance to the interval containing the accumulated time.

        This follows the interval-update behavior in the authors' Fitness.py:
        after a movement/service+movement, advance while the accumulated time
        is beyond the current interval upper boundary.
        """
        while time > self.instance.upper[interval]:
            next_interval = interval + 1
            if next_interval not in self.instance.lower:
                raise ValueError(
                    f"Time {time:.6f} exceeds the final time interval "
                    f"after interval {interval}"
                )
            interval = next_interval
        return interval

    def evaluate(self, solution: Solution) -> Evaluation:
        violations = self._structural_violations(solution)
        route_evaluations: List[RouteEvaluation] = []

        for k in sorted(self.instance.vehicles):
            route = solution.routes.get(
                k, [self.instance.depot_start, self.instance.depot_return]
            )

            if route == [self.instance.depot_start, self.instance.depot_return]:
                continue

            crew = solution.crew.get(k)
            start_interval = solution.start_interval.get(k)

            if crew is None:
                violations.append(f"Vehicle {k}: no crew assigned")
                continue

            if start_interval not in self.instance.lower:
                violations.append(f"Vehicle {k}: invalid start interval {start_interval}")
                continue

            try:
                result = self._evaluate_route(k, route, crew, start_interval)
                route_evaluations.append(result)
            except (KeyError, ValueError) as exc:
                violations.append(f"Vehicle {k}: {exc}")

        self._crew_violations(solution, violations)
        self._capacity_violations(solution, violations)

        t_max = max((r.completion_time for r in route_evaluations), default=0.0)

        return Evaluation(
            feasible=(len(violations) == 0),
            t_max=t_max,
            route_evaluations=route_evaluations,
            violations=violations,
            metadata={
                "service_scale": self.service_scale,
                "customers": len(self.instance.customers),
                "vehicles": len(self.instance.vehicles),
                "crew_combinations": len(self.instance.crew_combinations),
                "time_intervals": len(self.instance.time_intervals),
            },
        )

    def _evaluate_route(
        self, k: int, route: List[int], crew: int, start_interval: int
    ) -> RouteEvaluation:
        if route[0] != self.instance.depot_start:
            raise ValueError("route must start at depot node o")
        if route[-1] != self.instance.depot_return:
            raise ValueError("route must end at dummy return node s")

        current_time = self.instance.lower[start_interval]
        interval = start_interval
        travel_total = 0.0
        service_total = 0.0
        arrivals: Dict[int, float] = {}
        used_intervals: Dict[Tuple[int, int], int] = {}

        for pos in range(len(route) - 1):
            i, j = route[pos], route[pos + 1]

            if i == j:
                raise ValueError(f"self-loop ({i},{j})")
            if (i, j) not in self.instance.distance:
                raise ValueError(f"missing distance for arc ({i},{j})")

            # Service is performed at the current node before leaving it.
            # The depot has no service time. This matches Algorithm 1 / Fitness.py.
            if i not in {self.instance.depot_start, self.instance.depot_return}:
                key = (i, crew, interval)
                if key not in self.instance.service_time:
                    raise ValueError(
                        f"missing service time for node {i}, crew {crew}, "
                        f"interval {interval}"
                    )
                service = self.instance.service_time[key] * self.service_scale
                current_time += service
                service_total += service

            # Resolve the speed before evaluating the travel time. The
            # repository's small instance has no explicit speed rows for
            # arcs into the dummy return node, but its interval speed is
            # unique across all supplied arcs.
            self._speed_for_arc(i, j, interval)

            used_intervals[(i, j)] = interval
            travel = self._travel_time(i, j, interval)
            current_time += travel
            travel_total += travel
            arrivals[j] = current_time

            interval = self._update_interval(current_time, interval)

        load = sum(
            self.instance.demand.get(i, 0.0)
            for i in route
            if i in self.instance.customers
        )

        return RouteEvaluation(
            vehicle=k,
            route=list(route),
            crew=crew,
            start_interval=start_interval,
            departure_time=self.instance.lower[start_interval],
            completion_time=current_time,
            load=load,
            travel_time=travel_total,
            service_time=service_total,
            arrival_times=arrivals,
            intervals=used_intervals,
        )

    def _structural_violations(self, solution: Solution) -> List[str]:
        violations: List[str] = []
        vehicle_ids = set(self.instance.vehicles)

        for k in solution.routes:
            if k not in vehicle_ids:
                violations.append(f"unknown vehicle {k}")

        seen: Dict[int, int] = {}
        for k in vehicle_ids:
            route = solution.routes.get(
                k, [self.instance.depot_start, self.instance.depot_return]
            )
            if not route:
                violations.append(f"Vehicle {k}: empty route")
                continue
            if route[0] != self.instance.depot_start:
                violations.append(
                    f"Vehicle {k}: route does not start at {self.instance.depot_start}"
                )
            if route[-1] != self.instance.depot_return:
                violations.append(
                    f"Vehicle {k}: route does not end at {self.instance.depot_return}"
                )

            for node in route:
                if node in self.instance.customers:
                    seen[node] = seen.get(node, 0) + 1

        for i in self.instance.customers:
            count = seen.get(i, 0)
            if count == 0:
                violations.append(f"Customer {i}: not served")
            elif count > 1:
                violations.append(f"Customer {i}: served {count} times")

        return violations

    def _capacity_violations(self, solution: Solution, violations: List[str]) -> None:
        for k, vehicle in self.instance.vehicles.items():
            route = solution.routes.get(k, [])
            load = sum(self.instance.demand.get(i, 0.0) for i in route)
            if load > vehicle.capacity:
                violations.append(
                    f"Vehicle {k} capacity: {load:g} > {vehicle.capacity:g} "
                    f"(excess {load - vehicle.capacity:g})"
                )

    def _crew_violations(self, solution: Solution, violations: List[str]) -> None:
        used: Dict[int, float] = {}
        for k, route in solution.routes.items():
            if route == [self.instance.depot_start, self.instance.depot_return]:
                continue
            d = solution.crew.get(k)
            if d is None:
                continue
            if d not in self.instance.crew_combinations:
                violations.append(f"Vehicle {k}: invalid crew combination {d}")
                continue

            crew_size = sum(self.instance.crew_composition[d].values())
            if crew_size > self.instance.vehicles[k].max_crew:
                violations.append(
                    f"Vehicle {k} crew size: {crew_size} > "
                    f"{self.instance.vehicles[k].max_crew} "
                    f"(excess {crew_size - self.instance.vehicles[k].max_crew})"
                )
            for c, count in self.instance.crew_composition[d].items():
                used[c] = used.get(c, 0) + count

        if self.instance.worker_limits:
            for c, used_count in used.items():
                limit = self.instance.worker_limits[c]
                if used_count > limit:
                    violations.append(
                        f"Worker type {c} availability: {used_count:g} > {limit:g} "
                        f"(excess {used_count - limit:g})"
                    )
