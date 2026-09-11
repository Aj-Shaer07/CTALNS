from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import gurobipy as gp
from gurobipy import GRB

from .loader import Instance


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
    """Arcs that can actually occur in constraints (2)-(20).

    The paper has a start depot o and dummy return s.  The public small
    dataset has no speed entry for the artificial o->s arc; that arc is also
    unnecessary for any non-empty route.  It is therefore excluded rather
    than assigned a fabricated speed.
    """
    o, s = inst.depot_start, inst.depot_end
    return [
        (i, j)
        for i in inst.nodes
        for j in inst.nodes
        if i != j and i != s and j != o and not (i == o and j == s)
    ]


def _check_model_data(inst: Instance, arcs):
    missing_distance = [
        (i, j) for i, j in arcs if (i, j) not in inst.distance
    ]
    if missing_distance:
        raise MILPDataError(
            f"Missing distance values for required arcs; examples: {missing_distance[:10]}"
        )

    missing_speed = [
        (i, j, l)
        for i, j in arcs
        for l in inst.intervals
        if (i, j, l) not in inst.speed or inst.speed[(i, j, l)] <= 0
    ]
    if missing_speed:
        raise MILPDataError(
            "Missing/non-positive time-dependent speed for required arcs; "
            f"examples: {missing_speed[:10]}"
        )

    missing_service = [
        (i, d, l)
        for i in inst.customers
        for d in inst.crew
        for l in inst.intervals
        if (i, d, l) not in inst.service
    ]
    if missing_service:
        raise MILPDataError(
            "Missing service-time values t_id^l; examples: "
            f"{missing_service[:10]}"
        )


def build_paper_milp(
    inst: Instance,
    time_limit: float = 3600,
    mip_gap: float | None = None,
    verbose: bool = True,
    allow_reconstructed: bool = False,
) -> MILPResult:
    """Build the published TD-VRPFCA MILP (1)-(22).

    The formulation follows the printed equations.  The service contribution
    in (15)-(16) is aggregated over d; because (8) enforces exactly one crew
    per vehicle, this is algebraically equivalent to the paper's indexed form
    while avoiding an unnecessary factor |D| in the constraint count.
    """
    if set(inst.worker_availability) != {1, 2, 3}:
        if not allow_reconstructed:
            raise MILPDataError(
                "Constraint (13) needs V^c for worker types 1, 2 and 3. "
                "The public dataset does not provide it. Run with the explicitly "
                "labelled reconstructed mode."
            )
        # Source-supported reconstruction from the paper's reported small-instance
        # crew compositions: max #DP=4, #Dr=2, #MFDP=2.  The repository's worker
        # type order is DP, Dr, MFDP (see calculos_BWO.py / Tabu Search.py).
        inst.worker_availability = {1: 4.0, 2: 2.0, 3: 2.0}

    arcs = _required_arcs(inst)
    _check_model_data(inst, arcs)

    K = list(inst.vehicles)
    D = list(inst.crew)
    L = list(inst.intervals)
    N = list(inst.nodes)
    I = list(inst.customers)
    o, s = inst.depot_start, inst.depot_end

    # Paper: M1=|N| and M2=max_l U^l.  No arbitrary multiplier is needed.
    M1 = float(len(N))
    M2 = float(max(inst.upper.values()))

    model = gp.Model("TD-VRPFCA_paper")
    model.Params.TimeLimit = time_limit
    if mip_gap is not None:
        model.Params.MIPGap = mip_gap
    model.Params.OutputFlag = 1 if verbose else 0

    # x[k,i,j,l] = 1 iff vehicle k traverses i->j in interval l.
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

    # (4) every customer is assigned to exactly one vehicle.
    for i in I:
        model.addConstr(
            gp.quicksum(z[k, i] for k in K) == 1,
            name=f"c4_{i}",
        )

    # (5) exactly one incoming arc for each node except start depot.
    for j in N:
        if j == o or j == s:
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

    # (6) exactly one outgoing arc for each customer node.
    for j in N:
        if j == o or j == s:
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

    # (7) vehicle flow balance at customers.
    for k in K:
        for j in N:
            if j in (o, s):
                continue
            incoming = gp.quicksum(
                x[k, i, j, l]
                for i in N if i != j and i != s and (i, j) in arcs
                for l in L
            )
            outgoing = gp.quicksum(
                x[k, j, i, l]
                for i in N if i != j and i != o and (j, i) in arcs
                for l in L
            )
            model.addConstr(incoming == outgoing, name=f"c7_{k}_{j}")

    # (8) exactly one crew combination per vehicle.
    for k in K:
        model.addConstr(
            gp.quicksum(y[k, d] for d in D) == 1,
            name=f"c8_{k}",
        )

    # (9) a crew assignment is compatible with the vehicle visiting nodes.
    for k in K:
        for i in N:
            model.addConstr(
                gp.quicksum(y[k, d] for d in D) >= z[k, i],
                name=f"c9_{k}_{i}",
            )

    # (10) outgoing sequence from i implies i is visited by k.
    for k in K:
        for i in N:
            model.addConstr(
                gp.quicksum(
                    x[k, i, j, l]
                    for j in N if j != i and j != o and (i, j) in arcs
                    for l in L
                ) <= M1 * z[k, i],
                name=f"c10_{k}_{i}",
            )

    # (11) arrival time is zero unless node is visited.
    for k in K:
        for i in N:
            model.addConstr(w[k, i] <= M2 * z[k, i], name=f"c11_{k}_{i}")

    # (12) vehicle capacity.
    for k in K:
        model.addConstr(
            gp.quicksum(inst.demand[i] * z[k, i] for i in I)
            <= gp.quicksum(inst.vehicles[k].capacity * y[k, d] for d in D),
            name=f"c12_{k}",
        )

    # (13) workforce availability by worker type.
    for c in (1, 2, 3):
        model.addConstr(
            gp.quicksum(inst.crew[d][c] * y[k, d] for k in K for d in D)
            <= inst.worker_availability[c],
            name=f"c13_{c}",
        )

    # (14) maximum workers in each vehicle cabin.
    for k in K:
        model.addConstr(
            gp.quicksum(inst.crew[d][c] * y[k, d] for d in D for c in (1, 2, 3))
            <= inst.vehicles[k].max_crew,
            name=f"c14_{k}",
        )

    # Service at node i in interval l for vehicle k, given its selected crew.
    def service_expr(k: int, i: int, l: int):
        return gp.quicksum(inst.service[i, d, l] * y[k, d] for d in D)

    # (15)-(16).  The paper prints one pair for each d. Since (8) makes y[k,d]
    # one-hot, the aggregated service expression is equivalent and much smaller.
    for k in K:
        for i, j in arcs:
            if i == s or j == o:
                continue
            for l in L:
                travel = inst.distance[i, j] / inst.speed[i, j, l]
                xvar = x[k, i, j, l]
                svc = 0.0 if i == o else service_expr(k, i, l)
                model.addConstr(
                    w[k, j] >= w[k, i] + travel * xvar + svc - M2 * (1 - xvar),
                    name=f"c15_{k}_{i}_{j}_{l}",
                )
                model.addConstr(
                    w[k, i] <= w[k, j] + travel * xvar + svc - M2 * (xvar - 1),
                    name=f"c16_{k}_{i}_{j}_{l}",
                )

    # (17) departure/start time is the lower bound of selected initial interval.
    for k in K:
        model.addConstr(
            w[k, o] == gp.quicksum(
                inst.lower[l] * x[k, o, j, l] 
                for j in N if j != o and (o, j) in arcs 
                for l in L
            ),
            name=f"c17_{k}",
        )

    # (18) lower bound of interval for an active arc (fixed to use departure time).
    for k in K:
        for i, j in arcs:
            for l in L:
                svc = 0.0 if i == o else service_expr(k, i, l)
                model.addConstr(
                    inst.lower[l] * x[k, i, j, l] <= w[k, i] + svc,
                    name=f"c18_{k}_{i}_{j}_{l}",
                )

    # (19) upper bound of interval for an active arc (fixed to use departure time).
    for k in K:
        for i, j in arcs:
            for l in L:
                svc = 0.0 if i == o else service_expr(k, i, l)
                model.addConstr(
                    inst.upper[l] >= (w[k, i] + svc) - M2 * (1 - x[k, i, j, l]),
                    name=f"c19_{k}_{i}_{j}_{l}",
                )

    # (20) makespan. Because s is in N\{o}, w[k,s]-w[k,o] is included.
    for k in K:
        for i in N:
            if i == o:
                continue
            model.addConstr(tmax >= w[k, i] - w[k, o], name=f"c20_{k}_{i}")

    model.update()
    return MILPResult(
        status=-1,
        status_name="NOT_SOLVED",
        runtime=0.0,
        objective=None,
        bound=None,
        gap=None,
        sol_count=0,
        num_vars=model.NumVars,
        num_constraints=model.NumConstrs,
        model=model,
        x=x,
        y=y,
        z=z,
        w=w,
        tmax=tmax,
    )


def solve(result: MILPResult) -> MILPResult:
    result.model.optimize()
    m = result.model
    result.status = m.Status
    result.status_name = _status_name(m.Status)
    result.runtime = m.Runtime
    result.sol_count = m.SolCount
    result.objective = m.ObjVal if m.SolCount else None
    result.bound = m.ObjBound if m.Status in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.NODE_LIMIT, GRB.INTERRUPTED, GRB.SUBOPTIMAL) else None
    result.gap = m.MIPGap if m.SolCount else None
    return result


def extract_solution(result: MILPResult) -> dict[str, Any]:
    m = result.model
    if m.SolCount == 0:
        return {"feasible_solution": False}

    routes = {}
    crews = {}
    visits = {}
    arrivals = {}

    for k in sorted({key[0] for key in result.y}):
        chosen = [d for (kk, d), var in result.y.items() if kk == k and var.X > 0.5]
        if chosen:
            crews[str(k)] = chosen[0]

    for k in sorted({key[0] for key in result.x}):
        arcs = []
        for (kk, i, j, l), var in result.x.items():
            if kk == k and var.X > 0.5:
                arcs.append({"i": i, "j": j, "interval": l})
        routes[str(k)] = arcs

    for (k, i), var in result.z.items():
        if var.X > 0.5:
            visits.setdefault(str(k), []).append(i)

    for (k, i), var in result.w.items():
        if var.X > 1e-8:
            arrivals[f"{k},{i}"] = var.X

    return {
        "feasible_solution": True,
        "TMAX": result.tmax.X,
        "routes": routes,
        "crews": crews,
        "visits": visits,
        "arrival_times": arrivals,
    }
