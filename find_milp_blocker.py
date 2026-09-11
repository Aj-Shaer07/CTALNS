import gurobipy as gp
from td_vrpfca.loader import load_small_instance
from td_vrpfca.milp_new import build_paper_milp

print("Building MILP model...")
inst = load_small_instance("dataset/Small Intance")
inst.worker_availability = {1: 4.0, 2: 2.0, 3: 2.0}
res = build_paper_milp(inst, time_limit=60, allow_reconstructed=True)
m = res.model

def get_y(k, d): return m.getVarByName(f"y_{k}_{d}")
def get_z(k, i): return m.getVarByName(f"z_{k}_{i}")
def get_x(k, i, j): 
    # Sum over all intervals l
    return gp.quicksum(m.getVarByName(f"x_{k}_{i}_{j}_{l}") for l in inst.intervals)

print("Forcing the 35.325 BWO route into the MILP...")
# Vehicle 1: 0 -> 4 -> 2 -> 10 -> 5 -> 11, Crew 6
m.addConstr(get_y(1, 6) == 1, name="force_crew_v1")
m.addConstr(get_x(1, 0, 4) == 1, name="force_edge_v1_0_4")
m.addConstr(get_x(1, 4, 2) == 1, name="force_edge_v1_4_2")
m.addConstr(get_x(1, 2, 10) == 1, name="force_edge_v1_2_10")
m.addConstr(get_x(1, 10, 5) == 1, name="force_edge_v1_10_5")
m.addConstr(get_x(1, 5, 11) == 1, name="force_edge_v1_5_11")

# Vehicle 2: 0 -> 3 -> 6 -> 8 -> 7 -> 9 -> 1 -> 11, Crew 7
m.addConstr(get_y(2, 7) == 1, name="force_crew_v2")
m.addConstr(get_x(2, 0, 3) == 1, name="force_edge_v2_0_3")
m.addConstr(get_x(2, 3, 6) == 1, name="force_edge_v2_3_6")
m.addConstr(get_x(2, 6, 8) == 1, name="force_edge_v2_6_8")
m.addConstr(get_x(2, 8, 7) == 1, name="force_edge_v2_8_7")
m.addConstr(get_x(2, 7, 9) == 1, name="force_edge_v2_7_9")
m.addConstr(get_x(2, 9, 1) == 1, name="force_edge_v2_9_1")
m.addConstr(get_x(2, 1, 11) == 1, name="force_edge_v2_1_11")

m.Params.OutputFlag = 0
m.optimize()

if m.Status == gp.GRB.INFEASIBLE:
    print("\n[!] BWO ROUTE IS INFEASIBLE IN MILP!")
    print("Computing exactly which constraint blocks it...")
    m.computeIIS()
    print("\n--- BLOCKING CONSTRAINTS ---")
    for c in m.getConstrs():
        if c.IISConstr:
            print(c.ConstrName)
else:
    print("\n[+] BWO Route is FEASIBLE in MILP! ObjVal:", m.ObjVal)
