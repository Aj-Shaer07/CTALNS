from __future__ import annotations

from typing import Dict, List

from .model import Instance, Solution


def first_feasible_crew(instance: Instance, vehicle_id: int) -> int:
    max_crew = instance.vehicles[vehicle_id].max_crew
    for d in instance.crew_combinations:
        if sum(instance.crew_composition[d].values()) <= max_crew:
            return d
    raise ValueError(f"No crew combination fits vehicle {vehicle_id}")


def deterministic_solution(instance: Instance) -> Solution:
    """Deterministic feasibility-oriented construction for Objective 1 tests.

    Customers are assigned in input order using a balanced first-fit rule over
    the available vehicles. This is only a construction heuristic; it is not an
    optimization method.
    """
    vehicle_ids = sorted(instance.vehicles)
    if not vehicle_ids:
        raise ValueError("No vehicles available")

    routes: Dict[int, List[int]] = {
        k: [instance.depot_start, instance.depot_return] for k in vehicle_ids
    }
    crew: Dict[int, int] = {}
    start_interval: Dict[int, int] = {}
    loads = {k: 0.0 for k in vehicle_ids}

    # Spread customers over the available fleet while respecting capacity.
    for customer in instance.customers:
        demand = instance.demand[customer]
        candidates = [
            k
            for k in vehicle_ids
            if loads[k] + demand <= instance.vehicles[k].capacity
        ]
        if not candidates:
            raise ValueError(
                f"Constructive solution could not assign customer {customer} "
                "within available vehicle capacities"
            )

        # Choose the currently least-loaded feasible vehicle.
        k = min(candidates, key=lambda vehicle_id: (loads[vehicle_id], vehicle_id))
        routes[k].insert(-1, customer)
        loads[k] += demand

    for k in vehicle_ids:
        if len(routes[k]) > 2:
            crew[k] = first_feasible_crew(instance, k)
            start_interval[k] = instance.time_intervals[0]

    return Solution(routes=routes, crew=crew, start_interval=start_interval)
