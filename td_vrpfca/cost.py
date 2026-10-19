"""Novelty 2: Operational Cost Model for TD-VRPFCA.

Formulates total operational costs alongside makespan (T_MAX):
  C_total = C_vehicle_fixed + C_distance + C_crew_regular + C_crew_overtime
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

from .model import Instance, Solution, evaluate_solution


@dataclass
class CostConfig:
    """Configurable rates and parameters for the operational cost model."""
    # Fixed charge incurred per activated vehicle (F_k)
    vehicle_fixed_cost: float = 100.0

    # Fuel / maintenance cost per unit distance traveled (c_k)
    distance_cost_per_unit: float = 1.20

    # Base hourly wage rate per worker type:
    # 1: DP (Delivery Person), 2: Dr (Driver), 3: MFDP (Multi-Function Delivery Person)
    worker_hourly_wages: Dict[int, float] = field(default_factory=lambda: {
        1: 15.0,  # $15 / hr
        2: 20.0,  # $20 / hr
        3: 25.0,  # $25 / hr
    })

    # Standard regular shift duration threshold (in minutes)
    regular_shift_limit_minutes: float = 480.0  # 8 hours

    # Overtime wage multiplier applied to hours exceeding regular shift limit
    overtime_multiplier: float = 1.5

    # Conversion factor from clock time units (minutes) to wage billing hours
    time_to_hours: float = 1.0 / 60.0


@dataclass
class CostBreakdown:
    """Detailed decomposition of operational costs for a routing plan."""
    vehicle_fixed_cost: float
    distance_cost: float
    regular_crew_cost: float
    overtime_crew_cost: float
    total_cost: float
    active_vehicles: int
    total_distance: float
    total_crew_hours: float
    total_overtime_hours: float
    per_vehicle_details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_route_distance(
    inst: Instance,
    customers: List[int],
    return_leg_mode: str = "source",
) -> float:
    """Calculate the physical/evaluated distance traveled by a single vehicle route."""
    if not customers:
        return 0.0

    full_route = [inst.depot_start] + list(customers) + [inst.depot_end]
    total_dist = 0.0

    for a, b in zip(full_route, full_route[1:]):
        if return_leg_mode == "physical" and inst.depot_end == 101 and b == inst.depot_end:
            dist = inst.distance.get((a, inst.depot_start), inst.distance.get((inst.depot_start, a), 0.0))
        else:
            dist = inst.distance.get((a, b), 0.0)
        total_dist += dist

    return total_dist


def evaluate_cost(
    inst: Instance,
    solution: Solution,
    evaluation: Optional[Dict[str, Any]] = None,
    cost_config: Optional[CostConfig] = None,
    return_leg_mode: str = "source",
) -> CostBreakdown:
    """Compute the multi-term operational cost for a candidate solution.

    Parameters
    ----------
    inst : Instance
        The problem instance.
    solution : Solution
        The vehicle routes, crew assignments, and departure intervals.
    evaluation : dict, optional
        Pre-computed result from evaluate_solution() to avoid duplicate work.
    cost_config : CostConfig, optional
        Cost parameters. Defaults to standard configuration if None.
    return_leg_mode : str
        'source' or 'physical' distance evaluation.

    Returns
    -------
    CostBreakdown
        Full itemized breakdown of vehicle fixed, distance, and crew costs.
    """
    if cost_config is None:
        cost_config = CostConfig()

    if evaluation is None:
        evaluation = evaluate_solution(inst, solution, return_leg_mode=return_leg_mode)

    route_evals = {r["vehicle"]: r for r in evaluation.get("route_results", [])}

    total_fixed_cost = 0.0
    total_dist_cost = 0.0
    total_regular_crew_cost = 0.0
    total_ot_crew_cost = 0.0
    total_dist = 0.0
    total_crew_hours = 0.0
    total_ot_hours = 0.0
    active_vehicles = 0
    per_vehicle_details: List[Dict[str, Any]] = []

    for k in sorted(inst.vehicles):
        customers = solution.routes.get(k, [])
        if not customers:
            continue

        active_vehicles += 1
        crew_id = solution.crew.get(k, 1)
        crew_comp = inst.crew.get(crew_id, {})

        # 1. Hourly crew wage rate for this vehicle's assigned crew
        hourly_crew_wage = sum(
            cost_config.worker_hourly_wages.get(wt, 15.0) * count
            for wt, count in crew_comp.items()
        )

        # 2. Distance and route duration
        r_dist = calculate_route_distance(inst, customers, return_leg_mode=return_leg_mode)
        total_dist += r_dist

        r_eval = route_evals.get(k)
        duration_minutes = r_eval["completion_time"] if r_eval else 0.0
        duration_hours = duration_minutes * cost_config.time_to_hours
        total_crew_hours += duration_hours

        # 3. Regular vs Overtime crew costs
        reg_limit = cost_config.regular_shift_limit_minutes
        if duration_minutes <= reg_limit:
            reg_hours = duration_hours
            ot_hours = 0.0
        else:
            reg_hours = reg_limit * cost_config.time_to_hours
            ot_hours = (duration_minutes - reg_limit) * cost_config.time_to_hours

        total_ot_hours += ot_hours

        r_fixed = cost_config.vehicle_fixed_cost
        r_dist_cost = r_dist * cost_config.distance_cost_per_unit
        r_reg_crew_cost = reg_hours * hourly_crew_wage
        r_ot_crew_cost = ot_hours * hourly_crew_wage * cost_config.overtime_multiplier
        r_total_cost = r_fixed + r_dist_cost + r_reg_crew_cost + r_ot_crew_cost

        total_fixed_cost += r_fixed
        total_dist_cost += r_dist_cost
        total_regular_crew_cost += r_reg_crew_cost
        total_ot_crew_cost += r_ot_crew_cost

        per_vehicle_details.append({
            "vehicle": k,
            "crew_id": crew_id,
            "hourly_crew_wage": hourly_crew_wage,
            "distance": r_dist,
            "duration_minutes": duration_minutes,
            "duration_hours": duration_hours,
            "regular_hours": reg_hours,
            "overtime_hours": ot_hours,
            "fixed_cost": r_fixed,
            "distance_cost": r_dist_cost,
            "regular_crew_cost": r_reg_crew_cost,
            "overtime_crew_cost": r_ot_crew_cost,
            "total_route_cost": r_total_cost,
        })

    c_total = total_fixed_cost + total_dist_cost + total_regular_crew_cost + total_ot_crew_cost

    return CostBreakdown(
        vehicle_fixed_cost=total_fixed_cost,
        distance_cost=total_dist_cost,
        regular_crew_cost=total_regular_crew_cost,
        overtime_crew_cost=total_ot_crew_cost,
        total_cost=c_total,
        active_vehicles=active_vehicles,
        total_distance=total_dist,
        total_crew_hours=total_crew_hours,
        total_overtime_hours=total_ot_hours,
        per_vehicle_details=per_vehicle_details,
    )
