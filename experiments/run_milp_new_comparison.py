import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import gurobipy as gp
from td_vrpfca.loader import load_small_instance
from td_vrpfca.milp import build_paper_milp
from td_vrpfca.milp_new import build_paper_milp as build_new_milp

def main():
    print("Loading instance...")
    inst = load_small_instance("dataset/Small Intance")
    
    print("--- Running Old MILP ---")
    try:
        res_old = build_paper_milp(inst, time_limit=3600, allow_reconstructed=True)
        res_old.model.Params.OutputFlag = 0
        res_old.model.optimize()
        if res_old.model.Status in [gp.GRB.OPTIMAL, gp.GRB.TIME_LIMIT, gp.GRB.SUBOPTIMAL]:
            print("Old MILP ObjVal:", res_old.model.ObjVal)
        else:
            print("Old MILP Status:", res_old.model.Status)
    except gp.GurobiError as e:
        print("Old MILP Error:", e)

    print("\n--- Running New MILP ---")
    try:
        res_new = build_new_milp(inst, time_limit=3600, allow_reconstructed=True)
        res_new.model.Params.OutputFlag = 0
        res_new.model.optimize()
        if res_new.model.Status in [gp.GRB.OPTIMAL, gp.GRB.TIME_LIMIT, gp.GRB.SUBOPTIMAL]:
            print("New MILP ObjVal:", res_new.model.ObjVal)
        else:
            print("New MILP Status:", res_new.model.Status)
    except gp.GurobiError as e:
        print("New MILP Error:", e)

if __name__ == "__main__":
    main()
