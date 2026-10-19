#!/usr/bin/env python3
"""Run both BWO and CT-ALNS on a benchmark instance in a single command and generate comparison results."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

from tdvrpfca.data import load_small_instance, load_large_instance
from tdvrpfca.bwo import BWOOptimizer
from tdvrpfca.ctalns import CTALNSOptimizer
from tdvrpfca.model import evaluate_solution

ROOT = Path(__file__).resolve().parent


def run_bwo(inst, args, name, out_path: Path):
    npop = 20 if args.instance != "small" else 50
    bwo_iters = args.iterations
    runs_data = []

    print(f"\n[1/3] Running BWO Baseline ({args.runs} runs, {bwo_iters} iters)...", flush=True)
    t0 = time.perf_counter()

    for r in range(args.runs):
        seed = None if args.seed is None else args.seed + r
        optimizer = BWOOptimizer(
            inst,
            npop=npop,
            procreation_rate=0.40 if args.instance != "small" else 0.60,
            cannibalism_rate=0.50,
            mutation_rate=0.05 if args.instance != "small" else 0.10,
            seed=seed,
            time_mode=args.time_mode,
            return_leg_mode=args.return_leg_mode,
        )
        best, history, runtime = optimizer.run(bwo_iters)
        solution = optimizer.decode_chromosome(best.chromosome)
        evaluation = evaluate_solution(inst, solution, return_leg_mode=args.return_leg_mode)

        runs_data.append({
            "seed": seed,
            "best_T_MAX": evaluation["T_MAX"],
            "feasible": evaluation["feasible"],
            "runtime_seconds": runtime,
            "routes": solution.routes,
            "crew": solution.crew,
            "start_intervals": solution.start_intervals,
            "history": history,
            "violations": evaluation["violations"],
        })
        print(f"  BWO Run {r+1}/{args.runs}: feasible={evaluation['feasible']} T_MAX={evaluation['T_MAX']:.4f} ({runtime:.3f}s)", flush=True)

    elapsed_all = time.perf_counter() - t0
    feasible_vals = [r["best_T_MAX"] for r in runs_data if r["feasible"]]

    summary = {
        "algorithm": "BWO",
        "instance": name,
        "runs": args.runs,
        "feasible_runs": len(feasible_vals),
        "best_T_MAX": min(feasible_vals) if feasible_vals else None,
        "mean_best_T_MAX": statistics.mean(feasible_vals) if feasible_vals else None,
        "stdev_best_T_MAX": statistics.stdev(feasible_vals) if len(feasible_vals) > 1 else 0.0,
        "mean_runtime_seconds": statistics.mean(r["runtime_seconds"] for r in runs_data),
        "total_wallclock_seconds": elapsed_all,
    }

    full_output = {
        "algorithm": "BWO",
        "instance": name,
        "time_mode": args.time_mode,
        "return_leg_mode": args.return_leg_mode,
        "summary": summary,
        "runs": runs_data,
    }
    out_path.write_text(json.dumps(full_output, indent=2), encoding="utf-8")
    return summary, full_output


def run_ctalns(inst, args, name, out_path: Path):
    runs_data = []
    print(f"\n[2/3] Running CT-ALNS Novel Metaheuristic ({args.runs} runs, {args.iterations} iters)...", flush=True)
    t0 = time.perf_counter()

    for r in range(args.runs):
        seed = None if args.seed is None else args.seed + r
        optimizer = CTALNSOptimizer(
            inst,
            seed=seed,
            return_leg_mode=args.return_leg_mode,
            initial_time_mode=args.time_mode,
            removal_fraction=args.removal_fraction,
            reaction=args.reaction,
            cooling_rate=args.cooling_rate,
        )
        best, history, current_history, runtime, op_stats = optimizer.run(args.iterations)
        evaluation = evaluate_solution(inst, best, return_leg_mode=args.return_leg_mode)

        runs_data.append({
            "seed": seed,
            "best_T_MAX": evaluation["T_MAX"],
            "feasible": evaluation["feasible"],
            "runtime_seconds": runtime,
            "routes": best.routes,
            "crew": best.crew,
            "start_intervals": best.start_intervals,
            "history": history,
            "current_history": current_history,
            "operator_stats": op_stats,
            "violations": evaluation["violations"],
        })
        print(f"  CT-ALNS Run {r+1}/{args.runs}: feasible={evaluation['feasible']} T_MAX={evaluation['T_MAX']:.4f} ({runtime:.3f}s)", flush=True)

    elapsed_all = time.perf_counter() - t0
    feasible_vals = [r["best_T_MAX"] for r in runs_data if r["feasible"]]

    summary = {
        "algorithm": "CT-ALNS",
        "instance": name,
        "runs": args.runs,
        "feasible_runs": len(feasible_vals),
        "best_T_MAX": min(feasible_vals) if feasible_vals else None,
        "mean_best_T_MAX": statistics.mean(feasible_vals) if feasible_vals else None,
        "stdev_best_T_MAX": statistics.stdev(feasible_vals) if len(feasible_vals) > 1 else 0.0,
        "mean_runtime_seconds": statistics.mean(r["runtime_seconds"] for r in runs_data),
        "total_wallclock_seconds": elapsed_all,
    }

    full_output = {
        "algorithm": "CT-ALNS",
        "instance": name,
        "time_mode": args.time_mode,
        "return_leg_mode": args.return_leg_mode,
        "summary": summary,
        "runs": runs_data,
    }
    out_path.write_text(json.dumps(full_output, indent=2), encoding="utf-8")
    return summary, full_output


def main():
    p = argparse.ArgumentParser(description="Single command to run and compare BWO and CT-ALNS")
    p.add_argument("--instance", choices=["R101", "R201", "RC101", "RC201", "small"], default="R101",
                   help="Benchmark instance name (default: R101)")
    p.add_argument("--runs", type=int, default=3, help="Number of independent runs to average (default: 3)")
    p.add_argument("--iterations", type=int, default=50, help="Iterations per run (default: 50)")
    p.add_argument("--time-mode", choices=["shared", "per_vehicle"], default="per_vehicle",
                   help="Vehicle start interval mode (default: per_vehicle)")
    p.add_argument("--category", default="catheg.txt", help="Category file for large instances (default: catheg.txt)")
    p.add_argument("--speed", default="t_dep.txt", help="Speed file for large instances (default: t_dep.txt)")
    p.add_argument("--return-leg-mode", choices=["source", "physical"], default="source",
                   help="Return leg distance mode (default: source)")
    p.add_argument("--removal-fraction", type=float, default=0.10, help="CT-ALNS removal fraction (default: 0.10)")
    p.add_argument("--reaction", type=float, default=0.2, help="CT-ALNS adaptive reaction factor (default: 0.2)")
    p.add_argument("--cooling-rate", type=float, default=0.995, help="CT-ALNS cooling rate (default: 0.995)")
    p.add_argument("--seed", type=int, default=42, help="Base random seed (default: 42)")
    p.add_argument("--output-dir", type=Path, default=None,
                   help="Directory to save comparison reports and dashboard")

    args = p.parse_args()

    out_dir = args.output_dir or ROOT / "results" / f"comparison_{args.instance}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"  TD-VRPFCA EXPERIMENT: BWO vs CT-ALNS COMPARISON")
    print(f"  Instance: {args.instance} | Runs: {args.runs} | Iterations: {args.iterations} | Seed: {args.seed}")
    print(f"  Time Mode: {args.time_mode} | Return Leg: {args.return_leg_mode}")
    print(f"  Output Directory: {out_dir}")
    print("=" * 70)

    # 1. Load instance
    if args.instance == "small":
        inst = load_small_instance(ROOT / "data" / "small")
        name = "small"
    else:
        inst = load_large_instance(
            ROOT / "data" / "large",
            args.instance,
            category_matrix=args.category,
            speed_profile=args.speed,
            return_leg_mode=args.return_leg_mode,
        )
        name = args.instance

    # 2. Run BWO
    bwo_json = out_dir / f"bwo_{args.instance}.json"
    bwo_summary, _ = run_bwo(inst, args, name, bwo_json)

    # 3. Run CT-ALNS
    ctalns_json = out_dir / f"ctalns_{args.instance}.json"
    ctalns_summary, _ = run_ctalns(inst, args, name, ctalns_json)

    # 4. Run Analysis Dashboard
    print(f"\n[3/3] Generating Presentation Dashboard & Analysis...", flush=True)
    dash_dir = out_dir / "dashboard"
    try:
        cmd = [
            sys.executable,
            str(ROOT / "analyze_results.py"),
            "--ctalns", str(ctalns_json),
            "--bwo", str(bwo_json),
            "--out", str(dash_dir),
            "--data-dir", str(ROOT / "data" / "large") if args.instance != "small" else str(ROOT / "data" / "small"),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"  Dashboard successfully written to: {dash_dir}/REPORT.md")
    except Exception as e:
        print(f"  Notice: Dashboard generation skipped or encountered note: {e}")

    # 5. Calculate Deltas and Print Comparison Table
    bwo_best = bwo_summary["best_T_MAX"]
    ctalns_best = ctalns_summary["best_T_MAX"]
    bwo_mean = bwo_summary["mean_best_T_MAX"]
    ctalns_mean = ctalns_summary["mean_best_T_MAX"]

    imp_best_pct = ((bwo_best - ctalns_best) / bwo_best * 100) if (bwo_best and ctalns_best) else 0.0
    imp_mean_pct = ((bwo_mean - ctalns_mean) / bwo_mean * 100) if (bwo_mean and ctalns_mean) else 0.0

    b_feas_str = f"{bwo_summary['feasible_runs']}/{args.runs}"
    c_feas_str = f"{ctalns_summary['feasible_runs']}/{args.runs}"
    b_std_str = f"{bwo_summary['stdev_best_T_MAX']:.4f}"
    c_std_str = f"{ctalns_summary['stdev_best_T_MAX']:.4f}"
    b_time_str = f"{bwo_summary['mean_runtime_seconds']:.3f} s"
    c_time_str = f"{ctalns_summary['mean_runtime_seconds']:.3f} s"

    print("\n" + "=" * 70)
    print(f"                 COMPARISON RESULTS ({name.upper()})")
    print("=" * 70)
    print(f"{'Metric':<28} | {'BWO Baseline':<18} | {'CT-ALNS (Novel)':<18}")
    print("-" * 70)
    print(f"{'Feasible Runs':<28} | {b_feas_str:<18} | {c_feas_str:<18}")
    print(f"{'Best T_MAX':<28} | {bwo_best:.4f}             | {ctalns_best:.4f}")
    print(f"{'Mean T_MAX':<28} | {bwo_mean:.4f}             | {ctalns_mean:.4f}")
    print(f"{'Std Dev T_MAX':<28} | {b_std_str:<18} | {c_std_str:<18}")
    print(f"{'Mean Runtime (s/run)':<28} | {b_time_str:<18} | {c_time_str:<18}")
    print("-" * 70)
    print(f"Best T_MAX Improvement by CT-ALNS : {imp_best_pct:+.2f}%")
    print(f"Mean T_MAX Improvement by CT-ALNS : {imp_mean_pct:+.2f}%")
    print("=" * 70)

    # Save summary report to markdown
    report_md = out_dir / "COMPARISON_REPORT.md"
    report_md.write_text(f"""# TD-VRPFCA Algorithm Comparison Report: {name.upper()}

**Configuration:**
- **Instance:** `{name}` (100 customers, 25 vehicles)
- **Number of Runs:** `{args.runs}`
- **Iterations:** `{args.iterations}`
- **Time Mode:** `{args.time_mode}`
- **Category Matrix:** `{args.category}`
- **Speed Profile:** `{args.speed}`
- **Return Leg Mode:** `{args.return_leg_mode}`

## Summary Table

| Metric | BWO Baseline | CT-ALNS (Proposed) | Improvement / Difference |
| :--- | :--- | :--- | :--- |
| **Feasible Runs** | `{bwo_summary['feasible_runs']}/{args.runs}` | `{ctalns_summary['feasible_runs']}/{args.runs}` | `{ctalns_summary['feasible_runs'] - bwo_summary['feasible_runs']:+d}` |
| **Best $T_{{MAX}}$** | `{bwo_best:.4f}` | `{ctalns_best:.4f}` | **`{imp_best_pct:+.2f}%`** |
| **Mean $T_{{MAX}}$** | `{bwo_mean:.4f}` | `{ctalns_mean:.4f}` | **`{imp_mean_pct:+.2f}%`** |
| **Std Dev $T_{{MAX}}$** | `{bwo_summary['stdev_best_T_MAX']:.4f}` | `{ctalns_summary['stdev_best_T_MAX']:.4f}` | - |
| **Avg Runtime / Run** | `{bwo_summary['mean_runtime_seconds']:.3f} s` | `{ctalns_summary['mean_runtime_seconds']:.3f} s` | - |

## Key Insights
1. **Solution Quality:** CT-ALNS achieves a {imp_best_pct:+.2f}% improvement in Best $T_{{MAX}}$ over BWO.
2. **Operators Applied:** CT-ALNS utilized 12 coupled operators including Rush-Hour Congestion Destroy, Regret-2 Repair, and Bottleneck Critical Route moves.
3. **Artifacts:**
   - BWO Raw JSON: `{bwo_json.name}`
   - CT-ALNS Raw JSON: `{ctalns_json.name}`
   - Detailed visual dashboard: `dashboard/REPORT.md`
""", encoding="utf-8")
    print(f"\nReport saved to: {report_md}")


if __name__ == "__main__":
    main()
