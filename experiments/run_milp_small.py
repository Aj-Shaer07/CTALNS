from __future__ import annotations
import argparse, json, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))

from td_vrpfca.loader import load_small_instance, SourceDataError
from td_vrpfca.milp import build_paper_milp, solve, extract_solution
from td_vrpfca.report import write_json

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--time-limit", type=float, default=3600.0)
    ap.add_argument("--mode", choices=["strict","reconstructed"], default="reconstructed")
    ap.add_argument("--output", default="results/milp_small.json")
    args=ap.parse_args()
    try:
        inst=load_small_instance(args.dataset)
        print(f"Loaded Small Intance | customers={len(inst.customers)} vehicles={len(inst.vehicles)} crews={len(inst.crew)} intervals={len(inst.intervals)}")
        print(f"Mode: {args.mode}")
        result=build_paper_milp(inst,time_limit=args.time_limit,allow_reconstructed=args.mode=="reconstructed")
        result=solve(result)
        solution=extract_solution(result)
        payload={
            "instance":"Small Intance","mode":args.mode,"dataset":str(Path(args.dataset).resolve()),
            "time_limit":args.time_limit,"status":result.status_name,
            "objective_TMAX":result.objective,"best_bound":result.bound,"mip_gap":result.gap,
            "runtime":result.runtime,"solution_count":result.sol_count,
            "num_variables":result.num_vars,"num_constraints":result.num_constraints,
            "solution":solution,"source_metadata":inst.metadata,
        }
    except (SourceDataError, ValueError) as exc:
        payload={"instance":"Small Intance","mode":args.mode,"dataset":str(Path(args.dataset).resolve()),
                 "status":"NOT_RUN_SOURCE_OR_MODEL_DATA_INCOMPLETE","feasible_solution":False,
                 "reason":str(exc),"source_metadata":getattr(locals().get("inst",None),"metadata",{})}
        write_json(args.output,payload); print(json.dumps(payload,indent=2)); return 2
    write_json(args.output,payload); print(json.dumps(payload,indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())
