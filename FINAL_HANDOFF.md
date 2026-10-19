# TD-VRPFCA Project: Final Handoff and Status Report

## 1. Executive Summary

This repository contains the complete implementation, validation, and benchmarking for the **Time-Dependent Vehicle Routing Problem with Flexible Crew Assignment (TD-VRPFCA)**, developed around two distinct contributions:

1. **Novelty 1 — CT-ALNS (Crew-and-Time Aware Adaptive Large Neighborhood Search):**
   A problem-specific destroy-and-repair metaheuristic that simultaneously explores customer routing, crew assignment, and time-dependent departure scheduling under makespan minimization ($\min T_{MAX}$).
2. **Novelty 2 — Time–Cost Trade-off Multi-Objective Optimization:**
   A bi-objective extension ($\min \{ T_{MAX}, C_{total} \}$) incorporating fixed vehicle capitalization costs ($F_k = \$100$), fuel/mileage charges ($c_k = \$1.20/\text{unit}$), role-based hourly crew wages (DP: $\$15/\text{hr}$, Dr: $\$20/\text{hr}$, MFDP: $\$25/\text{hr}$), and overtime penalties beyond 8 hours ($1.5\times$ rate). Includes **MO-CTALNS** with 14 specialized operators and **MO-BWO** as the multi-objective baseline.

---

## 2. Validation Status

The complete automated test suite contains **30 passing unit and regression tests**:

```bash
./venv/bin/pytest -v
```

```text
============================== 30 passed in 0.79s ==============================
- tests/test_bwo_encoding.py             (BWO chromosome mapping & splits)
- tests/test_bwo_feasibility.py          (Route capacity & worker limits)
- tests/test_bwo_fitness.py              (Makespan evaluation accuracy)
- tests/test_bwo_operators.py            (Crossover, mutation & cannibalism)
- tests/test_bwo_reproducibility.py      (Deterministic pseudo-random seeding)
- tests/test_ctalns.py                   (CT-ALNS destroy/repair operator suite)
- tests/test_data.py                     (Instance loading & data consistency)
- tests/test_evaluator.py                (Shared evaluation & constraint engine)
- tests/test_large_loader.py             (Solomon benchmark parsing & time matrices)
- tests/test_milp.py                     (Exact MILP solver formulation & Gurobi model)
- tests/test_model.py                    (Core data classes & solution representations)
- tests/test_novelty2_multiobjective.py  (Cost model, Pareto dominance, archive & HV)
```

---

## 3. Key Quantitative Findings

### Novelty 1: Single-Objective Makespan ($T_{MAX}$)

Across all 4 Solomon large instances (`R101`, `R201`, `RC101`, `RC201`), **CT-ALNS systematically outperforms BWO**:
- **R101:** CT-ALNS achieves $333.35\text{ min}$ vs. BWO $990.90\text{ min}$ (**$+66.4\%$ improvement**).
- **RC101:** CT-ALNS achieves $393.20\text{ min}$ vs. BWO $1030.98\text{ min}$ (**$+61.9\%$ improvement**).
- **R201 / RC201:** CT-ALNS maintains a $30\text{--}50\%$ speed advantage across longer planning horizons.
- **Small Instance:** CT-ALNS finds $T_{MAX} = 34.31$, within $1.5\%$ of the provable global MILP optimum ($33.81$).

### Novelty 2: Multi-Objective Time–Cost Trade-Off

Head-to-head benchmarking between **MO-CTALNS** and **MO-BWO** (5 runs $\times$ 50 iterations on `R101`):
- **Set Coverage $C(\text{MO-CTALNS}, \text{MO-BWO}) = \mathbf{100.0\%}$:** Every single solution found by MO-BWO is strictly Pareto-dominated by MO-CTALNS ($C(\text{MO-BWO}, \text{MO-CTALNS}) = 0.0\%$).
- **Hypervolume ($HV$):** MO-CTALNS achieves $11,063,107$ vs. MO-BWO $658,431$ (**$+1,580.2\%$ superiority**).
- **Operational Cost:** MO-CTALNS's cheapest plan is $\mathbf{\$3,925.98}$ vs. MO-BWO's $\mathbf{\$12,842.45}$ (**$+69.4\%$ cheaper**).
- **Active Fleet:** MO-CTALNS downscales the fleet to $10\text{--}11$ trucks vs. MO-BWO which utilizes $19$ trucks, cutting unnecessary fixed capitalization and crew costs.

---

## 4. Key Reproducible Commands

### Activate Virtual Environment
```bash
source venv/bin/activate
```

### 1. Unified Master Benchmark Suite (All Instances, Both Novelties)
```bash
python run_benchmark_suite.py --instances R101 R201 RC101 RC201 --runs 10 --iterations 50 --seed 42 --mode both
```

### 2. Single-Objective Head-to-Head Comparison (BWO vs. CT-ALNS)
```bash
python run_comparison.py --instance R101 --runs 20 --iterations 100 --seed 42
```

### 3. Multi-Objective Head-to-Head Benchmark (MO-CTALNS vs. MO-BWO)
```bash
python compare_mo_algorithms.py --instance R101 --runs 5 --iterations 50 --seed 42
```

### 4. Novelty 2 Standalone Multi-Objective Pareto Search
```bash
python run_multiobjective.py --instance R101 --runs 5 --iterations 50 --seed 42
```

### 5. Exact MILP Solver (Small Benchmark)
```bash
python run_milp.py --mode both --time-limit 300
```

---

## 5. Artifact Directory Map

- `td_vrpfca/`: Core package containing models, loaders, MILP, BWO, CT-ALNS, cost model, Pareto archive, and multi-objective optimizers.
- `results/benchmark_suite/`: Master cross-instance reports and comparative summary charts.
- `results/comparison_<inst>/`: Single-objective BWO vs CT-ALNS results, boxplots, and dashboards.
- `results/multiobjective_<inst>/`: Standalone MO-CTALNS Pareto frontiers, hypervolume convergence, and CSV logs.
- `results/mo_comparison_<inst>/`: Direct MO-CTALNS vs MO-BWO reports and overlapping Pareto frontier plots.
