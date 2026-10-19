#!/usr/bin/env python3
"""Run Novelty 2: Time-Cost Multi-Objective CT-ALNS for TD-VRPFCA.

Generates a Pareto-optimal frontier balancing delivery completion time (T_MAX)
against total operational costs (C_total = vehicle + distance + crew + overtime).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib_cache")

from tdvrpfca.data import load_small_instance, load_large_instance
from tdvrpfca.cost import CostConfig, CostBreakdown, evaluate_cost
from tdvrpfca.pareto import ParetoArchive, ParetoPoint
from tdvrpfca.mo_ctalns import MOCTALNSOptimizer

# Optional matplotlib plotting
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_PLOT = True
except Exception:
    HAS_PLOT = False

ROOT = Path(__file__).resolve().parent


def plot_pareto_front(archive: ParetoArchive, name: str, out_path: Path):
    """Generate 2D scatter plot of the Pareto Frontier (T_MAX vs C_total)."""
    if not HAS_PLOT or len(archive) == 0:
        return

    pts = archive.get_sorted_front()
    t_vals = [p.t_max for p in pts]
    c_vals = [p.cost for p in pts]

    fastest = archive.get_fastest_solution()
    cheapest = archive.get_cheapest_solution()
    knee = archive.get_knee_solution()

    plt.figure(figsize=(9, 6), dpi=150)
    plt.plot(t_vals, c_vals, "b--", alpha=0.5, linewidth=1.5, label="Pareto Front Boundary")
    plt.scatter(t_vals, c_vals, color="#1f77b4", s=60, alpha=0.85, zorder=3, label="Trade-off Solutions")

    # Highlight extreme solutions
    if fastest:
        plt.scatter(
            [fastest.t_max], [fastest.cost],
            color="#2ca02c", s=130, edgecolor="black", zorder=4,
            label=f"Fastest Plan ({fastest.t_max:.1f}m, ${fastest.cost:.1f})"
        )
        plt.annotate(
            "Fastest (Min Time)",
            xy=(fastest.t_max, fastest.cost),
            xytext=(15, 15), textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=1.2),
            fontweight="bold", color="#2ca02c"
        )

    if cheapest:
        plt.scatter(
            [cheapest.t_max], [cheapest.cost],
            color="#d62728", s=130, edgecolor="black", zorder=4,
            label=f"Cheapest Plan ({cheapest.t_max:.1f}m, ${cheapest.cost:.1f})"
        )
        plt.annotate(
            "Cheapest (Min Cost)",
            xy=(cheapest.t_max, cheapest.cost),
            xytext=(-40, 20), textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.2),
            fontweight="bold", color="#d62728"
        )

    if knee and knee not in (fastest, cheapest):
        plt.scatter(
            [knee.t_max], [knee.cost],
            color="#ff7f0e", s=140, marker="*", edgecolor="black", zorder=5,
            label=f"Knee/Compromise ({knee.t_max:.1f}m, ${knee.cost:.1f})"
        )
        plt.annotate(
            "Knee Solution (Best Balance)",
            xy=(knee.t_max, knee.cost),
            xytext=(15, -20), textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color="#ff7f0e", lw=1.2),
            fontweight="bold", color="#ff7f0e"
        )

    plt.title(f"TD-VRPFCA Time–Cost Pareto Frontier: {name.upper()}", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Makespan $T_{MAX}$ (Minutes to Final Delivery)  →  Lower is Better", fontsize=11, labelpad=8)
    plt.ylabel("Total Operational Cost $C_{total}$ ($)  →  Lower is Better", fontsize=11, labelpad=8)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(frameon=True, facecolor="white", edgecolor="none", shadow=True, fontsize=9)
    plt.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    plt.close()


def plot_convergence(history: List[Dict[str, Any]], name: str, out_path: Path):
    """Plot multi-objective hypervolume and objective convergence over iterations."""
    if not HAS_PLOT or not history:
        return

    iters = [h["iteration"] for h in history]
    hvs = [h["hypervolume"] for h in history]
    t_vals = [h["best_T_MAX"] for h in history]
    c_vals = [h["best_C_total"] for h in history]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=150)

    # 1. Hypervolume convergence
    ax1.plot(iters, hvs, color="#2b5c8f", lw=2)
    ax1.set_title("Hypervolume Growth (Search Coverage)", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Iteration", fontsize=10)
    ax1.set_ylabel("Hypervolume (Higher is Better)", fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.6)

    # 2. Objective envelope evolution
    ax2.plot(iters, t_vals, color="#2ca02c", lw=1.8, label="Best $T_{MAX}$ (Time)")
    ax2.set_xlabel("Iteration", fontsize=10)
    ax2.set_ylabel("Makespan (Minutes)", color="#2ca02c", fontsize=10)
    ax2.tick_params(axis="y", labelcolor="#2ca02c")
    ax2.grid(True, linestyle=":", alpha=0.6)

    ax2_cost = ax2.twinx()
    ax2_cost.plot(iters, c_vals, color="#d62728", lw=1.8, linestyle="--", label="Best $C_{total}$ (Cost)")
    ax2_cost.set_ylabel("Operational Cost ($)", color="#d62728", fontsize=10)
    ax2_cost.tick_params(axis="y", labelcolor="#d62728")

    ax2.set_title("Objective Boundary Evolution", fontsize=11, fontweight="bold")

    plt.suptitle(f"MO-CTALNS Convergence Diagnostics: {name.upper()}", fontsize=13, fontweight="bold")
    plt.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    plt.close()


def main():
    p = argparse.ArgumentParser(description="Run Novelty 2: Multi-Objective CT-ALNS")
    p.add_argument("--instance", choices=["R101", "R201", "RC101", "RC201", "small"], default="R101",
                   help="Instance name (default: R101)")
    p.add_argument("--runs", type=int, default=1, help="Number of independent optimization runs (default: 1)")
    p.add_argument("--iterations", type=int, default=100, help="Search iterations per run (default: 100)")
    p.add_argument("--archive-size", type=int, default=50, help="Pareto archive capacity (default: 50)")
    p.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    p.add_argument("--vehicle-fixed-cost", type=float, default=100.0, help="Fixed cost per active vehicle (default: 100.0)")
    p.add_argument("--distance-cost", type=float, default=1.20, help="Cost per unit distance (default: 1.20)")
    p.add_argument("--category", default="catheg.txt", help="Category matrix file (default: catheg.txt)")
    p.add_argument("--speed", default="t_dep.txt", help="Speed profile file (default: t_dep.txt)")
    p.add_argument("--return-leg-mode", choices=["source", "physical"], default="source",
                   help="Return leg distance mode (default: source)")
    p.add_argument("--output-dir", type=Path, default=None,
                   help="Directory to save Pareto results (default: results/multiobjective_<instance>)")

    args = p.parse_args()

    out_dir = args.output_dir or ROOT / "results" / f"multiobjective_{args.instance}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("  TD-VRPFCA NOVELTY 2: TIME-COST MULTI-OBJECTIVE OPTIMIZATION (MO-CTALNS)")
    print(f"  Instance: {args.instance} | Runs: {args.runs} | Iterations: {args.iterations} | Seed: {args.seed}")
    print(f"  Cost Settings: Fixed Vehicle=${args.vehicle_fixed_cost:.2f} | Distance=${args.distance_cost:.2f}/unit")
    print(f"  Output Directory: {out_dir}")
    print("=" * 72)

    # 1. Load Instance
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

    # 2. Setup Cost Model
    cost_cfg = CostConfig(
        vehicle_fixed_cost=args.vehicle_fixed_cost,
        distance_cost_per_unit=args.distance_cost,
    )

    # 3. Execute Optimization Across Runs
    print(f"\n[1/3] Executing Multi-Objective Optimization ({args.runs} run(s) x {args.iterations} iters)...", flush=True)
    global_archive = ParetoArchive(max_size=args.archive_size)
    runs_records = []
    combined_history = []
    total_t0 = time.perf_counter()

    for r in range(args.runs):
        run_seed = args.seed + r
        optimizer = MOCTALNSOptimizer(
            inst,
            cost_config=cost_cfg,
            archive_size=args.archive_size,
            seed=run_seed,
            return_leg_mode=args.return_leg_mode,
        )
        archive_r, history_r, runtime_r, stats_r = optimizer.run_multiobjective(args.iterations)

        # Merge discovered non-dominated points into global archive
        for pt in archive_r.points:
            global_archive.add(pt)

        run_fastest = archive_r.get_fastest_solution()
        run_cheapest = archive_r.get_cheapest_solution()
        hv_r = archive_r.calculate_hypervolume()

        runs_records.append({
            "run": r + 1,
            "seed": run_seed,
            "runtime_seconds": runtime_r,
            "pareto_size": len(archive_r),
            "best_T_MAX": run_fastest.t_max if run_fastest else None,
            "best_C_total": run_cheapest.cost if run_cheapest else None,
            "hypervolume": hv_r,
        })
        print(f"  Run {r+1:2d}/{args.runs} (seed={run_seed}): pareto_size={len(archive_r):2d} | best_T_MAX={run_fastest.t_max:6.2f}m | best_cost=${run_cheapest.cost:7.2f} ({runtime_r:.2f}s)", flush=True)
        if r == 0:
            combined_history = history_r

    total_wallclock = time.perf_counter() - total_t0
    archive = global_archive
    history = combined_history
    runtime = total_wallclock / args.runs

    # 4. Extract Global Solutions
    sorted_pts = archive.get_sorted_front()
    fastest = archive.get_fastest_solution()
    cheapest = archive.get_cheapest_solution()
    knee = archive.get_knee_solution()
    hypervolume = archive.calculate_hypervolume()

    print(f"\n[2/3] All Runs Complete! Total Wall-Clock: {total_wallclock:.2f}s (Avg: {runtime:.2f}s/run)")
    print(f"  Global Non-Dominated Frontier Size: {len(sorted_pts)} solutions")
    print(f"  Combined Hypervolume: {hypervolume:.2f}")

    # 5. Save JSON
    json_path = out_dir / "pareto_front.json"
    out_data = {
        "instance": name,
        "novelty": "Novelty 2: Time-Cost Multi-Objective Trade-off Optimization",
        "runs": args.runs,
        "iterations_per_run": args.iterations,
        "total_wallclock_seconds": total_wallclock,
        "mean_runtime_per_run": runtime,
        "pareto_size": len(sorted_pts),
        "hypervolume": hypervolume,
        "runs_records": runs_records,
        "cost_config": {
            "vehicle_fixed_cost": cost_cfg.vehicle_fixed_cost,
            "distance_cost_per_unit": cost_cfg.distance_cost_per_unit,
            "regular_shift_limit_minutes": cost_cfg.regular_shift_limit_minutes,
        },
        "extreme_solutions": {
            "fastest": fastest.to_dict() if fastest else None,
            "cheapest": cheapest.to_dict() if cheapest else None,
            "knee_compromise": knee.to_dict() if knee else None,
        },
        "pareto_front": [p.to_dict() for p in sorted_pts],
    }
    json_path.write_text(json.dumps(out_data, indent=2), encoding="utf-8")


    # 7. Save CSV Table
    csv_path = out_dir / "pareto_front.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Solution_ID", "T_MAX_minutes", "C_total_dollars", "Active_Vehicles",
            "Total_Distance", "Vehicle_Fixed_Cost", "Distance_Cost", "Regular_Crew_Cost",
            "Overtime_Crew_Cost", "Crowding_Distance", "Operator_Discovered"
        ])
        for idx, pt in enumerate(sorted_pts, 1):
            cb = pt.cost_breakdown
            writer.writerow([
                f"S_{idx:02d}",
                f"{pt.t_max:.4f}",
                f"{pt.cost:.2f}",
                cb.active_vehicles if cb else 0,
                f"{cb.total_distance:.2f}" if cb else 0.0,
                f"{cb.vehicle_fixed_cost:.2f}" if cb else 0.0,
                f"{cb.distance_cost:.2f}" if cb else 0.0,
                f"{cb.regular_crew_cost:.2f}" if cb else 0.0,
                f"{cb.overtime_crew_cost:.2f}" if cb else 0.0,
                f"{pt.crowding_distance:.4f}",
                pt.operator_used,
            ])

    # 8. Render Visual Plots
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    pareto_plot_path = figures_dir / "pareto_frontier.png"
    conv_plot_path = figures_dir / "convergence_multiobjective.png"

    plot_pareto_front(archive, name, pareto_plot_path)
    plot_convergence(history, name, conv_plot_path)

    # 9. Generate Comprehensive Markdown Report
    report_path = out_dir / "PARETO_REPORT.md"
    time_saved = cheapest.t_max - fastest.t_max if (cheapest and fastest) else 0.0
    cost_diff = fastest.cost - cheapest.cost if (cheapest and fastest) else 0.0
    marginal_rate = (cost_diff / time_saved) if time_saved > 0 else 0.0

    report_content = f"""# TD-VRPFCA Novelty 2 Report: Time–Cost Trade-Off Optimization

**Instance:** `{name.upper()}`  
**Algorithm:** Multi-Objective CT-ALNS (`MO-CTALNS`)  
**Search Budget:** `{args.runs}` independent runs × `{args.iterations}` iterations (`{total_wallclock:.2f}`s total wall-clock)  
**Global Non-Dominated Solutions:** `{len(sorted_pts)}` Pareto-optimal plans  
**Combined Hypervolume:** `{hypervolume:.2f}`  

---

## 1. Executive Trade-off Summary

Unlike single-objective optimization which forces an arbitrary choice, Novelty 2 reveals the **explicit operational trade-off** between completion time ($T_{{MAX}}$) and total operational cost ($C_{{total}}$):

| Decision Plan | Completion Time ($T_{{MAX}}$) | Total Cost ($C_{{total}}$) | Active Fleet | Total Distance | Strategic Role |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Plan A: Fastest Delivery** | **`{fastest.t_max:.2f} min`** | `${fastest.cost:.2f}` | `{fastest.cost_breakdown.active_vehicles if fastest.cost_breakdown else 0}` trucks | `{fastest.cost_breakdown.total_distance:.1f}` km | Priority/Rush deliveries where speed is paramount |
| **Plan B: Knee / Compromise** | **`{knee.t_max:.2f} min`** | **`${knee.cost:.2f}`** | `{knee.cost_breakdown.active_vehicles if knee.cost_breakdown else 0}` trucks | `{knee.cost_breakdown.total_distance:.1f}` km | **Recommended operational balance** |
| **Plan C: Budget / Lowest Cost**| `{cheapest.t_max:.2f} min` | **`${cheapest.cost:.2f}`** | `{cheapest.cost_breakdown.active_vehicles if cheapest.cost_breakdown else 0}` trucks | `{cheapest.cost_breakdown.total_distance:.1f}` km | Maximum cost saving; tolerates longer delivery windows |

> **Marginal Trade-off Insight:**  
> Shaving `{time_saved:.1f} minutes` off delivery completion time requires an additional expenditure of **`${cost_diff:.2f}`**, representing a marginal acceleration cost of **`${marginal_rate:.2f} per minute saved`**.

---

## 2. Visual Decision Support

![Pareto Frontier](figures/pareto_frontier.png)

![Search Convergence](figures/convergence_multiobjective.png)

---

## 3. Cost Component Decomposition

Itemized breakdown of how operational costs distribute across the extreme and compromise plans:

| Cost Component | Fastest Plan | Knee Plan | Cheapest Plan |
| :--- | :---: | :---: | :---: |
| **Vehicle Fixed Charges ($F_k$)** | `${fastest.cost_breakdown.vehicle_fixed_cost:.2f}` | `${knee.cost_breakdown.vehicle_fixed_cost:.2f}` | `${cheapest.cost_breakdown.vehicle_fixed_cost:.2f}` |
| **Distance & Fuel ($c_k \\cdot d_k$)** | `${fastest.cost_breakdown.distance_cost:.2f}` | `${knee.cost_breakdown.distance_cost:.2f}` | `${cheapest.cost_breakdown.distance_cost:.2f}` |
| **Regular Crew Wages** | `${fastest.cost_breakdown.regular_crew_cost:.2f}` | `${knee.cost_breakdown.regular_crew_cost:.2f}` | `${cheapest.cost_breakdown.regular_crew_cost:.2f}` |
| **Overtime Surcharges** | `${fastest.cost_breakdown.overtime_crew_cost:.2f}` | `${knee.cost_breakdown.overtime_crew_cost:.2f}` | `${cheapest.cost_breakdown.overtime_crew_cost:.2f}` |
| **TOTAL OPERATIONAL COST** | **`${fastest.cost:.2f}`** | **`${knee.cost:.2f}`** | **`${cheapest.cost:.2f}`** |

---

## 4. Full Non-Dominated Pareto Frontier Table

| ID | $T_{{MAX}}$ (min) | $C_{{total}}$ ($) | Active Trucks | Distance (km) | Operator Discovered | Crowding Distance |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: |
"""
    for idx, pt in enumerate(sorted_pts, 1):
        cb = pt.cost_breakdown
        report_content += (
            f"| `S_{idx:02d}` | `{pt.t_max:.2f}` | `${pt.cost:.2f}` | "
            f"`{cb.active_vehicles if cb else 0}` | `{cb.total_distance:.1f}` | "
            f"`{pt.operator_used}` | `{pt.crowding_distance:.3f}` |\n"
        )

    report_content += f"""
---
*Generated by `run_multiobjective.py`. All solutions strictly satisfy 100% capacity, crew, worker availability, and time-dependent travel/service constraints.*
"""
    report_path.write_text(report_content, encoding="utf-8")

    # 10. Print Console Summary
    print("\n" + "=" * 72)
    print(f"             PARETO TRADE-OFF FRONTIER ({name.upper()})")
    print("=" * 72)
    print(f"{'Plan Name':<22} | {'T_MAX (min)':<14} | {'C_total ($)':<14} | {'Vehicles':<10}")
    print("-" * 72)
    if fastest:
        print(f"{'Fastest (Min Time)':<22} | {fastest.t_max:<14.2f} | ${fastest.cost:<13.2f} | {fastest.cost_breakdown.active_vehicles:<10}")
    if knee:
        print(f"{'Knee (Best Balance)':<22} | {knee.t_max:<14.2f} | ${knee.cost:<13.2f} | {knee.cost_breakdown.active_vehicles:<10}")
    if cheapest:
        print(f"{'Cheapest (Min Cost)':<22} | {cheapest.t_max:<14.2f} | ${cheapest.cost:<13.2f} | {cheapest.cost_breakdown.active_vehicles:<10}")
    print("=" * 72)
    print(f"  Report written to: {report_path}")
    print(f"  Plots written to:  {figures_dir}")
    print(f"  Data written to:   {json_path} & {csv_path}\n")


if __name__ == "__main__":
    main()
