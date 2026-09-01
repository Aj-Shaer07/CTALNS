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

import statistics

def generate_bwo_report(instance_name: str, runs_results: list, npop: int, max_iter: int, milp_baseline: float, output_dir: str):
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)
    
    tmax_values = [r["TMAX"] for r in runs_results if r["feasible"]]
    runtimes = [r["runtime"] for r in runs_results]
    
    if not tmax_values:
        print("No feasible solutions found across runs.")
        return
        
    best_tmax = min(tmax_values)
    best_run = next(r for r in runs_results if r["TMAX"] == best_tmax)
    
    mean_tmax = statistics.mean(tmax_values)
    std_tmax = statistics.stdev(tmax_values) if len(tmax_values) > 1 else 0.0
    
    mean_runtime = statistics.mean(runtimes)
    min_runtime = min(runtimes)
    max_runtime = max(runtimes)
    
    gap_abs = None
    gap_rel = None
    if milp_baseline is not None:
        gap_abs = best_tmax - milp_baseline
        gap_rel = (gap_abs / milp_baseline) * 100.0
        
    # Format route and crew data for best solution
    route_sol = []
    crew_assignment = []
    
    for v_id, route in best_run["routes"].items():
        if route:
            formatted_route = "0 → " + " → ".join(map(str, route)) + " → 11"
            route_sol.append({"vehicle": v_id, "route": formatted_route})
            
            c_type = best_run["crew"].get(v_id)
            crew_assignment.append({"vehicle": v_id, "crew_type": c_type})
            
    json_result = {
        "algorithm": "BWO",
        "instance": instance_name,
        "status": "FEASIBLE" if best_run["feasible"] else "INFEASIBLE",
        "best_TMAX": best_tmax,
        "mean_TMAX": mean_tmax,
        "std_TMAX": std_tmax,
        "runtime": min_runtime,
        "mean_runtime": mean_runtime,
        "max_runtime": max_runtime,
        "iterations": max_iter,
        "population_size": npop,
        "seed": best_run["seed"],
        "feasible": best_run["feasible"],
        "route_solution": route_sol,
        "crew_assignment": crew_assignment,
        "source_fidelity": "reconstructed",
        "reconstruction_notes": "Cannibalism phases reconstructed; Initialization and Feasibility logic rebuilt from undefined variables; single-time interval format preserved."
    }
    
    prefix = instance_name.split(".")[0]
    if "Small" in prefix:
        prefix = "small"
    
    json_path = p / f"bwo_{prefix}_result.json"
    write_json(json_path, json_result)
    
    # Generate TXT Report
    txt_lines = []
    txt_lines.append("================================================================")
    txt_lines.append("                        TD-VRPFCA — BWO RESULTS                 ")
    txt_lines.append("================================================================")
    txt_lines.append(f"Instance       : {instance_name}")
    txt_lines.append(f"Algorithm      : Black Widow Optimization")
    txt_lines.append(f"Source         : Ilabaca et al. repository")
    txt_lines.append(f"Status         : {'FEASIBLE' if best_run['feasible'] else 'INFEASIBLE'}")
    txt_lines.append("----------------------------------------------------------------")
    txt_lines.append("                          PERFORMANCE                           ")
    txt_lines.append("----------------------------------------------------------------")
    txt_lines.append(f"Best TMAX      : {best_tmax:.3f}")
    txt_lines.append(f"Mean TMAX      : {mean_tmax:.3f}")
    txt_lines.append(f"Std TMAX       : {std_tmax:.3f}")
    txt_lines.append(f"Min Runtime    : {min_runtime:.3f} seconds")
    txt_lines.append(f"Mean Runtime   : {mean_runtime:.3f} seconds")
    txt_lines.append(f"Max Runtime    : {max_runtime:.3f} seconds")
    txt_lines.append(f"Iterations     : {max_iter}")
    txt_lines.append(f"Population     : {npop}")
    txt_lines.append(f"Best Run Seed  : {best_run['seed']}")
    txt_lines.append("----------------------------------------------------------------")
    txt_lines.append("                          SOLUTION                              ")
    txt_lines.append("----------------------------------------------------------------")
    
    for v_id, route in best_run["routes"].items():
        if route:
            c_type = best_run["crew"].get(v_id)
            formatted_route = "0 → " + " → ".join(map(str, route)) + " → 11"
            txt_lines.append(f"Vehicle {v_id}:")
            txt_lines.append(f"  Route : {formatted_route}")
            txt_lines.append(f"  Crew  : Type {c_type}")
            txt_lines.append("")
            
    txt_lines.append("----------------------------------------------------------------")
    txt_lines.append("                       MILP COMPARISON                          ")
    txt_lines.append("----------------------------------------------------------------")
    if milp_baseline is not None:
        txt_lines.append(f"MILP TMAX      : {milp_baseline:.3f}")
        txt_lines.append(f"BWO TMAX       : {best_tmax:.3f}")
        txt_lines.append(f"Absolute Gap   : {gap_abs:.3f}")
        txt_lines.append(f"Relative Gap   : {gap_rel:.3f} %")
    else:
        txt_lines.append("MILP TMAX      : N/A")
        
    txt_lines.append("----------------------------------------------------------------")
    txt_lines.append("                       SOURCE FIDELITY                          ")
    txt_lines.append("----------------------------------------------------------------")
    txt_lines.append("Implementation : Reconstructed / Source-faithful with gaps")
    txt_lines.append("Repository     : BWO.py / BWO_etapas.py / Fitness.py / calculos_BWO.py")
    txt_lines.append("Reconstruction : Cannibalism completely reconstructed using paper Algorithm 2")
    txt_lines.append("                 as the repository implementation was undefined (self.pop).")
    txt_lines.append("                 Time representation single-interval appended at the end")
    txt_lines.append("                 preserved from repository. Feasibility rewritten to be")
    txt_lines.append("                 cleanly isolated instead of global variables.")
    txt_lines.append("================================================================")
    
    txt_path = p / f"bwo_{prefix}_report.txt"
    txt_path.write_text("\n".join(txt_lines), encoding="utf-8")

