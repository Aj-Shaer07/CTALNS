#!/usr/bin/env python3
"""Create a readable, auditable results pack from CT-ALNS and BWO JSON outputs.

Example:
  python analyze_results.py --ctalns results/ctalns_v3_R101_20x100_combined.json \
      --bwo results/bwo_R101_per_vehicle_20x100.json --out results/presentation

Only the plots/report are derived here; raw experiment JSON files are preserved.
"""
from __future__ import annotations
import argparse, csv, json, math, statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from tdvrpfca.data import load_large_instance, _read_solomon
from tdvrpfca.model import Solution, evaluate_solution

ROOT = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def get_runs(path, algorithm):
    d = read_json(path)
    if isinstance(d, list):
        if not d: raise ValueError(f'No experiment records in {path}')
        # BWO runner stores one record per config, select matching first record.
        rec = d[0]
    else:
        rec = d
    runs = rec.get('runs', [])
    if not runs: raise ValueError(f'No runs found in {path}')
    return rec, runs


def to_solution(run):
    return Solution(
        routes={int(k): list(v) for k,v in run['routes'].items()},
        crew={int(k): int(v) for k,v in run['crew'].items()},
        start_intervals={int(k): int(v) for k,v in run['start_intervals'].items()},
    )


def stats(vals):
    vals = [float(x) for x in vals if x is not None and math.isfinite(float(x))]
    return {'n':len(vals),'best':min(vals) if vals else None,'mean':statistics.mean(vals) if vals else None,
            'median':statistics.median(vals) if vals else None,'std':statistics.stdev(vals) if len(vals)>1 else 0.0,
            'worst':max(vals) if vals else None}


def write_csv(path, rows):
    if not rows: return
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def plot_convergence(best_run, out):
    hist=best_run.get('history', [])
    cur=best_run.get('current_history', [])
    if not hist: return
    fig,ax=plt.subplots(figsize=(10,5.2))
    ax.plot(range(len(hist)),hist,label='Best-so-far T_MAX',linewidth=2.6)
    if cur and len(cur)==len(hist): ax.plot(range(len(cur)),cur,label='Current solution T_MAX',alpha=.7,linewidth=1.1)
    ax.set(title='Search trajectory — best CT-ALNS run',xlabel='Recorded search step',ylabel='T_MAX (time units)')
    ax.grid(True,alpha=.25); ax.legend(); fig.tight_layout(); fig.savefig(out,dpi=180); plt.close(fig)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ctalns',type=Path,required=True,help='CT-ALNS JSON output')
    ap.add_argument('--bwo',type=Path,default=None,help='Optional BWO JSON output (single configuration record list)')
    ap.add_argument('--out',type=Path,default=ROOT/'results'/'presentation')
    ap.add_argument('--data-dir',type=Path,default=ROOT/'data'/'large')
    args=ap.parse_args(); out=args.out; figs=out/'figures'; tables=out/'tables'; figs.mkdir(parents=True,exist_ok=True); tables.mkdir(parents=True,exist_ok=True)
    c_rec,c_runs=get_runs(args.ctalns,'CT-ALNS')
    instance=c_rec.get('instance','R101'); category=c_rec.get('category_matrix') or 'catheg.txt'; speed=c_rec.get('speed_profile') or 't_dep.txt'; return_mode=c_rec.get('return_leg_mode','source')
    inst=load_large_instance(args.data_dir,instance,category_matrix=category,speed_profile=speed,return_leg_mode=return_mode)
    feasible=[r for r in c_runs if r.get('feasible',False)]
    if not feasible: raise ValueError('CT-ALNS file has no feasible runs')
    best_run=min(feasible,key=lambda r:float(r['best_T_MAX']))
    best_solution=to_solution(best_run); eval_result=evaluate_solution(inst,best_solution,return_leg_mode=return_mode)
    if not eval_result['feasible']: raise ValueError('Best run failed fresh evaluator validation: '+str(eval_result['violations']))
    routes=eval_result['route_results']; active=sorted([r for r in routes if r['customers']],key=lambda r:r['vehicle'])
    # Keep original IDs for audit; provide compact display IDs only as a convenience.
    vehicle_rows=[]
    for display_id,r in enumerate(sorted(active,key=lambda x:x['vehicle']),1):
        v=inst.vehicles[r['vehicle']]
        vehicle_rows.append({'display_vehicle':display_id,'original_vehicle_id':r['vehicle'],'customer_count':len(r['customers']),
          'customers_sequence':' -> '.join(map(str,[0]+r['customers']+[101])),'crew_id':r['crew_id'],
          'start_interval':r['start_interval'],'start_time':round(r['start_time'],6),'load':round(r['load'],6),
          'capacity':v.capacity,'load_utilization_pct':round(100*r['load']/v.capacity,3) if v.capacity else 0,
          'travel_time':round(r['travel_time'],6),'service_time':round(r['service_time'],6),
          'completion_time':round(r['completion_time'],6),'is_critical_route':abs(r['completion_time']-eval_result['T_MAX'])<1e-8})
    write_csv(tables/'best_solution_vehicle_summary.csv',vehicle_rows)
    # Customer assignment / exact coverage audit.
    assignment=[]
    for r in active:
        for pos,cust in enumerate(r['customers'],1): assignment.append({'customer_id':cust,'original_vehicle_id':r['vehicle'],'display_vehicle':next(x['display_vehicle'] for x in vehicle_rows if x['original_vehicle_id']==r['vehicle']),'stop_order':pos})
    assignment.sort(key=lambda x:x['customer_id']); write_csv(tables/'customer_assignment.csv',assignment)
    # Worker counts under evaluator (all vehicle assignments) and active-route crew demand.
    worker_rows=[]
    labels={1:'DP',2:'Dr',3:'MFDP'}
    for wt,available in inst.worker_availability.items():
        assigned_all=sum(inst.crew[best_solution.crew[k]].get(wt,0) for k in inst.vehicles if k in best_solution.crew)
        active_used=sum(inst.crew[r['crew_id']].get(wt,0) for r in active)
        worker_rows.append({'worker_type':labels.get(wt,str(wt)),'available':available,'assigned_all_vehicles_evaluator':assigned_all,
          'active_routes_only':active_used,'remaining_if_active_only':available-active_used})
    write_csv(tables/'worker_availability.csv',worker_rows)
    # Distribution summaries and route-level load balance indicators.
    loads=[r['load'] for r in active]; utils=[x['load_utilization_pct'] for x in vehicle_rows]; completions=[r['completion_time'] for r in active]; custcounts=[len(r['customers']) for r in active]
    def cv(vals):
        m=statistics.mean(vals) if vals else 0
        return statistics.pstdev(vals)/m if len(vals)>1 and abs(m)>1e-12 else 0
    load_metrics={'active_vehicles':len(active),'available_vehicles':len(inst.vehicles),'customers_served':len(assignment),'expected_customers':len(inst.customers),
      'customer_coverage_exactly_once':len(assignment)==len(inst.customers) and len({x['customer_id'] for x in assignment})==len(inst.customers),
      'T_MAX':eval_result['T_MAX'],'min_completion_time':min(completions),'max_completion_time':max(completions),
      'completion_time_range':max(completions)-min(completions),'completion_time_mean':statistics.mean(completions),
      'completion_time_population_std':statistics.pstdev(completions),'completion_time_CV':cv(completions),
      'min_load':min(loads),'max_load':max(loads),'mean_load':statistics.mean(loads),'load_population_std':statistics.pstdev(loads),
      'load_CV':cv(loads),'min_load_utilization_pct':min(utils),'max_load_utilization_pct':max(utils),'mean_load_utilization_pct':statistics.mean(utils),
      'customer_count_min':min(custcounts),'customer_count_max':max(custcounts),'customer_count_mean':statistics.mean(custcounts),
      'evaluator_feasible':eval_result['feasible'],'evaluator_violations':eval_result['violations']}
    (out/'load_balance_metrics.json').write_text(json.dumps(load_metrics,indent=2),encoding='utf-8')
    # Per-run data for reproducible distribution plots.
    cvals=[float(r['best_T_MAX']) for r in c_runs if r.get('feasible',False)]
    run_rows=[{'algorithm':'CT-ALNS-v3','seed':r.get('seed'),'feasible':r.get('feasible'),'best_T_MAX':r.get('best_T_MAX'),'runtime_seconds':r.get('runtime_seconds')} for r in c_runs]
    b_rec=b_runs=None
    if args.bwo:
        b_rec,b_runs=get_runs(args.bwo,'BWO')
        run_rows += [{'algorithm':'BWO','seed':r.get('seed'),'feasible':r.get('feasible'),'best_T_MAX':r.get('best_T_MAX'),'runtime_seconds':r.get('runtime_seconds')} for r in b_runs]
    write_csv(tables/'per_run_results.csv',run_rows)
    # Convergence for best seed.
    plot_convergence(best_run,figs/'convergence_best_run.png')
    # Active route load/capacity, completion time and customer counts.
    xs=[f"V{x['display_vehicle']}\n(id {x['original_vehicle_id']})" for x in vehicle_rows]
    fig,axs=plt.subplots(3,1,figsize=(13,11),sharex=True)
    axs[0].bar(xs,loads); axs[0].set_ylabel('Demand load'); axs[0].set_title('Route workload balance — load and capacity'); axs[0].grid(axis='y',alpha=.25)
    caps=[x['capacity'] for x in vehicle_rows]; axs[0].plot(range(len(caps)),caps,linestyle='--',linewidth=1.8,label='Capacity'); axs[0].legend()
    axs[1].bar(xs,utils); axs[1].axhline(100,color='red',linestyle='--',linewidth=1.2,label='Capacity limit'); axs[1].set_ylabel('Capacity used (%)'); axs[1].grid(axis='y',alpha=.25); axs[1].legend()
    axs[2].bar(xs,completions); axs[2].axhline(eval_result['T_MAX'],color='red',linestyle='--',linewidth=1.5,label=f"T_MAX = {eval_result['T_MAX']:.2f}"); axs[2].set_ylabel('Completion time'); axs[2].set_xlabel('Compact display ID (original ID shown underneath)'); axs[2].grid(axis='y',alpha=.25); axs[2].legend()
    fig.tight_layout(); fig.savefig(figs/'active_vehicle_balance.png',dpi=180); plt.close(fig)
    # Route map from original Solomon coordinates; the line back to the dummy sink is not plotted.
    coord_rows=_read_solomon(args.data_dir/f"{instance}.txt")
    coords={int(row[0]):(float(row[1]),float(row[2])) for row in coord_rows}
    fig,ax=plt.subplots(figsize=(9,7.5))
    cmap=plt.get_cmap('tab20',max(1,len(active)))
    for idx,r in enumerate(active):
        seq=[0]+list(r['customers'])
        xx=[coords[n][0] for n in seq if n in coords]; yy=[coords[n][1] for n in seq if n in coords]
        ax.plot(xx,yy,marker='o',markersize=3.2,linewidth=1.25,color=cmap(idx),alpha=.9,label=f"Display V{idx+1} (ID {r['vehicle']})")
    if 0 in coords: ax.scatter([coords[0][0]],[coords[0][1]],marker='*',s=220,c='black',edgecolors='white',linewidths=.7,label='Depot (0)',zorder=5)
    ax.set(title=f'{instance} customer routes — best CT-ALNS solution',xlabel='X coordinate',ylabel='Y coordinate'); ax.set_aspect('equal',adjustable='datalim'); ax.grid(True,alpha=.2)
    ax.legend(loc='upper left',bbox_to_anchor=(1.02,1),fontsize=7,ncol=1); fig.tight_layout(); fig.savefig(figs/'route_map.png',dpi=180,bbox_inches='tight'); plt.close(fig)
    # TMAX run distribution comparison.
    alg_data={'CT-ALNS-v3':cvals}
    if b_runs is not None: alg_data['BWO']=[float(r['best_T_MAX']) for r in b_runs if r.get('feasible',False)]
    fig,ax=plt.subplots(figsize=(8.5,5.5)); ax.boxplot(list(alg_data.values()),tick_labels=list(alg_data.keys()),showmeans=True); ax.set_ylabel('Best T_MAX per run'); ax.set_title('Run-to-run objective distribution (lower is better)'); ax.grid(axis='y',alpha=.25); fig.tight_layout(); fig.savefig(figs/'objective_distribution.png',dpi=180); plt.close(fig)
    if b_runs is not None:
        fig,axs=plt.subplots(1,2,figsize=(11,4.8))
        for ax,metric,title,ylabel in [(axs[0],'best_T_MAX','Objective distribution','Best T_MAX'),(axs[1],'runtime_seconds','Runtime distribution','Runtime (seconds)')]:
            vals=[[float(r[metric]) for r in rr if r.get('feasible',False) and r.get(metric) is not None] for rr in [c_runs,b_runs]]
            ax.boxplot(vals,tick_labels=['CT-ALNS-v3','BWO'],showmeans=True); ax.set_title(title); ax.set_ylabel(ylabel); ax.grid(axis='y',alpha=.25)
        fig.tight_layout(); fig.savefig(figs/'objective_runtime_comparison.png',dpi=180); plt.close(fig)
    # Operator diagnostics for best run.
    op=best_run.get('operator_stats',{})
    if op:
        op_rows=[]
        for name,s in op.items(): op_rows.append({'operator':name,'uses':s.get('uses',0),'accepted':s.get('accepted',0),'improving':s.get('improving',0),'average_reward':s.get('average_reward',0),'final_weight':s.get('weight',0)})
        op_rows.sort(key=lambda x:(x['improving'],x['average_reward']),reverse=True); write_csv(tables/'best_run_operator_diagnostics.csv',op_rows)
        fig,ax=plt.subplots(figsize=(10,6)); names=[r['operator'] for r in op_rows]; yy=np.arange(len(names)); ax.barh(yy,[r['improving'] for r in op_rows]); ax.set_yticks(yy,names); ax.invert_yaxis(); ax.set_xlabel('Improving moves'); ax.set_title('Operator contribution in the best run'); ax.grid(axis='x',alpha=.25); fig.tight_layout(); fig.savefig(figs/'operator_improvements.png',dpi=180); plt.close(fig)
    # Markdown report, embeds figures using relative paths.
    cstats=stats(cvals); bstats=stats([float(r['best_T_MAX']) for r in b_runs if r.get('feasible',False)]) if b_runs else None
    ctime=statistics.mean(float(r['runtime_seconds']) for r in c_runs if r.get('runtime_seconds') is not None)
    report=[f'# {instance} — CT-ALNS Results Dashboard','',
      '> Generated by `analyze_results.py`. Raw experiment JSON remains the source of truth. Lower T_MAX is better.','',
      '## Executive summary','',
      f'- **Best CT-ALNS T_MAX:** {cstats["best"]:.3f}; **mean:** {cstats["mean"]:.3f}; **median:** {cstats["median"]:.3f}; **SD:** {cstats["std"]:.3f}.',
      f'- **Feasible runs:** {sum(bool(r.get("feasible")) for r in c_runs)}/{len(c_runs)}; **mean runtime:** {ctime:.3f} s/run.',
      f'- **Best-run seed:** {best_run.get("seed")}; **active vehicles:** {len(active)}/{len(inst.vehicles)}; **customers:** {len(assignment)}/{len(inst.customers)}.',
      f'- **Fresh evaluator check:** {"PASS" if eval_result["feasible"] else "FAIL"}; **T_MAX recomputed:** {eval_result["T_MAX"]:.6f}.','',
      '## Algorithm comparison','']
    if bstats:
        bruntime=statistics.mean(float(r['runtime_seconds']) for r in b_runs if r.get('runtime_seconds') is not None)
        report += [ '| Metric | CT-ALNS-v3 | BWO |','|---|---:|---:|',
          f'| Feasible runs | {sum(bool(r.get("feasible")) for r in c_runs)}/{len(c_runs)} | {sum(bool(r.get("feasible")) for r in b_runs)}/{len(b_runs)} |',
          f'| Best T_MAX | {cstats["best"]:.3f} | {bstats["best"]:.3f} |',f'| Mean T_MAX | {cstats["mean"]:.3f} | {bstats["mean"]:.3f} |',
          f'| Median T_MAX | {cstats["median"]:.3f} | {bstats["median"]:.3f} |',f'| Std. dev. T_MAX | {cstats["std"]:.3f} | {bstats["std"]:.3f} |',
          f'| Mean runtime (s/run) | {ctime:.3f} | {bruntime:.3f} |','',
          '**Fair-comparison note:** these are the supplied experiment files. Confirm identical evaluator, data files, time-mode, return-leg mode, and stopping budget before treating the comparison as a controlled algorithmic claim. The current run files both label R101 / `catheg.txt` / `t_dep.txt` / source return-leg mode; BWO uses per-vehicle time mode.','']
    report += ['## Best solution and load balance','',
      f'- Exact customer coverage: **{load_metrics["customers_served"]}/{load_metrics["expected_customers"]}**, exactly once = **{load_metrics["customer_coverage_exactly_once"]}**.',
      f'- Load: min **{load_metrics["min_load"]:.2f}**, mean **{load_metrics["mean_load"]:.2f}**, max **{load_metrics["max_load"]:.2f}**; mean capacity utilization **{load_metrics["mean_load_utilization_pct"]:.1f}%**.',
      f'- Completion times: min **{load_metrics["min_completion_time"]:.2f}**, mean **{load_metrics["completion_time_mean"]:.2f}**, max/T_MAX **{load_metrics["T_MAX"]:.2f}**; range **{load_metrics["completion_time_range"]:.2f}**.',
      f'- Load coefficient of variation: **{load_metrics["load_CV"]:.3f}**; completion-time coefficient of variation: **{load_metrics["completion_time_CV"]:.3f}**. These are descriptive balance metrics, not extra optimized objectives.',
      '- **Vehicle IDs:** compact display IDs are only presentation labels. The CSV retains each original vehicle ID; do not rewrite raw solution IDs unless vehicle interchangeability has been confirmed.','',
      '![Active vehicle load and completion](figures/active_vehicle_balance.png)','',
      '## Search and repeatability','', '![Best-run convergence](figures/convergence_best_run.png)','',
      '![Objective distribution](figures/objective_distribution.png)','']
    if b_runs is not None: report += ['![Objective and runtime comparison](figures/objective_runtime_comparison.png)','']
    if op: report += ['## Operator diagnostics','', '![Operator improvements](figures/operator_improvements.png)','', 'See `tables/best_run_operator_diagnostics.csv` for uses, accepted moves, improving moves, average reward, and final weight.','']
    report += ['## Output files','',
      '- `load_balance_metrics.json` — machine-readable load/completion balance summary.',
      '- `tables/best_solution_vehicle_summary.csv` — one row per used vehicle, original ID, compact display ID, route, crew, start interval, load, capacity, travel/service/completion times.',
      '- `tables/customer_assignment.csv` — auditable mapping of every customer to a vehicle and stop order.',
      '- `tables/worker_availability.csv` — worker availability and crew use.',
      '- `tables/per_run_results.csv` — every run’s seed, feasibility, objective and runtime.',
      '- `tables/best_run_operator_diagnostics.csv` — operator contribution in best CT-ALNS run (if logged).','',
      '## Interpretation and model caveats','',
      '- The reported objective is **T_MAX = maximum active-route completion time** under the current project evaluator.',
      '- The current large-instance loader does not enforce Solomon READYTIME/DUEDATE time windows; it replicates service times across crew/time intervals.',
      '- With `return_leg_mode=source`, arcs involving dummy sink 101 have zero distance under source-compatible preprocessing. This can reduce route completion estimates; do not describe the result as physical depot-return travel without a sensitivity run using `--return-leg-mode physical`.',
      '- The evaluator counts crew assignments for all vehicles, including empty routes, when checking worker availability. The separate `active_routes_only` count is shown to expose the difference; do not confuse it with the evaluator’s assigned-all-vehicles check.',
      '- Load balance is reported descriptively. The algorithm minimizes T_MAX, not load variance or vehicle count. A lower T_MAX does not imply perfectly equal loads, and using fewer vehicles is not automatically better unless fleet count is an explicit objective.','']
    (out/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
    summary={'instance':instance,'algorithm':'CT-ALNS-v3','best_seed':best_run.get('seed'),'experiment_runs':len(c_runs),'feasible_runs':sum(bool(r.get('feasible')) for r in c_runs),'best_T_MAX':cstats['best'],'mean_T_MAX':cstats['mean'],'median_T_MAX':cstats['median'],'stdev_T_MAX':cstats['std'],'mean_runtime_seconds':ctime,'active_vehicles':len(active),'customers_served':len(assignment),'fresh_evaluator_feasible':eval_result['feasible'],'return_leg_mode':return_mode,'category_matrix':category,'speed_profile':speed}
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2)); print(f'\nDashboard: {out / "REPORT.md"}')

if __name__=='__main__': main()
