from __future__ import annotations

import csv
import json
from pathlib import Path


def write_json(path: str | Path, payload: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_comparison(path: str | Path, rows: list[dict]):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fields = list(rows[0])
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def status_text(status: int, gurobi):
    mapping = {
        gurobi.GRB.OPTIMAL: "OPTIMAL",
        gurobi.GRB.TIME_LIMIT: "TIME_LIMIT",
        gurobi.GRB.INFEASIBLE: "INFEASIBLE",
        gurobi.GRB.UNBOUNDED: "UNBOUNDED",
        gurobi.GRB.INF_OR_UNBD: "INF_OR_UNBD",
    }
    return mapping.get(status, str(status))
