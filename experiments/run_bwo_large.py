import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from td_vrpfca.large_loader import load_large_instance
from td_vrpfca.bwo import BWOOptimizer
from td_vrpfca.report import generate_bwo_report

def main():
    parser = argparse.ArgumentParser(description="Run BWO on large instance")
    parser.add_argument("--dataset", type=str, required=True, help="Path to Large Intance directory")
    parser.add_argument("--instance", type=str, required=True, help="Instance name e.g. C101")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs")
    args = parser.parse_args()

    inst = load_large_instance(args.dataset, args.instance)
    
    np_val = 0.60
    cr_val = 0.50
    nm_val = 0.10
    npop = 20
    i_max = 100 # This is max_iter
    
    runs_results = []
    
    for r in range(args.runs):
        current_seed = args.seed + r if args.seed is not None else None
        
        optimizer = BWOOptimizer(
            instance=inst,
            npop=npop,
            procreation_rate=np_val, 
            cannibalism_rate=cr_val,
            mutation_rate=nm_val,
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
        instance_name=args.instance,
        runs_results=runs_results,
        npop=npop,
        max_iter=i_max,
        milp_baseline=None,
        output_dir="results/bwo/large"
    )

if __name__ == "__main__":
    main()
