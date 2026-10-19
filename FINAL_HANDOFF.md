# TD-VRPFCA baseline — final handoff and status

## What this bundle contains

This is the consolidated, runnable BWO baseline package for the TD-VRPFCA project. It includes the instance files, loaders, shared evaluator, BWO implementation, experiment runner, tests, and reproduction notes. The code is based on the available friend implementation and public-source-informed preprocessing; it is not presented as an exact reproduction of every result in the 2025 paper.

## Validation performed for this handoff

Command:

```bash
python -m pytest -q
```

Result: **8 tests passed** in the current environment.

These are software and smoke-test checks. They do not establish that the published paper's numerical results have been reproduced.

## Important interpretation limits

Before using results in the final report, preserve these distinctions:

1. **Objective/metric:** the evaluator reports `T_MAX` (maximum route completion time). The paper's Table 12 is titled “Average travel times and CPU”; do not treat its travel-time column as a published `T_MAX` target without checking the table definition and equations.
2. **Time windows:** Solomon `READYTIME` and `DUEDATE` fields are loaded from the source rows but are not enforced by the current evaluator. Therefore “feasible” means feasible under this implementation's checks, not necessarily feasible under all paper constraints.
3. **Crew and time genes:** the current BWO mutation changes route order only; crew and start-time genes are not directly mutated. This limits the search over those decisions.
4. **Shared start interval:** the default is `--time-mode shared`, so all vehicles share one start interval. `--time-mode per_vehicle` changes the search space and must be reported as a separate mode.
5. **Return leg:** default `--return-leg-mode source` preserves the source convention where arcs involving the dummy sink node have zero distance. `physical` is a different sensitivity setting; do not combine results from these modes.
6. **Travel-time units:** the small-instance compatibility setting uses `distance / speed`; the unit-consistent alternative may require a factor of 60 depending on the units of the supplied distance, speed, and clock values. The chosen factor must be stated.
7. **Paper parameter discrepancy:** Appendix A and Table 12 appear to describe different parameter settings. Do not claim one parameter combination simultaneously reproduces both unless the original table is resolved directly.
8. **Repeated R/RC results:** if RC101 and RC201 produce identical summaries, inspect the selected input files, configuration labels, and output rows before interpreting the equality as a result.

## Reproducible commands

Install and test:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

Run one large-instance configuration with explicit output paths:

```bash
python run_experiments.py \
  --kind large \
  --instance R101 \
  --category catheg.txt \
  --speed t_dep.txt \
  --npop 20 \
  --iterations 100 \
  --procreation 0.4 \
  --cannibalism 0.5 \
  --mutation 0.1 \
  --runs 20 \
  --seed 42 \
  --output results/R101_catheg_tdep_baseline
```

Run all 24 large-instance configurations as a smoke/experiment sweep:

```bash
python run_experiments.py --kind large --all-large-configs --runs 1 --seed 42 \
  --output results/all_large_configs
```

Check `python run_experiments.py --help` for the exact supported flags in this version. Use distinct output names for different parameter settings so results are not overwritten.

## Baseline status

**Ready as a runnable, documented project baseline; not yet verified as a faithful numerical reproduction of the paper.** The next step should be to resolve the paper's exact metric and modelling conventions, then align and test the evaluator and BWO operators before claiming paper-level reproduction or comparing against CT-ALNS.
