from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import re
from typing import Dict, List, Tuple


class SourceDataError(ValueError):
    """Raised when the source data are insufficient for the published MILP."""


@dataclass(frozen=True)
class Vehicle:
    k: int
    capacity: float
    max_crew: float


@dataclass
class Instance:
    customers: List[int]
    nodes: List[int]
    depot_start: int
    depot_end: int
    vehicles: Dict[int, Vehicle]
    crew: Dict[int, Dict[int, float]]
    worker_availability: Dict[int, float]
    demand: Dict[int, float]
    distance: Dict[Tuple[int, int], float]
    speed: Dict[Tuple[int, int, int], float]
    service: Dict[Tuple[int, int, int], float]
    lower: Dict[int, float]
    upper: Dict[int, float]
    intervals: List[int]
    metadata: Dict[str, object] = field(default_factory=dict)


def _read_tsv(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return [line.strip().split() for line in f if line.strip()]


def _load_worker_availability(root: Path) -> Dict[int, float]:
    """
    Read V^c only when an explicitly named worker-availability file exists.

    The authors' public Small Intance directory does NOT contain V.txt;
    its files are C.txt, Distances.txt, I.txt, K.txt, coord.csv, t.txt and v.txt.
    Therefore an arbitrary V.txt in a user's Objective-1 directory must not be
    interpreted as worker availability.

    Accepted filenames:
      worker_availability.json
      worker_availability.txt
      V_worker.txt

    TXT format:
      1 2
      2 2
      3 0

    JSON format:
      {"1": 2, "2": 2, "3": 0}
    """
    for path in (root / "worker_availability.json",):
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            try:
                values = {int(k): float(v) for k, v in raw.items()}
            except (ValueError, TypeError) as exc:
                raise SourceDataError(
                    f"Invalid worker_availability JSON in {path}: {exc}"
                ) from exc
            return values

    for path in (root / "worker_availability.txt", root / "V_worker.txt"):
        if path.exists():
            rows = _read_tsv(path)
            values = {}
            for row_no, r in enumerate(rows, start=1):
                if len(r) < 2:
                    raise SourceDataError(
                        f"Invalid worker availability row {row_no} in {path}: {r}"
                    )
                try:
                    values[int(r[0])] = float(r[1])
                except ValueError as exc:
                    raise SourceDataError(
                        f"Invalid worker availability row {row_no} in {path}: {r}. "
                        "Expected: worker_type availability"
                    ) from exc
            return values

    return {}


def load_small_instance(root: str | Path) -> Instance:
    """
    Load the published small-instance data.

    The paper's Table 3 defines eight crew combinations. The public
    repository C.txt currently contains only five rows and therefore is
    recorded as a repository discrepancy; the MILP uses the paper's
    eight-combination table as the mathematical source.

    V^c is NOT fabricated. If the dataset/configuration does not contain it,
    build_paper_milp() will stop with a source-data diagnostic because
    constraint (13) cannot be instantiated exactly.
    """
    root = Path(root)

    I = _read_tsv(root / "I.txt")
    K_rows = _read_tsv(root / "K.txt")

    demand = {int(r[0]): float(r[1]) for r in I[1:]}
    nodes = sorted(demand)
    customers = [i for i in nodes if i not in (0, 11)]
    vehicles = {
        int(r[0]): Vehicle(int(r[0]), float(r[1]), float(r[2]))
        for r in K_rows[1:]
    }

    # The repository stores crew rows in worker-type order:
    #   type 1 = DP, type 2 = Dr, type 3 = MFDP.
    # This is confirmed by the authors' calculos_BWO.py, which transposes
    # the C/D matrix before using it. The paper's Table 3 labels the first
    # two columns as Dr and DP, so the internal representation follows the
    # repository order to remain compatible with the authors' code.
    crew = {}
    c_path = root / "C.txt"
    repository_crew_rows = []
    if c_path.exists():
        rows = _read_tsv(c_path)
        repository_crew_rows = rows[1:]

    # The public C.txt is truncated to five rows. The paper's Table 3/D.txt
    # defines all eight combinations. The first five repository rows are
    # retained as evidence, and the complete eight-row paper table is used
    # in repository worker-type order (DP, Dr, MFDP).
    crew = {
        1: {1: 1, 2: 1, 3: 0},
        2: {1: 2, 2: 1, 3: 0},
        3: {1: 3, 2: 1, 3: 0},
        4: {1: 4, 2: 1, 3: 0},
        5: {1: 0, 2: 0, 3: 1},
        6: {1: 1, 2: 0, 3: 1},
        7: {1: 2, 2: 0, 3: 1},
        8: {1: 3, 2: 0, 3: 1},
    }

    worker_availability = _load_worker_availability(root)

    distance = {}
    distance_path = root / "Distances.txt"
    if not distance_path.exists():
        raise SourceDataError(f"Missing required source file: {distance_path}")
    for line in distance_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\((\d+),(\d+)\):\s*([-+0-9.eE]+)", line.strip().rstrip(","))
        if m:
            i, j, val = int(m.group(1)), int(m.group(2)), float(m.group(3))
            distance[(i, j)] = val

    v_rows = _read_tsv(root / "v.txt")
    intervals = list(range(1, len(v_rows[0]) - 1))
    speed = {}
    for r in v_rows[1:]:
        i, j = int(r[0]), int(r[1])
        for idx, l in enumerate(intervals):
            speed[(i, j, l)] = float(r[2 + idx])

    # The public small-instance speed file represents the physical depot as
    # node 0 and the dummy return depot as node 11.  It provides 0->i speeds
    # and i->j customer speeds, but deliberately does not repeat the return
    # arcs i->11.  Distances.txt confirms that the dummy return depot is at
    # the same physical location as the start depot: distance(i,11) equals
    # distance(0,i).  Therefore the non-fabricated source mapping for the
    # return leg is v[i,11,l] := v[0,i,l].  This is a representation adapter,
    # not a guessed speed value.
    for i in [n for n in nodes if n not in (0, 11)]:
        for l in intervals:
            if (i, 11, l) not in speed:
                key = (0, i, l)
                if key in speed and speed[key] > 0:
                    speed[(i, 11, l)] = speed[key]

    t_rows = _read_tsv(root / "t.txt")
    service = {}
    for r in t_rows[1:]:
        i, d = int(r[0]), int(r[1])
        for idx, l in enumerate(intervals):
            service[(i, d, l)] = float(r[2 + idx])

    # The small-instance source uses ten 60-minute intervals.
    lower = {l: 60.0 * (l - 1) for l in intervals}
    upper = {l: 60.0 * l for l in intervals}

    return Instance(
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
        metadata={
            "source": "Ilabaca et al. (2025), Table 3 + public repository data",
            "paper_crew_combinations": 8,
            "repository_C_rows": len(repository_crew_rows),
            "crew_data_discrepancy": len(repository_crew_rows) != 8,
            "repository_worker_type_order": "DP, Dr, MFDP",
            "worker_availability_present": bool(worker_availability),
            "return_arc_speed_adapter": "v[i,11,l] mapped from v[0,i,l] using same physical depot representation",
        },
    )
