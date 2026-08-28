
from __future__ import annotations

from typing import List

from .model import Solution


def solution_to_vector(solution: Solution, vehicle_ids: List[int]) -> List[int]:
    route_part: List[int] = []
    for k in vehicle_ids:
        route = solution.routes.get(k, [0, 0])
        if not route:
            continue
        if not route_part:
            route_part.extend(route)
        else:
            route_part.extend(route[1:])

    crew_part = [solution.crew.get(k, 0) for k in vehicle_ids]
    time_part = [solution.start_interval.get(k, 0) for k in vehicle_ids]
    return route_part + crew_part + time_part
