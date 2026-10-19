import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from td_vrpfca.loader import load_small_instance
from td_vrpfca.ctalns import CTALNS, ALNSSolution
from td_vrpfca.bwo import BWOOptimizer

def main():
    print("Loading Small Instance...")
    inst = load_small_instance("dataset/Small Intance")
    
    # Let's generate an initial solution using BWO to give ALNS a valid starting point
    print("Generating Initial Solution with BWO...")
    bwo = BWOOptimizer(inst, npop=20, procreation_rate=0.6, cannibalism_rate=0.5, mutation_rate=0.1)
    best_bwo, _, _ = bwo.run(max_iter=5)
    
    routes, crew, start_intervals = bwo.decode_chromosome(best_bwo.chromosome)
    init_sol = ALNSSolution(routes, crew, start_intervals)
    init_fitness = init_sol.evaluate(inst)
    print(f"Initial BWO TMAX: {init_fitness}")
    
    print("\nStarting CT-ALNS Optimization (with Rush-Hour Destroy & Crew-Aware Repair)...")
    alns = CTALNS(inst, init_sol, max_iter=50)
    best_alns, history = alns.optimize()
    
    print(f"\nFinal CT-ALNS TMAX: {best_alns.fitness}")
    print("Final Routes:")
    for k, r in best_alns.routes.items():
        if r:
            print(f"  Vehicle {k} (Crew {best_alns.crew[k]}): 0 -> {' -> '.join(map(str, r))} -> 0")

if __name__ == "__main__":
    main()
