#!/usr/bin/env python3
"""Run the BWO baseline on the friend's small instance or four large instances."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

from tdvrpfca.data import load_small_instance, load_large_instance
from tdvrpfca.bwo import BWOOptimizer


ROOT = Path(__file__).resolve().parent
SMALL = ROOT / "data" / "small"
LARGE = ROOT / "data" / "large"
LARGE_INSTANCES = ("R101", "R201", "RC101", "RC201")
CATEGORY_FILES = ("catheg.txt", "catheg_2.txt")
SPEED_FILES = ("t_dep.txt", "t_dep_2.txt", "t_dep_3.txt")


def run_one(args, name, category=None, speed=None):
    if args.kind == "small":
        inst = load_small_instance(SMALL, travel_time_factor=args.small_travel_factor)
        npop = args.npop if args.npop is not None else 50
        iterations = args.iterations if args.iterations is not None else 10
        procreation = args.procreation if args.procreation is not None else 0.60
        cannibalism = args.cannibalism if args.cannibalism is not None else 0.50
        mutation = args.mutation if args.mutation is not None else 0.10
        return_leg_mode = "source"
        label = f"small_factor{args.small_travel_factor:g}"
    else:
        inst = load_large_instance(
            LARGE, name,
            category_matrix=category or "catheg.txt",
            speed_profile=speed or "t_dep.txt",
            return_leg_mode=args.return_leg_mode,
        )
        npop = args.npop if args.npop is not None else 20
        iterations = args.iterations if args.iterations is not None else 100
        procreation = args.procreation if args.procreation is not None else 0.40
        cannibalism = args.cannibalism if args.cannibalism is not None else 0.50
        mutation = args.mutation if args.mutation is not None else 0.05
        return_leg_mode = args.return_leg_mode
        label = f"{name}_{category or 'catheg.txt'}_{speed or 't_dep.txt'}_{return_leg_mode}"

    runs = []
    for r in range(args.runs):
        seed = None if args.seed is None else args.seed + r
        optimizer = BWOOptimizer(
            inst, npop=npop, procreation_rate=procreation,
            cannibalism_rate=cannibalism, mutation_rate=mutation,
            seed=seed, time_mode=args.time_mode,
            return_leg_mode=return_leg_mode,
        )
        best, history, runtime = optimizer.run(iterations)
        solution = optimizer.decode_chromosome(best.chromosome)
        from tdvrpfca.model import evaluate_solution
        evaluation = evaluate_solution(inst, solution, return_leg_mode=return_leg_mode)
        runs.append({
            "seed": seed,
            "best_T_MAX": best.fitness,
            "runtime_seconds": runtime,
            "feasible": evaluation["feasible"],
            "routes": solution.routes,
            "crew": solution.crew,
            "start_intervals": solution.start_intervals,
            "history": history,
            "violations": evaluation["violations"],
        })

    finite = [r["best_T_MAX"] for r in runs if r["feasible"]]
    return {
        "instance": name,
        "label": label,
        "kind": args.kind,
        "category_matrix": category,
        "speed_profile": speed,
        "time_mode": args.time_mode,
        "return_leg_mode": return_leg_mode,
        "travel_time_factor": inst.travel_time_factor,
        "parameters": {
            "npop": npop, "iterations": iterations,
            "procreation_rate": procreation, "cannibalism_rate": cannibalism,
            "mutation_rate": mutation, "runs": args.runs, "base_seed": args.seed,
        },
        "metadata": inst.metadata,
        "summary": {
            "feasible_runs": len(finite),
            "runs": len(runs),
            "best_T_MAX": min(finite) if finite else None,
            "mean_best_T_MAX": statistics.mean(finite) if finite else None,
            "stdev_best_T_MAX": statistics.stdev(finite) if len(finite) > 1 else 0.0,
            "mean_runtime_seconds": statistics.mean(r["runtime_seconds"] for r in runs),
        },
        "runs": runs,
    }


def parse_args():
    p = argparse.ArgumentParser(description="Run the source-informed TD-VRPFCA BWO baseline.")
    p.add_argument("--kind", choices=["small", "large"], default="small")
    p.add_argument("--instance", choices=LARGE_INSTANCES, default="R101")
    p.add_argument("--category", choices=CATEGORY_FILES, default="catheg.txt")
    p.add_argument("--speed", choices=SPEED_FILES, default="t_dep.txt")
    p.add_argument("--all-large-configs", action="store_true",
                   help="Run all 4 x 2 x 3 = 24 large configurations used by the project.")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--npop", type=int, default=None)
    p.add_argument("--iterations", type=int, default=None)
    p.add_argument("--procreation", type=float, default=None)
    p.add_argument("--cannibalism", type=float, default=None)
    p.add_argument("--mutation", type=float, default=None)
    p.add_argument("--time-mode", choices=["shared", "per_vehicle"], default="shared",
                   help="shared reproduces friend's single interval gene; per_vehicle follows the paper's vehicle-specific interpretation.")
    p.add_argument("--small-travel-factor", type=float, default=1.0,
                   help="1 reproduces friend/public Fitness.py; 60 is a unit-consistency sensitivity setting if distance is km and speed km/h.")
    p.add_argument("--return-leg-mode", choices=["source", "physical"], default="source",
                   help="source reproduces authors' large preprocessing (zero distance to dummy sink); physical is a sensitivity variant.")
    p.add_argument("--output", type=Path, default=ROOT / "results" / "bwo_runs.json")
    return p.parse_args()


def main():
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")

    results = []
    if args.kind == "small":
        results.append(run_one(args, "small"))
    elif args.all_large_configs:
        for instance in LARGE_INSTANCES:
            for category in CATEGORY_FILES:
                for speed in SPEED_FILES:
                    print(f"Running {instance} | {category} | {speed}", flush=True)
                    results.append(run_one(args, instance, category, speed))
    else:
        results.append(run_one(args, args.instance, args.category, args.speed))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")

    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "instance", "label", "category_matrix", "speed_profile",
            "time_mode", "return_leg_mode", "runs", "feasible_runs",
            "best_T_MAX", "mean_best_T_MAX", "stdev_best_T_MAX",
            "mean_runtime_seconds",
        ])
        writer.writeheader()
        for result in results:
            writer.writerow({
                "instance": result["instance"],
                "label": result["label"],
                "category_matrix": result["category_matrix"],
                "speed_profile": result["speed_profile"],
                "time_mode": result["time_mode"],
                "return_leg_mode": result["return_leg_mode"],
                "runs": result["summary"]["runs"],
                "feasible_runs": result["summary"]["feasible_runs"],
                "best_T_MAX": result["summary"]["best_T_MAX"],
                "mean_best_T_MAX": result["summary"]["mean_best_T_MAX"],
                "stdev_best_T_MAX": result["summary"]["stdev_best_T_MAX"],
                "mean_runtime_seconds": result["summary"]["mean_runtime_seconds"],
            })
    for result in results:
        print(json.dumps({"label": result["label"], **result["summary"]}, indent=2))
    print(f"\nJSON: {args.output}\nCSV:  {csv_path}")


if __name__ == "__main__":
    main()
