
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List

from .model import Instance, Vehicle


def _tokens(line: str) -> List[str]:
    return [x for x in re.split(r"[\t, ]+", line.strip()) if x]


def load_small_or_case_instance(
    folder: str | Path,
    *,
    depot_start: int = 0,
    depot_return: int | None = None,
    interval_minutes: float = 60.0,
) -> Instance:
    folder = Path(folder)

    demand = _read_I(folder / "I.txt")
    vehicles = _read_K(folder / "K.txt")
    crew_composition = _read_C(folder / "C.txt")
    distance = _read_distances(folder / "Distances.txt")
    service_time, service_intervals = _read_service(folder / "t.txt")
    speed, speed_intervals = _read_speed(folder / "v.txt")

    if service_intervals != speed_intervals:
        raise ValueError(
            f"Service and speed files use different intervals: "
            f"{service_intervals} vs {speed_intervals}"
        )

    intervals = sorted(service_intervals)
    lower = {l: (l - 1) * interval_minutes / 60.0 for l in intervals}
    upper = {l: l * interval_minutes / 60.0 for l in intervals}

    # The repository's small-instance I.txt explicitly contains node 0 as
    # the start depot and node 11 as the dummy return depot.
    if depot_return is None:
        depot_return = max(demand)

    customers = sorted(i for i in demand if i not in {depot_start, depot_return})
    nodes = sorted(demand)

    # V^c is not contained in C.txt. It is therefore kept as a loader input
    # rather than invented from the data file.
    worker_limits = {}

    return Instance(
        customers=customers,
        nodes=nodes,
        vehicles=vehicles,
        crew_composition=crew_composition,
        worker_limits=worker_limits,
        demand=demand,
        distance=distance,
        speed=speed,
        service_time=service_time,
        lower=lower,
        upper=upper,
        depot_start=depot_start,
        depot_return=depot_return,
    )


def _read_I(path: Path) -> Dict[int, float]:
    out: Dict[int, float] = {}
    with path.open(encoding="utf-8") as f:
        next(f, None)
        for line in f:
            t = _tokens(line)
            if len(t) >= 2:
                out[int(t[0])] = float(t[1])
    return out


def _read_K(path: Path) -> Dict[int, Vehicle]:
    out: Dict[int, Vehicle] = {}
    with path.open(encoding="utf-8") as f:
        next(f, None)
        for line in f:
            t = _tokens(line)
            if len(t) >= 3:
                k = int(t[0])
                out[k] = Vehicle(k, float(t[1]), int(float(t[2])))
    return out


def _read_C(path: Path) -> Dict[int, Dict[int, int]]:
    out: Dict[int, Dict[int, int]] = {}
    with path.open(encoding="utf-8") as f:
        rows = []
        for line in f:
            t = _tokens(line)
            if t:
                rows.append([int(float(x)) for x in t])

    if not rows:
        return out

    # Header contains worker-type IDs; following rows are:
    # crew_id, worker_type_1_count, ..., worker_type_C_count
    worker_types = rows[0]
    for row in rows[1:]:
        d = row[0]
        out[d] = {
            c: row[c_index + 1]
            for c_index, c in enumerate(worker_types)
            if c_index + 1 < len(row)
        }
    return out


_PAIR_RE = re.compile(r"\((\d+)\s*,\s*(\d+)\)\s*:\s*([-+0-9.eE]+)")


def _read_distances(path: Path) -> Dict[tuple[int, int], float]:
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            m = _PAIR_RE.search(line)
            if m:
                i, j, value = m.groups()
                out[(int(i), int(j))] = float(value.rstrip(","))
    return out


def _read_service(path: Path):
    out = {}
    intervals = []
    with path.open(encoding="utf-8") as f:
        header = _tokens(next(f))
        intervals = [int(x) for x in header[2:]]
        for line in f:
            t = _tokens(line)
            if len(t) < 2 + len(intervals):
                continue
            i, d = int(t[0]), int(t[1])
            for idx, l in enumerate(intervals):
                out[(i, d, l)] = float(t[2 + idx])
    return out, intervals


def _read_speed(path: Path):
    out = {}
    intervals = []
    with path.open(encoding="utf-8") as f:
        header = _tokens(next(f))
        intervals = [int(x) for x in header[2:]]
        for line in f:
            t = _tokens(line)
            if len(t) < 2 + len(intervals):
                continue
            i, j = int(t[0]), int(t[1])
            for idx, l in enumerate(intervals):
                out[(i, j, l)] = float(t[2 + idx])
    return out, intervals
