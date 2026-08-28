from __future__ import annotations
import argparse, json, sys
from pathlib import Path

PROJECT_ROOT=Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0,str(PROJECT_ROOT))

from td_vrpfca.large_loader import load_large_instance
from td_vrpfca.milp import build_paper_milp, solve, extract_solution
from td_vrpfca.report import write_json

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset",required=True)
    ap.add_argument("--instance",default="C101")
    ap.add_argument("--time-limit",type=float,default=3600.0)
    ap.add_argument("--category-matrix",default="catheg.txt")
    ap.add_argument("--speed-profile",default="t_dep.txt")
    ap.add_argument("--output",default="results/milp_large.json")
    args=ap.parse_args()
    inst=None
    try:
        inst=load_large_instance(args.dataset,args.instance,args.category_matrix,args.speed_profile)
        print(f"Loaded {args.instance} | customers={len(inst.customers)} vehicles={len(inst.vehicles)} crews={len(inst.crew)} intervals={len(inst.intervals)}")
        result=build_paper_milp(inst,time_limit=args.time_limit)
        result=solve(result)
        payload={
            "instance":args.instance,"dataset":str(Path(args.dataset).resolve()),
            "time_limit":args.time_limit,"status":result.status_name,
            "objective_TMAX":result.objective,"best_bound":result.bound,"mip_gap":result.gap,
            "runtime":result.runtime,"optimality_proven":result.status_name=="OPTIMAL",
            "feasible_solution":result.sol_count>0,
            "num_variables":result.num_vars,"num_constraints":result.num_constraints,
            "solution":extract_solution(result),"source_metadata":inst.metadata
        }
    except (ValueError, FileNotFoundError, KeyError) as exc:
        payload={
            "instance":args.instance,"dataset":str(Path(args.dataset).resolve()),
            "time_limit":args.time_limit,
            "status":"NOT_RUN_SOURCE_OR_MODEL_DATA_INCOMPLETE",
            "feasible_solution":False,"optimality_proven":False,
            "reason":str(exc),
            "source_metadata":getattr(inst,"metadata",{}) if inst else {},
            "note":"This is a data/formulation diagnostic, not evidence that MILP is computationally infeasible."
        }
        write_json(args.output,payload); print(json.dumps(payload,indent=2)); return 2
    write_json(args.output,payload); print(json.dumps(payload,indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())
