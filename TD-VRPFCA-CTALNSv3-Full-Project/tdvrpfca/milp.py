"""Exact Mixed-Integer Linear Program (MILP) for TD-VRPFCA with mathematical fixes.

This module implements the TD-VRPFCA mathematical formulation with the critical
bug fixes discovered during project validation:
  1. (c5) and (c6): Exclude depot nodes (o and s) from customer unit-degree rules,
     restoring the true multi-vehicle routing capability.
  2. (c17): Sum over outgoing arcs rather than enforcing single-customer equality,
     preventing departure time from being artificially locked to 0.0.
  3. (c18) and (c19): Evaluate time-dependent interval bounds based on departure time
     (arrival + service time) rather than arrival time alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import gurobipy as gp
from gurobipy import GRB

from .model import Instance


@dataclass
class MILPResult:
    status: int
    status_name: str
    runtime: float
    objective: float | None
    bound: float | None
    gap: float | None
    sol_count: int
    num_vars: int
    num_constraints: int
    model: gp.Model
    x: Dict[Tuple[int, int, int, int], gp.Var]
    y: Dict[Tuple[int, int], gp.Var]
    z: Dict[Tuple[int, int], gp.Var]
    w: Dict[Tuple[int, int], gp.Var]
    tmax: gp.Var


class MILPDataError(ValueError):
    pass


def _status_name(status: int) -> str:
    names = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.TIME_LIMIT: "TIME_LIMIT",
        GRB.INTERRUPTED: "INTERRUPTED",
        GRB.NODE_LIMIT: "NODE_LIMIT",
        GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
        GRB.SUBOPTIMAL: "SUBOPTIMAL",
    }
    return names.get(status, str(status))


def _required_arcs(inst: Instance):
    o, s = inst.depot_start, inst.depot_end
    return [
        (i, j)
        for i in inst.nodes
        for j in inst.nodes
        if i != j and i != s and j != o and not (i == o and j == s)
    ]


def _check_model_data(inst: Instance, arcs):
    missing_distance = [(i, j) for i, j in arcs if (i, j) not in inst.distance]
    if missing_distance:
        raise MILPDataError(f"Missing distance values for required arcs: {missing_distance[:10]}")

    missing_speed = [
        (i, j, l)
        for i, j in arcs
        for l in inst.intervals
        if (i, j, l) not in inst.speed or inst.speed[(i, j, l)] <= 0
    ]
    if missing_speed:
        raise MILPDataError(f"Missing/non-positive speed for arcs: {missing_speed[:10]}")

    missing_service = [
        (i, d, l)
        for i in inst.customers
        for d in inst.crew
        for l in inst.intervals
        if (i, d, l) not in inst.service
    ]
    if missing_service:
        raise MILPDataError(f"Missing service-time values: {missing_service[:10]}")


def build_corrected_milp(
    inst: Instance,
    time_limit: float = 3600,
    mip_gap: float | None = None,
    verbose: bool = True,
    fix_all_bugs: bool = True,
) -> MILPResult:
    """Build the TD-VRPFCA MILP model with verified algebraic fixes."""
    arcs = _required_arcs(inst)
    _check_model_data(inst, arcs)

    K = list(inst.vehicles)
    D = list(inst.crew)
    L = list(inst.intervals)
    N = list(inst.nodes)
    I = list(inst.customers)
    o, s = inst.depot_start, inst.depot_end

    M1 = float(len(N))
    M2 = float(max(inst.upper.values()))

    model = gp.Model("TD-VRPFCA_corrected" if fix_all_bugs else "TD-VRPFCA_paper")
    model.Params.TimeLimit = time_limit
    if mip_gap is not None:
        model.Params.MIPGap = mip_gap
    model.Params.OutputFlag = 1 if verbose else 0

    x = {
        (k, i, j, l): model.addVar(vtype=GRB.BINARY, name=f"x_{k}_{i}_{j}_{l}")
        for k in K for i, j in arcs for l in L
    }
    y = {
        (k, d): model.addVar(vtype=GRB.BINARY, name=f"y_{k}_{d}")
        for k in K for d in D
    }
    z = {
        (k, i): model.addVar(vtype=GRB.BINARY, name=f"z_{k}_{i}")
        for k in K for i in N
    }
    w = {
        (k, i): model.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name=f"w_{k}_{i}")
        for k in K for i in N
    }
    tmax = model.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="TMAX")

    model.setObjective(tmax, GRB.MINIMIZE)

    # (2) at most one departure per vehicle.
    for k in K:
        model.addConstr(
            gp.quicksum(x[k, o, j, l] for j in N if (o, j) in arcs for l in L) <= 1,
            name=f"c2_{k}",
        )

    # (3) at most one return per vehicle.
    for k in K:
        model.addConstr(
            gp.quicksum(x[k, i, s, l] for i in N if (i, s) in arcs for l in L) <= 1,
            name=f"c3_{k}",
        )

    # (4) exactly one visit per customer node.
    for i in I:
        model.addConstr(
            gp.quicksum(z[k, i] for k in K) == 1,
            name=f"c4_{i}",
        )

    # (5) incoming arc constraints
    for j in N:
        if fix_all_bugs:
            if j == o or j == s:
                continue
        else:
            if j == o:
                continue
        model.addConstr(
            gp.quicksum(
                x[k, i, j, l]
                for k in K for i in N
                if i != j and i != s and (i, j) in arcs
                for l in L
            ) == 1,
            name=f"c5_{j}",
        )

    # (6) outgoing arc constraints
    for j in N:
        if fix_all_bugs:
            if j == o or j == s:
                continue
        else:
            if j == s:
                continue
        model.addConstr(
            gp.quicksum(
                x[k, j, i, l]
                for k in K for i in N
                if i != j and i != o and (j, i) in arcs
                for l in L
            ) == 1,
            name=f"c6_{j}",
        )

    # (7) flow balance at customer nodes
    for k in K:
        for p in I:
            inflow = gp.quicksum(
                x[k, i, p, l]
                for i in N
                if i != p and i != s and (i, p) in arcs
                for l in L
            )
            outflow = gp.quicksum(
                x[k, p, j, l]
                for j in N
                if j != p and j != o and (p, j) in arcs
                for l in L
            )
            model.addConstr(inflow - outflow == 0, name=f"c7_{k}_{p}")

    # (8) exactly one crew combination per vehicle.
    for k in K:
        model.addConstr(
            gp.quicksum(y[k, d] for d in D) == 1,
            name=f"c8_{k}",
        )

    # (9) link incoming arcs to vehicle visit indicator.
    for k in K:
        for i in I:
            model.addConstr(
                gp.quicksum(
                    x[k, j, i, l]
                    for j in N
                    if j != i and j != s and (j, i) in arcs
                    for l in L
                ) == z[k, i],
                name=f"c9_{k}_{i}",
            )

    # (10) link outgoing arcs to vehicle visit indicator.
    for k in K:
        for i in I:
            model.addConstr(
                gp.quicksum(
                    x[k, i, j, l]
                    for j in N
                    if j != i and j != o and (i, j) in arcs
                    for l in L
                ) <= M1 * z[k, i],
                name=f"c10_{k}_{i}",
            )

    # (11) vehicle capacity.
    for k in K:
        model.addConstr(
            gp.quicksum(inst.demand[i] * z[k, i] for i in I) <= inst.vehicles[k].capacity,
            name=f"c11_{k}",
        )

    # (12) vehicle crew capacity.
    for k in K:
        model.addConstr(
            gp.quicksum(
                sum(inst.crew[d].values()) * y[k, d]
                for d in D
            ) <= inst.vehicles[k].max_crew,
            name=f"c12_{k}",
        )

    # (13) total worker availability per worker type.
    if inst.worker_availability:
        for c, limit in inst.worker_availability.items():
            model.addConstr(
                gp.quicksum(
                    inst.crew[d].get(c, 0.0) * y[k, d]
                    for k in K for d in D
                ) <= limit,
                name=f"c13_{c}",
            )

    # Helper: service time expression
    def service_expr(k, i, l):
        return gp.quicksum(inst.service[(i, d, l)] * y[k, d] for d in D)

    # (15) and (16) time propagation.
    for k in K:
        for i, j in arcs:
            if i == o:
                continue
            for l in L:
                travel = inst.distance[(i, j)] / inst.speed[(i, j, l)]
                xvar = x[k, i, j, l]
                svc = service_expr(k, i, l)
                model.addConstr(
                    w[k, j] >= w[k, i] + travel * xvar + svc - M2 * (1 - xvar),
                    name=f"c15_{k}_{i}_{j}_{l}",
                )
                model.addConstr(
                    w[k, j] <= w[k, i] + travel * xvar + svc + M2 * (1 - xvar),
                    name=f"c16_{k}_{i}_{j}_{l}",
                )

    # (17) departure time at depot
    if fix_all_bugs:
        for k in K:
            model.addConstr(
                w[k, o] == gp.quicksum(
                    inst.lower[l] * x[k, o, j, l]
                    for j in N if j != o and (o, j) in arcs
                    for l in L
                ),
                name=f"c17_{k}",
            )
    else:
        for k in K:
            for j in N:
                if j == o or (o, j) not in arcs:
                    continue
                for l in L:
                    model.addConstr(
                        w[k, o] == inst.lower[l] * x[k, o, j, l],
                        name=f"c17_{k}_{j}_{l}",
                    )

    # (18) lower bound of interval for active arc.
    for k in K:
        for i, j in arcs:
            for l in L:
                svc = (0.0 if i == o else service_expr(k, i, l)) if fix_all_bugs else 0.0
                model.addConstr(
                    inst.lower[l] * x[k, i, j, l] <= w[k, i] + svc,
                    name=f"c18_{k}_{i}_{j}_{l}",
                )

    # (19) upper bound of interval for active arc.
    for k in K:
        for i, j in arcs:
            for l in L:
                svc = (0.0 if i == o else service_expr(k, i, l)) if fix_all_bugs else 0.0
                model.addConstr(
                    inst.upper[l] >= (w[k, i] + svc) - M2 * (1 - x[k, i, j, l]),
                    name=f"c19_{k}_{i}_{j}_{l}",
                )

    # (20) TMAX definition.
    for k in K:
        model.addConstr(tmax >= w[k, s], name=f"c20_{k}")

    model.update()

    return MILPResult(
        status=model.Status,
        status_name=_status_name(model.Status),
        runtime=0.0,
        objective=None,
        bound=None,
        gap=None,
        sol_count=0,
        num_vars=model.NumVars,
        num_constraints=model.NumConstrs,
        model=model,
        x=x, y=y, z=z, w=w, tmax=tmax,
    )
