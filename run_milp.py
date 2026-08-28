"""Master runner.

Small:
  python3 run_milp.py --instance small --dataset "./dataset/Small Intance" --mode strict
Large:
  python3 run_milp.py --instance large --dataset "./dataset/Large Intance" --large-instance C101
"""
from __future__ import annotations
import argparse, os, subprocess, sys
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    ap=argparse.ArgumentParser()
    ap.add_argument("--instance",choices=["small","large"],required=True)
    ap.add_argument("--dataset",required=True)
    ap.add_argument("--time-limit",type=float,default=3600.0)
    ap.add_argument("--output",default=None)
    ap.add_argument("--mode",choices=["strict","reconstructed"],default="reconstructed")
    ap.add_argument("--large-instance",default="C101")
    ap.add_argument("--category-matrix",default="catheg.txt")
    ap.add_argument("--speed-profile",default="t_dep.txt")
    a=ap.parse_args()
    script=root/"experiments"/f"run_milp_{a.instance}.py"
    env=os.environ.copy(); env["PYTHONPATH"]=str(root)+os.pathsep+env.get("PYTHONPATH","")
    cmd=[sys.executable,str(script),"--dataset",a.dataset,"--time-limit",str(a.time_limit)]
    if a.output: cmd += ["--output",a.output]
    if a.instance=="small": cmd += ["--mode",a.mode]
    else: cmd += ["--instance",a.large_instance,"--category-matrix",a.category_matrix,"--speed-profile",a.speed_profile]
    raise SystemExit(subprocess.call(cmd,cwd=root,env=env))

if __name__=="__main__": main()
