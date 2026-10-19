# TD-VRPFCA — clean BWO baseline

**Final handoff/status:** see [`FINAL_HANDOFF.md`](FINAL_HANDOFF.md) for validation performed, reproduction limits, and safe experiment commands.

This repository is a compact, runnable baseline for the project that will later
compare BWO with CT-ALNS. It is built primarily from the **friend's
`CTALNS-main` implementation**, cross-checked against the public authors'
repository and the 2025 paper. It deliberately includes only the instances used
in the project: the 10-customer small instance and large instances R101, R201,
RC101, RC201 with their 24 time/category configurations.

## Structure

```text
TD-VRPFCA/
├── data/
│   ├── small/              # Original source files + explicit reconstructed assumptions
│   └── large/              # R101, R201, RC101, RC201 + D/time/category files
├── tdvrpfca/
│   ├── model.py            # Shared solution and time-dependent evaluator
│   ├── data.py             # Shared loaders and preprocessing
│   └── bwo.py              # Friend-based BWO with documented software fixes
├── tests/
├── run_experiments.py      # Single runner for small or large experiments
├── REPRODUCTION_NOTES.md   # Provenance and discrepancies
└── requirements.txt
```

The repository now includes an **initial CT-ALNS research prototype** in
`tdvrpfca/ctalns.py` and `run_ctalns.py`. Its operator portfolio and limitations
are documented in [`CTALNS_DESIGN.md`](CTALNS_DESIGN.md). It reuses the same
`Instance`, `Solution`, and `evaluate_solution()` as BWO; the evaluator is still
provisional pending the paper-alignment audit.

## Setup

Python 3.10+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest -q
```

## Run Exact MILP (Gurobi)

Compare the mathematically corrected multi-vehicle formulation against the paper's original formulation:

```bash
python run_milp.py --mode both --time-limit 300
```
This reproduces the exact global optimal baseline on the small instance ($T_{MAX} = 33.812$).

## Run BWO

Small instance, friend-runner settings (population 50, 10 iterations,
procreation 0.60, cannibalism 0.50, mutation 0.10):

```bash
python run_experiments.py --kind small --runs 10 --seed 42
```

Large instance R101, source-compatible settings (population 20, 100 iterations,
procreation 0.40, cannibalism 0.50, mutation 0.05):

```bash
python run_experiments.py --kind large --instance R101 --category catheg.txt --speed t_dep.txt --runs 5 --seed 42
```

Run the 24 large configurations used by the project (4 base instances × 2
category matrices × 3 speed profiles):

```bash
python run_experiments.py --kind large --all-large-configs --runs 1 --seed 42
```

The JSON and CSV reports are written to `results/bwo_runs.json` and
`results/bwo_runs.csv` by default. Override the destination with `--output`.

## Reproduction modes and assumptions

The default settings preserve the friend's current BWO encoding and source
conventions as closely as possible:

- Chromosome: route sequence with depot separators, counts of each of the
  eight crew combinations, and one shared start-interval gene.
- Route crossover, route-swap mutation, parent/offspring cannibalism, and
  population truncation follow the friend's implementation.
- Obvious software failures are corrected: `list.append()` is not assigned to
  a variable, parent selection does not rely on an undefined `self.pop`, route
  initialization has bounded retries, and the final population is checked for
  a new global best.
- `--time-mode per_vehicle` enables one start-interval gene per vehicle. This
  follows the paper's vehicle-specific interpretation, but it is a different
  search space from the friend's shared-interval chromosome. Do not mix results
  from the two modes in one baseline table.

### Small instance

The original `Small Intance/C.txt` has only five crew rows, while Table 3 of the
paper defines eight combinations. `data/small/crew_combinations.csv` completes
the table using the paper, in the worker order used by the friend's loader:
DP, Dr, MFDP. The original `C.txt` is included unchanged as source evidence.

The original small data do not include worker availability. The friend's small
experiment runner injects `{DP: 4, Dr: 2, MFDP: 2}`; this project records that
assumption in `worker_availability.json` rather than silently inventing it in
the loader. Confirm this assumption against your project notes before final
reporting.

`--small-travel-factor 1` reproduces the friend/public `Fitness.py` calculation
`distance / speed`. If distance is in km, speed in km/hour, and service/clock
times in minutes, the unit-consistent travel term would be
`60 * distance / speed`. The latter can be tested explicitly with
`--small-travel-factor 60`. These modes produce different objective values and
must be reported separately. The default is `1` for compatibility with the
friend's previously reported baseline.

### Large instances

The loader uses the original Solomon-style files and the same preprocessing
conventions documented in the friend's code:

- 25 vehicles; capacities: R101=200, R201/RC101/RC201=1000.
- Worker availability `{DP: 50, Dr: 20, MFDP: 20}` and crew table from `D.txt`.
- Solomon `SERVICETIME` repeated across crew combinations and intervals.
- Three 480-minute intervals and category-based time-dependent speeds.
- Missing/non-positive speed lookups use the source's 0.3 fallback.
- `--return-leg-mode source` preserves the authors' public large-instance
  preprocessing where arcs involving dummy node 101 have zero distance.
  `--return-leg-mode physical` is an alternative sensitivity check with a
  physical return distance; do not mix these results with source mode.
- Solomon READYTIME/DUEDATE time windows are not enforced, matching the
  friend's BWO evaluator and the public authors' large-instance TS preprocessing.

## Important interpretation

This is a **source-informed, reproducible project baseline**, not a claim that
the paper's results have already been reproduced exactly. The paper, authors'
public code, and friend's implementation differ in some details. Those are
documented in `REPRODUCTION_NOTES.md`. Historical values should only be compared
after instance, time convention, start-interval representation, and algorithm
parameters are matched.


## Run CT-ALNS prototype

Small-instance smoke run:

```bash
python run_ctalns.py --kind small --runs 2 --iterations 5 --seed 42 --output results/ctalns_small_smoke
```

Large-instance smoke run (use modest iterations first):

```bash
python run_ctalns.py --kind large --instance R101 --category catheg.txt --speed t_dep.txt --runs 1 --iterations 10 --seed 42 --output results/ctalns_R101_smoke
```

This is an early prototype. Do not interpret its smoke-run objective values as a
performance claim. See `CTALNS_DESIGN.md` before designing full experiments.

## Generate a clean results dashboard (CT-ALNS + BWO)

After you have experiment JSON files, generate a presentation-ready report, plots,
load-balancing diagnostics, and auditable CSV tables with:

```bash
python analyze_results.py \
  --ctalns results/ctalns_v3_R101_20x100_combined.json \
  --bwo results/bwo_R101_per_vehicle_20x100.json \
  --out results/presentation
```

Then open `results/presentation/REPORT.md`. It embeds the generated plots and links
conceptually to the CSV/JSON audit tables in the same folder. The analysis script
re-evaluates the best CT-ALNS solution using the project evaluator before reporting
it, checks customer coverage, preserves original vehicle IDs, and assigns compact
**display-only** vehicle labels for readable charts. It reports load balance and
completion-time balance separately because the current objective minimizes `T_MAX`,
not load variance or fleet size.

The generated bundle includes convergence and run-distribution plots, a route map,
per-vehicle load/capacity/completion plots, operator diagnostics, per-run results,
customer-to-vehicle assignments, and worker availability tables. `REPORT.md` also
states the current modeling caveats: Solomon time windows are not enforced, the
source-compatible return leg to dummy sink 101 has zero distance, and the evaluator
counts crew assignments on empty vehicles for worker-availability checks.

Install the plotting dependency if needed:

```bash
python -m pip install matplotlib numpy
```

**Important:** results from the included JSON are a saved experiment snapshot. To
regenerate them from fresh runs, first run `run_ctalns.py` and `run_experiments.py`
with explicitly matched instance, time mode, return-leg mode, data files, and budgets;
then pass those fresh output files to `analyze_results.py`.
