from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Dict

from .loader import Instance, Vehicle, SourceDataError


def _solomon(path: Path):
    """Read the repository's Solomon/Balseiro-style file."""
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    start = None
    for idx, ln in enumerate(lines):
        if ln.upper().startswith("CUSTNO"):
            start = idx + 1
            break
    if start is None:
        raise SourceDataError(f"Cannot find CUSTNO header in {path}")

    rows = []
    for ln in lines[start:]:
        parts = ln.split()
        if len(parts) < 7:
            continue
        try:
            rows.append(
                (
                    int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]),
                    float(parts[4]), float(parts[5]), float(parts[6]),
                )
            )
        except ValueError:
            continue
    if not rows:
        raise SourceDataError(f"No customer rows found in {path}")
    return rows


def _category_matrix(path: Path):
    rows = [ln.split() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not rows:
        raise SourceDataError(f"Empty category matrix: {path}")
    header = [int(x) for x in rows[0]]
    data = {}
    for r in rows[1:]:
        if len(r) < len(header) + 1:
            continue
        try:
            i = int(r[0])
        except ValueError:
            continue
        for j, value in zip(header, r[1:]):
            data[(i, j)] = int(float(value))
    return data


def _speed_profile(path: Path):
    rows = [ln.split() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(rows) < 2:
        raise SourceDataError(f"Invalid speed profile: {path}")
    intervals = [int(x) for x in rows[0]]
    values = {}
    for r in rows[1:]:
        if len(r) < len(intervals) + 1:
            continue
        category = int(float(r[0]))
        for l, value in zip(intervals, r[1:]):
            values[(category, l)] = float(value)
    return intervals, values


def _capacity_for(instance_name: str) -> float:
    """Vehicle capacities used by the authors' large-instance preprocessing."""
    capacities = {
        "RC101": 1000.0,
        "RC201": 1000.0,
        "R201": 1000.0,
        "C101": 200.0,
        "R101": 200.0,
        "C201": 700.0,
    }
    try:
        return capacities[instance_name]
    except KeyError as exc:
        raise SourceDataError(
            f"No repository capacity rule is available for large instance {instance_name}"
        ) from exc


def load_large_instance(
    root: str | Path,
    instance_name: str = "C101",
    category_matrix: str = "catheg.txt",
    speed_profile: str = "t_dep.txt",
    crew_file: str = "D.txt",
) -> Instance:
    """Load a large benchmark using the authors' published preprocessing.

    The paper does not report MILP results for the 100-node benchmarks; it uses
    them for BWO/GA/TS. This adapter nevertheless makes the common TD-VRPFCA
    MILP executable on the same benchmark so the project's scalability test is
    empirical rather than hard-coded.

    Source-code-backed choices:
      * 25 vehicles.
      * max cabin crew = 5.
      * C101/R101 capacity=200; C201=700; RC101/RC201/R201=1000.
      * worker availability = {DP:50, Dr:20, MFDP:20} in the repository's
        worker-type order 1,2,3.
      * service time = Solomon SERVICETIME, constant across crew/intervals,
        exactly as used by the authors' large-instance TS code.
      * category matrix + t_dep profile determine time-dependent arc speed.
      * missing depot/dummy-sink category lookups fall back to speed 0.3,
        exactly as the authors' TS preprocessing does.
    """
    root = Path(root)
    source = root / f"{instance_name}.txt"
    if not source.exists():
        raise SourceDataError(f"Large benchmark file not found: {source}")

    rows = _solomon(source)
    ids = [r[0] for r in rows]
    if 0 not in ids:
        raise SourceDataError(f"Solomon depot 0 not found in {source}")

    # 0 is the physical start depot. 101 is the dummy return node used by the
    # authors' large-instance code.
    o = 0
    s = 101
    customers = [i for i in ids if i != o]
    nodes = ids + [s]

    coords = {r[0]: (r[1], r[2]) for r in rows}
    coords[s] = coords[o]
    demand = {r[0]: r[3] for r in rows}
    demand[s] = 0.0

    capacity = _capacity_for(instance_name)
    vehicles = {
        k: Vehicle(k=k, capacity=capacity, max_crew=5.0)
        for k in range(1, 26)
    }

    crew_rows = [ln.split() for ln in (root / crew_file).read_text(encoding="utf-8").splitlines() if ln.strip()]
    crew = {}
    for r in crew_rows[1:]:
        if len(r) >= 4:
            d = int(r[0])
            # Repository worker order: DP, Dr, MFDP.
            crew[d] = {1: float(r[1]), 2: float(r[2]), 3: float(r[3])}
    if set(crew) != set(range(1, 9)):
        raise SourceDataError(f"{crew_file} must define crew combinations 1..8")

    cat = _category_matrix(root / category_matrix)
    intervals, profile = _speed_profile(root / speed_profile)

    distance = {}
    for i in nodes:
        for j in nodes:
            if i == j:
                continue
            # This follows the authors' large-instance code: depot/dummy-sink
            # distances are set to zero; customer distances are Euclidean.
            if i == s or j == s:
                distance[(i, j)] = 0.0
            else:
                xi, yi = coords[i]
                xj, yj = coords[j]
                distance[(i, j)] = math.hypot(xi - xj, yi - yj)

    speed = {}
    fallback_speed = 0.3
    for i in nodes:
        for j in nodes:
            if i == j:
                continue
            category = cat.get((i, j))
            for l in intervals:
                if category is None or (category, l) not in profile:
                    speed[(i, j, l)] = fallback_speed
                else:
                    value = profile[(category, l)]
                    if value <= 0:
                        speed[(i, j, l)] = fallback_speed
                    else:
                        speed[(i, j, l)] = value

    # Authors' large-instance code uses 480-minute intervals.
    lower = {l: (l - 1) * 480.0 for l in intervals}
    upper = {l: l * 480.0 for l in intervals}

    # Authors' large-instance TS preprocessing uses the Solomon SERVICETIME
    # column for every crew/interval combination. It is not the richer t_id^l
    # service tensor of the small TD-VRPFCA dataset, so this discrepancy is
    # explicitly recorded in metadata.
    service = {}
    for r in rows:
        i = r[0]
        base_service = r[6]
        for d in crew:
            for l in intervals:
                service[(i, d, l)] = base_service
    for d in crew:
        for l in intervals:
            service[(o, d, l)] = 0.0
            service[(s, d, l)] = 0.0

    return Instance(
        customers=customers,
        nodes=nodes,
        depot_start=o,
        depot_end=s,
        vehicles=vehicles,
        crew=crew,
        worker_availability={1: 50.0, 2: 20.0, 3: 20.0},
        demand=demand,
        distance=distance,
        speed=speed,
        service=service,
        lower=lower,
        upper=upper,
        intervals=intervals,
        metadata={
            "format": "Balseiro/Solomon benchmark + authors' TD-VRPFCA preprocessing",
            "source_instance": instance_name,
            "category_matrix": category_matrix,
            "speed_profile": speed_profile,
            "vehicle_count": 25,
            "vehicle_capacity": capacity,
            "worker_availability": {"DP": 50, "Dr": 20, "MFDP": 20},
            "worker_type_order": "DP, Dr, MFDP",
            "service_source": "Solomon SERVICETIME replicated over crew/interval",
            "depot_speed_fallback": fallback_speed,
            "paper_MILP_published_for_large": False,
        },
    )
