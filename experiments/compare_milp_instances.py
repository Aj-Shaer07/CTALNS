from __future__ import annotations
import argparse, csv, json
from pathlib import Path

FIELDS=["Instance","Customers","Vehicles","Variables","Constraints","Status",
        "Feasible","Optimality proven","T_MAX","Best bound","MIP gap","Runtime","Time limit"]

def row(path):
    d=json.loads(Path(path).read_text(encoding="utf-8"))
    return {"Instance":d.get("instance"),"Customers":d.get("source_metadata",{}).get("customers",d.get("num_customers")),
            "Vehicles":d.get("source_metadata",{}).get("vehicle_count",d.get("num_vehicles")),
            "Variables":d.get("num_variables"),"Constraints":d.get("num_constraints"),
            "Status":d.get("status"),"Feasible":d.get("feasible_solution"),
            "Optimality proven":d.get("optimality_proven",d.get("status")=="OPTIMAL"),
            "T_MAX":d.get("objective_TMAX"),"Best bound":d.get("best_bound"),
            "MIP gap":d.get("mip_gap"),"Runtime":d.get("runtime"),"Time limit":d.get("time_limit")}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--small",default="results/milp_small.json")
    ap.add_argument("--large",default="results/milp_large.json")
    ap.add_argument("--output",default="results/milp_comparison.csv")
    args=ap.parse_args()
    rows=[row(args.small),row(args.large)]
    p=Path(args.output); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(json.dumps(rows,indent=2))

if __name__=="__main__": main()
