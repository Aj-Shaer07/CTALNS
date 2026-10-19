#!/usr/bin/env python3
"""Run the initial CT-ALNS prototype on the shared TD-VRPFCA evaluator."""
from __future__ import annotations
import argparse, csv, json, statistics
from pathlib import Path
from tdvrpfca.data import load_small_instance, load_large_instance
from tdvrpfca.ctalns import CTALNSOptimizer
from tdvrpfca.model import evaluate_solution

ROOT = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser(description="Run CT-ALNS research prototype")
    p.add_argument('--kind', choices=['small','large'], default='small')
    p.add_argument('--instance', choices=['R101','R201','RC101','RC201'], default='R101')
    p.add_argument('--category', default='catheg.txt')
    p.add_argument('--speed', default='t_dep.txt')
    p.add_argument('--runs', type=int, default=3)
    p.add_argument('--iterations', type=int, default=30)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--return-leg-mode', choices=['source','physical'], default='source')
    p.add_argument('--removal-fraction', type=float, default=0.12)
    p.add_argument('--reaction', type=float, default=0.2)
    p.add_argument('--cooling-rate', type=float, default=0.995)
    p.add_argument('--output', type=Path, default=ROOT/'results'/'ctalns_runs.json')
    args = p.parse_args()
    if args.runs < 1 or args.iterations < 1:
        p.error('--runs and --iterations must be >= 1')
    if args.kind == 'small':
        inst = load_small_instance(ROOT/'data'/'small')
        name = 'small'
    else:
        inst = load_large_instance(ROOT/'data'/'large', args.instance,
            category_matrix=args.category, speed_profile=args.speed,
            return_leg_mode=args.return_leg_mode)
        name = args.instance
    rows=[]
    for r in range(args.runs):
        seed = None if args.seed is None else args.seed+r
        opt=CTALNSOptimizer(inst, seed=seed, return_leg_mode=args.return_leg_mode,
            removal_fraction=args.removal_fraction, reaction=args.reaction,
            cooling_rate=args.cooling_rate)
        best, history, current_history, runtime, op_stats=opt.run(args.iterations)
        evaluation=evaluate_solution(inst,best,return_leg_mode=args.return_leg_mode)
        rows.append({'seed':seed,'best_T_MAX':evaluation['T_MAX'],
            'feasible':evaluation['feasible'],'runtime_seconds':runtime,
            'routes':best.routes,'crew':best.crew,'start_intervals':best.start_intervals,
            'history':history,'current_history':current_history,'operator_stats':op_stats,'violations':evaluation['violations']})
        print(f"Run {r+1}/{args.runs}: feasible={evaluation['feasible']} T_MAX={evaluation['T_MAX']:.6f} runtime={runtime:.3f}s",flush=True)
    finite=[x['best_T_MAX'] for x in rows if x['feasible']]
    result={'algorithm':'CT-ALNS-v3','instance':name,'kind':args.kind,
        'category_matrix':args.category if args.kind=='large' else None,
        'speed_profile':args.speed if args.kind=='large' else None,
        'return_leg_mode':args.return_leg_mode,'parameters':{
            'runs':args.runs,'iterations':args.iterations,'base_seed':args.seed,
            'removal_fraction':args.removal_fraction,'reaction':args.reaction,
            'cooling_rate':args.cooling_rate},
        'summary':{'feasible_runs':len(finite),'runs':len(rows),
            'best_T_MAX':min(finite) if finite else None,
            'mean_best_T_MAX':statistics.mean(finite) if finite else None,
            'stdev_best_T_MAX':statistics.stdev(finite) if len(finite)>1 else 0.0,
            'mean_runtime_seconds':statistics.mean(x['runtime_seconds'] for x in rows)},
        'runs':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    csvpath=args.output.with_suffix('.csv')
    with csvpath.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['algorithm','instance','runs','feasible_runs','best_T_MAX','mean_best_T_MAX','stdev_best_T_MAX','mean_runtime_seconds'])
        writer.writeheader(); writer.writerow({'algorithm':result['algorithm'],'instance':name,**result['summary']})
    print(json.dumps(result['summary'],indent=2)); print(f'JSON: {args.output}\nCSV:  {csvpath}')

if __name__=='__main__': main()
