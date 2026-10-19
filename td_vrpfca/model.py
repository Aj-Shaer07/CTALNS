"""Shared TD-VRPFCA data model and objective evaluator.

The default behavior preserves source-compatible preprocessing conventions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Any, Iterator


@dataclass(frozen=True)
class Vehicle:
    k: int
    capacity: float
    max_crew: float


@dataclass
class Instance:
    name: str
    customers: List[int]
    nodes: List[int]
    depot_start: int
    depot_end: int
    vehicles: Dict[int, Vehicle]
    crew: Dict[int, Dict[int, float]]  # crew_id -> worker_type -> count
    worker_availability: Dict[int, float]
    demand: Dict[int, float]
    distance: Dict[Tuple[int, int], float]
    speed: Dict[Tuple[int, int, int], float]
    service: Dict[Tuple[int, int, int], float]
    lower: Dict[int, float]
    upper: Dict[int, float]
    intervals: List[int]
    travel_time_factor: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Solution:
    routes: Dict[int, List[int]]
    crew: Dict[int, int]
    start_intervals: Dict[int, int]

    def __iter__(self) -> Iterator[Any]:
        """Support unpacking as: routes, crew, start_intervals = solution."""
        return iter((self.routes, self.crew, self.start_intervals))


@dataclass
class RouteResult:
    vehicle: int
    customers: List[int]
    crew_id: int
    start_interval: int
    start_time: float
    completion_time: float
    travel_time: float
    service_time: float
    load: float
    feasible: bool
    violations: List[str]


def _expand_crew_counts(inst: Instance, crew: Dict[int, int]) -> Dict[int, int]:
    """Return crew assignment for every vehicle from the BWO count encoding."""
    result: Dict[int, int] = {}
    vehicle_ids = sorted(inst.vehicles)
    pos = 0
    for crew_id in sorted(inst.crew):
        count = int(crew.get(crew_id, 0))
        for _ in range(max(0, count)):
            if pos < len(vehicle_ids):
                result[vehicle_ids[pos]] = crew_id
                pos += 1
    return result


def evaluate_solution(
    inst: Instance,
    solution: Solution,
    *,
    check_worker_availability: bool = True,
    check_customer_coverage: bool = True,
    return_leg_mode: str = "source",
) -> dict:
    """Evaluate a feasible candidate using the common objective evaluator.

    Time-dependent convention: for each arc, the current interval is used for
    the service at its tail and for the arc travel time; the interval is then
    advanced if the resulting clock exceeds its upper boundary. This mirrors
    the constructive evaluator / public Fitness.py behavior.

    return_leg_mode:
      - "source": preserve the authors' large-instance preprocessing where arcs
        involving dummy sink 101 have distance zero.
      - "physical": interpret the dummy sink as the physical depot and use the
        distance from each customer back to depot 0.
    """
    if return_leg_mode not in {"source", "physical"}:
        raise ValueError("return_leg_mode must be 'source' or 'physical'")

    violations: List[str] = []
    route_results: List[RouteResult] = []
    all_served: List[int] = []
    used_worker_counts = {wt: 0.0 for wt in (getattr(inst, "worker_availability", None) or {})}

    # Check that the vehicle-level assignment is complete and crew IDs are valid.
    for k in inst.vehicles:
        if k not in solution.crew:
            violations.append(f"Vehicle {k}: no crew assignment")
        elif solution.crew[k] not in inst.crew:
            violations.append(f"Vehicle {k}: invalid crew ID {solution.crew[k]}")
        else:
            crew_id = solution.crew[k]
            for wt, count in inst.crew[crew_id].items():
                used_worker_counts[wt] = used_worker_counts.get(wt, 0.0) + count
            crew_size = sum(inst.crew[crew_id].values())
            if crew_size > inst.vehicles[k].max_crew + 1e-9:
                violations.append(
                    f"Vehicle {k}: crew size {crew_size} exceeds max {inst.vehicles[k].max_crew}"
                )

    if check_worker_availability and getattr(inst, "worker_availability", None):
        for wt, used in used_worker_counts.items():
            available = inst.worker_availability.get(wt)
            if available is not None and used > available + 1e-9:
                violations.append(
                    f"Worker type {wt}: assigned {used}, availability {available}"
                )

    interval_set = set(inst.intervals)
    last_interval = max(inst.intervals)
    expected = set(inst.customers)

    for k in sorted(inst.vehicles):
        seq = list(solution.routes.get(k, []))
        if not seq:
            continue

        local: List[str] = []
        if k not in solution.crew or solution.crew[k] not in inst.crew:
            local.append(f"Vehicle {k}: invalid or missing crew assignment")
            crew_id = min(inst.crew)
        else:
            crew_id = solution.crew[k]

        start_interval = solution.start_intervals.get(k)
        if start_interval not in interval_set:
            local.append(f"Vehicle {k}: invalid start interval {start_interval}")
            start_interval = min(inst.intervals)

        current = float(inst.lower[start_interval])
        start_time = current
        travel_total = 0.0
        service_total = 0.0
        load = 0.0
        full_route = [inst.depot_start] + seq + [inst.depot_end]

        for a, b in zip(full_route, full_route[1:]):
            if a not in (inst.depot_start, inst.depot_end):
                st = inst.service.get((a, crew_id, start_interval))
                if st is None:
                    local.append(
                        f"Vehicle {k}: missing service time for node {a}, crew {crew_id}, interval {start_interval}"
                    )
                    st = 0.0
                service_total += st
                current += st
                load += inst.demand.get(a, 0.0)
                all_served.append(a)

            if return_leg_mode == "physical" and inst.depot_end == 101 and b == inst.depot_end:
                dist = inst.distance.get((a, inst.depot_start), inst.distance.get((inst.depot_start, a)))
                spd = inst.speed.get((a, inst.depot_start, start_interval))
            else:
                dist = inst.distance.get((a, b))
                spd = inst.speed.get((a, b, start_interval))

            if dist is None:
                local.append(f"Vehicle {k}: missing distance for arc {a}->{b}")
                dist = 0.0
            if spd is None or spd <= 0:
                local.append(f"Vehicle {k}: missing/non-positive speed for arc {a}->{b}, interval {start_interval}")
                tt = 0.0
            else:
                tt = float(dist) / float(spd) * getattr(inst, "travel_time_factor", 1.0)
            travel_total += tt
            current += tt

            while start_interval < last_interval and current > inst.upper[start_interval]:
                start_interval += 1

        if load > inst.vehicles[k].capacity + 1e-9:
            local.append(f"Vehicle {k}: load {load} exceeds capacity {inst.vehicles[k].capacity}")

        route_results.append(
            RouteResult(
                vehicle=k,
                customers=seq,
                crew_id=crew_id,
                start_interval=solution.start_intervals.get(k, min(inst.intervals)),
                start_time=start_time,
                completion_time=current,
                travel_time=travel_total,
                service_time=service_total,
                load=load,
                feasible=not local,
                violations=local,
            )
        )
        violations.extend(local)

    if check_customer_coverage and (len(all_served) != len(expected) or set(all_served) != expected):
        missing = sorted(expected - set(all_served))
        duplicates = sorted({c for c in all_served if all_served.count(c) > 1})
        if missing:
            violations.append(f"Customer coverage missing: {missing}")
        if duplicates:
            violations.append(f"Customer coverage duplicated: {duplicates}")

    t_max = max((r.completion_time for r in route_results), default=float("inf"))
    return {
        "feasible": not violations and t_max != float("inf"),
        "T_MAX": t_max,
        "route_results": [asdict(r) for r in route_results],
        "violations": violations,
    }
