from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List

from .loader import Instance


@dataclass
class RouteEvaluation:
    vehicle: int
    start_time: float
    completion_time: float
    travel_time: float
    service_time: float
    load: float
    customers: List[int]
    feasible: bool
    violations: List[str]


def evaluate_routes(inst: Instance, routes: Dict[int, List[int]], crew: Dict[int, int], start_intervals: Dict[int, int]) -> dict:
    """Independent constructive evaluator following the repository Fitness.py logic.

    It is intentionally separate from the MILP model. Times are in the same
    units as the source matrices (the repository uses distance/speed directly).
    """
    violations: list[str] = []
    route_results: list[RouteEvaluation] = []
    served = []

    for k, seq in routes.items():
        if not seq:
            continue
        d = crew[k]
        l = start_intervals[k]
        if l not in inst.intervals:
            violations.append(f"Vehicle {k}: invalid start interval {l}")
            continue
        current = inst.lower[l]
        travel_total = 0.0
        service_total = 0.0
        load = 0.0
        local_violations = []
        full = [inst.depot_start] + list(seq) + [inst.depot_end]

        for a, b in zip(full, full[1:]):
            if (a, b, l) not in inst.speed:
                local_violations.append(f"missing speed for arc {a}->{b}, interval {l}")
                continue
            speed = inst.speed[(a, b, l)]
            if speed <= 0:
                local_violations.append(f"non-positive speed for arc {a}->{b}, interval {l}: {speed}")
                continue
            tt = inst.distance[(a, b)] / speed
            travel_total += tt
            if a not in (inst.depot_start, inst.depot_end):
                st = inst.service.get((a, d, l))
                if st is None:
                    local_violations.append(f"missing service time for node {a}, crew {d}, interval {l}")
                    st = 0.0
                service_total += st
                load += inst.demand[a]
                served.append(a)
                current += st
            current += tt
            while l < max(inst.intervals) and current > inst.upper[l]:
                l += 1

        if load > inst.vehicles[k].capacity + 1e-9:
            local_violations.append(f"vehicle capacity {load} > {inst.vehicles[k].capacity}")
        route_results.append(RouteEvaluation(k, inst.lower[start_intervals[k]], current, travel_total, service_total, load, list(seq), not local_violations, local_violations))
        violations.extend([f"Vehicle {k}: {v}" for v in local_violations])

    expected = set(inst.customers)
    if set(served) != expected or len(served) != len(expected):
        missing = sorted(expected - set(served))
        dup = sorted({x for x in served if served.count(x) > 1})
        if missing:
            violations.append(f"customer coverage missing: {missing}")
        if dup:
            violations.append(f"customer coverage duplicated: {dup}")

    return {
        "feasible": not violations,
        "T_MAX": max((r.completion_time for r in route_results), default=0.0),
        "route_results": [asdict(r) for r in route_results],
        "violations": violations,
    }
