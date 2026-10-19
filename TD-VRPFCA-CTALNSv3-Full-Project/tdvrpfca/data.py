"""Load only the instances used in the project baseline.

Small-instance crew combinations are completed from Table 3 of the 2025 paper.
The public C.txt is retained unchanged as source evidence; it contains only
five combinations. The small worker-availability vector is the explicit
reconstruction used by the friend's experiment runner.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple

from .model import Instance, Vehicle


class DataError(ValueError):
    pass


def _read_rows(path: Path) -> List[List[str]]:
    if not path.exists():
        raise DataError(f"Required data file is missing: {path}")
    return [line.strip().split() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _load_crew_csv(path: Path) -> Dict[int, Dict[int, float]]:
    if not path.exists():
        raise DataError(f"Required crew table is missing: {path}")
    result = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            result[int(row["crew_id"])] = {
                1: float(row["DP"]),
                2: float(row["Dr"]),
                3: float(row["MFDP"]),
            }
    if set(result) != set(range(1, 9)):
        raise DataError("crew_combinations.csv must contain crew IDs 1..8")
    return result


def load_small_instance(
    root: str | Path,
    *,
    travel_time_factor: float = 1.0,
) -> Instance:
    """Load the ten-customer Allen-style small instance.

    travel_time_factor=1.0 reproduces the friend's/public Fitness.py formula
    distance/speed. If distances are km and speeds are km/hour while all clock
    values/service times are minutes, factor=60 is the unit-consistent variant.
    Do not mix results from the two settings.
    """
    root = Path(root)
    i_rows = _read_rows(root / "I.txt")
    k_rows = _read_rows(root / "K.txt")

    demand = {int(r[0]): float(r[1]) for r in i_rows[1:]}
    nodes = sorted(demand)
    customers = [n for n in nodes if n not in (0, 11)]
    vehicles = {
        int(r[0]): Vehicle(int(r[0]), float(r[1]), float(r[2]))
        for r in k_rows[1:]
    }
    crew = _load_crew_csv(root / "crew_combinations.csv")

    availability_path = root / "worker_availability.json"
    if availability_path.exists():
        raw = json.loads(availability_path.read_text(encoding="utf-8"))
        worker_availability = {int(k): float(v) for k, v in raw.items()}
    else:
        # This is the explicit assumption used by the friend's small runner.
        worker_availability = {1: 4.0, 2: 2.0, 3: 2.0}

    distance = {}
    for line in (root / "Distances.txt").read_text(encoding="utf-8").splitlines():
        match = re.match(r"\((\d+),(\d+)\):\s*([-+0-9.eE]+)", line.strip().rstrip(","))
        if match:
            i, j, value = int(match.group(1)), int(match.group(2)), float(match.group(3))
            distance[(i, j)] = value
    if not distance:
        raise DataError("No distances could be parsed from Distances.txt")

    v_rows = _read_rows(root / "v.txt")
    intervals = [int(x) for x in v_rows[0][2:]]
    speed = {}
    for r in v_rows[1:]:
        i, j = int(r[0]), int(r[1])
        for l, value in zip(intervals, r[2:]):
            speed[(i, j, l)] = float(value)

    # The source matrices represent the physical depot at 0 and the dummy
    # return node at 11. Return speeds are adapted from 0->i, as in the friend's
    # loader and supported by equal source distances to the physical depot.
    for i in customers:
        for l in intervals:
            if (i, 11, l) not in speed and (0, i, l) in speed:
                speed[(i, 11, l)] = speed[(0, i, l)]

    t_rows = _read_rows(root / "t.txt")
    service = {}
    for r in t_rows[1:]:
        i, d = int(r[0]), int(r[1])
        for l, value in zip(intervals, r[2:]):
            service[(i, d, l)] = float(value)

    lower = {l: 60.0 * (l - 1) for l in intervals}
    upper = {l: 60.0 * l for l in intervals}
    return Instance(
        name="small",
        customers=customers,
        nodes=nodes,
        depot_start=0,
        depot_end=11,
        vehicles=vehicles,
        crew=crew,
        worker_availability=worker_availability,
        demand=demand,
        distance=distance,
        speed=speed,
        service=service,
        lower=lower,
        upper=upper,
        intervals=intervals,
        travel_time_factor=travel_time_factor,
        metadata={
            "source": "Original public repository data + paper Table 3",
            "customers": len(customers),
            "vehicle_count": len(vehicles),
            "crew_combinations": 8,
            "original_C_txt_rows": 5,
            "crew_completion": "paper Table 3, in friend repository worker order DP, Dr, MFDP",
            "worker_availability": worker_availability,
            "worker_availability_source": "explicit friend-runner reconstruction; not present in original small data",
            "travel_time_factor": travel_time_factor,
            "time_unit_warning": "factor 1 preserves friend/public source behavior; factor 60 is an alternative if distance is km, speed km/h and clock/service units are minutes",
        },
    )


def _read_solomon(path: Path):
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    start = next((i + 1 for i, line in enumerate(lines) if line.upper().startswith("CUSTNO")), None)
    if start is None:
        raise DataError(f"Cannot find CUSTNO header in {path}")
    rows = []
    for line in lines[start:]:
        p = line.split()
        if len(p) < 7:
            continue
        try:
            rows.append((int(p[0]), *[float(x) for x in p[1:7]]))
        except ValueError:
            continue
    if not rows:
        raise DataError(f"No data rows found in {path}")
    return rows


def _read_category_matrix(path: Path):
    rows = _read_rows(path)
    header = [int(x) for x in rows[0]]
    data = {}
    for row in rows[1:]:
        i = int(row[0])
        for j, val in zip(header, row[1:]):
            data[(i, j)] = int(float(val))
    return data


def _read_speed_profile(path: Path):
    rows = _read_rows(path)
    intervals = [int(x) for x in rows[0]]
    values = {}
    for row in rows[1:]:
        category = int(float(row[0]))
        for l, value in zip(intervals, row[1:]):
            values[(category, l)] = float(value)
    return intervals, values


def load_large_instance(
    root: str | Path,
    instance_name: str,
    *,
    category_matrix: str = "catheg.txt",
    speed_profile: str = "t_dep.txt",
    crew_file: str = "D.txt",
    return_leg_mode: str = "source",
) -> Instance:
    """Load one of the four large instances used in the friend's experiments.

    `return_leg_mode="source"` reproduces the public authors' TS preprocessing:
    arcs involving dummy node 101 have distance zero. "physical" is a clearly
    labelled alternative that returns to the physical depot and is useful for
    checking the effect of that source convention.
    """
    if instance_name not in {"R101", "R201", "RC101", "RC201"}:
        raise DataError(
            f"Project scope includes R101, R201, RC101 and RC201; got {instance_name!r}"
        )
    if return_leg_mode not in {"source", "physical"}:
        raise ValueError("return_leg_mode must be 'source' or 'physical'")

    root = Path(root)
    rows = _read_solomon(root / f"{instance_name}.txt")
    ids = [r[0] for r in rows]
    if 0 not in ids:
        raise DataError("Solomon depot node 0 is missing")

    depot_start, depot_end = 0, 101
    customers = [i for i in ids if i != depot_start]
    nodes = ids + [depot_end]
    coords = {r[0]: (r[1], r[2]) for r in rows}
    demand = {r[0]: r[3] for r in rows}
    demand[depot_end] = 0.0

    capacity = {"R101": 200.0, "R201": 1000.0, "RC101": 1000.0, "RC201": 1000.0}[instance_name]
    vehicles = {k: Vehicle(k=k, capacity=capacity, max_crew=5.0) for k in range(1, 26)}

    crew_rows = _read_rows(root / crew_file)
    crew = {}
    for row in crew_rows[1:]:
        if len(row) >= 4:
            d = int(row[0])
            crew[d] = {1: float(row[1]), 2: float(row[2]), 3: float(row[3])}
    if set(crew) != set(range(1, 9)):
        raise DataError(f"{crew_file} must define crew combinations 1..8")

    categories = _read_category_matrix(root / category_matrix)
    intervals, profile = _read_speed_profile(root / speed_profile)

    distance = {}
    for i in nodes:
        for j in nodes:
            if i == j:
                continue
            if i == depot_end or j == depot_end:
                if return_leg_mode == "source":
                    distance[(i, j)] = 0.0
                elif j == depot_end and i in coords:
                    distance[(i, j)] = math.hypot(
                        coords[i][0] - coords[depot_start][0],
                        coords[i][1] - coords[depot_start][1],
                    )
                else:
                    distance[(i, j)] = 0.0
            else:
                distance[(i, j)] = math.hypot(
                    coords[i][0] - coords[j][0],
                    coords[i][1] - coords[j][1],
                )

    speed = {}
    fallback_speed = 0.3
    for i in nodes:
        for j in nodes:
            if i == j:
                continue
            category = categories.get((i, j))
            for l in intervals:
                val = profile.get((category, l)) if category is not None else None
                speed[(i, j, l)] = val if val is not None and val > 0 else fallback_speed

    # The authors' large-instance TS preprocessing uses 480-minute intervals.
    lower = {l: (l - 1) * 480.0 for l in intervals}
    upper = {l: l * 480.0 for l in intervals}

    service = {}
    for row in rows:
        node, service_time = row[0], row[6]
        for d in crew:
            for l in intervals:
                service[(node, d, l)] = service_time
    for d in crew:
        for l in intervals:
            service[(depot_start, d, l)] = 0.0
            service[(depot_end, d, l)] = 0.0

    return Instance(
        name=instance_name,
        customers=customers,
        nodes=nodes,
        depot_start=depot_start,
        depot_end=depot_end,
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
        travel_time_factor=1.0,
        metadata={
            "source": "Original public repository Solomon/Balseiro data + author's Tabu Search preprocessing",
            "source_instance": instance_name,
            "category_matrix": category_matrix,
            "speed_profile": speed_profile,
            "vehicles": 25,
            "capacity": capacity,
            "crew_combinations": 8,
            "worker_availability": {"DP": 50, "Dr": 20, "MFDP": 20},
            "service_time": "Solomon SERVICETIME replicated across crew combinations and intervals",
            "missing_speed_fallback": fallback_speed,
            "return_leg_mode": return_leg_mode,
            "time_windows": "Not enforced by the friend's BWO evaluator / public authors' TS preprocessing",
        },
    )
