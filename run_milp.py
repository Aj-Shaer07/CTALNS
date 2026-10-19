#!/usr/bin/env python3
"""Run exact MILP on the TD-VRPFCA small instance."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gurobipy as gp

from tdvrpfca.data import load_small_instance
from tdvrpfca.milp import build_corrected_milp


def main():
    parser = argparse.ArgumentParser(description="Run exact MILP for TD-VRPFCA small instance")
    parser.add_argument("--time-limit", type=float, default=300, help="Gurobi solver time limit (seconds)")
    parser.add_argument("--mode", choices=["corrected", "paper", "both"], default="both",
                        help="Solve corrected model, original paper model, or both side-by-side")
    args = parser.parse_args()

    data_dir = Path(__file__).resolve().parent / "data" / "small"
    print(f"Loading small instance from {data_dir}...")
    inst = load_small_instance(data_dir)

    modes_to_run = ["paper", "corrected"] if args.mode == "both" else [args.mode]

    for mode in modes_to_run:
        fix_bugs = (mode == "corrected")
        label = "Corrected Multi-Vehicle MILP" if fix_bugs else "Original Paper MILP"
        print(f"\n==========================================")
        print(f"  Running {label}")
        print(f"==========================================")

        try:
            res = build_corrected_milp(inst, time_limit=args.time_limit, verbose=True, fix_all_bugs=fix_bugs)
            res.model.optimize()

            if res.model.Status in [gp.GRB.OPTIMAL, gp.GRB.TIME_LIMIT, gp.GRB.SUBOPTIMAL] and res.model.SolCount > 0:
                print(f"\n>> {label} Objective (T_MAX): {res.model.ObjVal:.4f}")
                print(f">> Runtime: {res.model.Runtime:.2f} s | Gap: {res.model.MIPGap * 100:.2f}%")
            else:
                print(f"\n>> {label} Status: {res.model.Status}")
        except gp.GurobiError as e:
            print(f">> Gurobi error: {e}")


if __name__ == "__main__":
    main()
