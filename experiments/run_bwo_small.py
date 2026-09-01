import argparse
import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from td_vrpfca.loader import load_small_instance
from td_vrpfca.bwo import BWOOptimizer
from td_vrpfca.report import generate_bwo_report

def main():
    parser = argparse.ArgumentParser(description="Run BWO on small instance")
    parser.add_argument("--dataset", type=str, required=True, help="Path to Small Intance directory")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs")
    args = parser.parse_args()

    inst = load_small_instance(args.dataset)
    
    npop = 50
    i_max = 10 # This is max_iter
    
    runs_results = []
    
    for r in range(args.runs):
        current_seed = args.seed + r if args.seed is not None else None
        
        optimizer = BWOOptimizer(
            instance=inst,
            npop=npop,
            procreation_rate=0.60, 
            cannibalism_rate=0.50,
            mutation_rate=0.10,
            seed=current_seed
        )
        
        best_sol, hist, runtime = optimizer.run(max_iter=i_max)
        
        routes, crew, start_intervals = optimizer.decode_chromosome(best_sol.chromosome)
        is_feasible = (best_sol.fitness != float('inf'))
        
        runs_results.append({
            "seed": current_seed,
            "TMAX": best_sol.fitness,
            "runtime": runtime,
            "routes": routes,
            "crew": crew,
            "start_intervals": start_intervals,
            "hist": hist,
            "feasible": is_feasible
        })
        
    generate_bwo_report(
        instance_name="Small Intance",
        runs_results=runs_results,
        npop=npop,
        max_iter=i_max,
        milp_baseline=63.825,
        output_dir="results/bwo/small"
    )

if __name__ == "__main__":
    main()
