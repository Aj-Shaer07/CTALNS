This project focuses on the formulation, implementation, and optimization of the **Time-Dependent Vehicle Routing Problem with Flexible Crew Assignment (TD-VRPFCA)**. The project evaluates an exact MILP approach and metaheuristic optimization methods, with **Black Widow Optimization (BWO)** used as the baseline and a proposed **Crew-and-Time Aware Adaptive Large Neighborhood Search (CT-ALNS)** developed for improved performance.

## Objectives

### 1. Formulate and Implement TD-VRPFCA

Formulate and implement the **TD-VRPFCA problem**, incorporating the following key components:

- Time-dependent travel time
- Time-dependent service time
- Fleet assignment
- Crew assignment
- Objective of minimizing \(T_{MAX}\), the maximum completion time

### 2. Implement MILP for Small Instances

Develop a **Mixed-Integer Linear Programming (MILP)** formulation for small-sized instances.

The MILP solutions will be used as an **exact reference** for:

- Validating the implemented problem formulation
- Verifying constraints and feasibility
- Evaluating the performance of optimization methods
- Measuring the solution quality gap of metaheuristics

MILP is restricted to small instances because exact optimization becomes computationally impractical as the problem size increases.

### 3. Implement Black Widow Optimization (BWO)

Implement **Black Widow Optimization (BWO)** as the baseline metaheuristic.

The implementation will reproduce the approach presented in the reference paper for:

- Medium-sized instances
- Large-sized instances
- The same TD-VRPFCA formulation
- The same constraints
- The same objective function

BWO will serve as the baseline for evaluating the effectiveness of the proposed optimization approach.

### 4. Develop CT-ALNS

Develop the proposed **Crew-and-Time Aware Adaptive Large Neighborhood Search (CT-ALNS)**.

The algorithm will include problem-specific destroy-and-repair operators designed to address the three tightly coupled components of TD-VRPFCA:

- **Route:** Modify and improve vehicle routes
- **Crew:** Reassign and optimize crew allocations
- **Time:** Adjust schedules and time-dependent decisions

An **adaptive operator selection mechanism** dynamically selects operators based on their search performance via roulette-wheel scoring.

### 5. Novelty 2: Multi-Objective Time–Cost Trade-Off Optimization

Extend the original makespan-only problem into a bi-objective formulation balancing operational speed against real-world logistics costs:

$$\min_{S} \; \Big( T_{MAX}(S), \; C_{total}(S) \Big)$$

where $C_{total} = C_{vehicle} + C_{distance} + C_{crew} + C_{overtime}$.

- **MO-CTALNS:** Multi-Objective CT-ALNS equipped with 14 operators (including cost-conscious fleet reduction and crew reassignment), Chebyshev scalarized simulated annealing, and NSGA-II style crowding distance pruning.
- **MO-BWO Baseline:** Multi-Objective Black Widow Optimization baseline using non-dominated sorting and crowding distance diversity preservation.

### 6. Experimental Evaluation & Metrics

Conduct comprehensive evaluations across both single-objective ($T_{MAX}$) and multi-objective ($T_{MAX}, C_{total}$) formulations using:
- **Single-Objective:** Solution quality, consistency, convergence curves, and wall-clock execution time.
- **Multi-Objective:** Hypervolume ($HV$), Zitzler-Thiele Set Coverage $C(A, B)$, and extreme plan trade-offs (Fastest vs. Cheapest vs. Knee compromise).

## Overall Workflow

```text
TD-VRPFCA Problem Formulation
        │
        ├── MILP (Gurobi)
        │    └── Small Instances ── Exact Reference Benchmarks (T_MAX = 33.81)
        │
        ├── Novelty 1: Single-Objective Optimization (min T_MAX)
        │    ├── BWO Baseline (Black Widow Optimization)
        │    └── CT-ALNS (12 Coordinated Destroy/Repair Operators)
        │
        └── Novelty 2: Multi-Objective Optimization (min T_MAX, C_total)
             ├── MO-BWO Baseline (Pareto Ranking + Crowding Distance)
             └── MO-CTALNS (14 Operators + Chebyshev SA + Pareto Archive)
                      │
                      ▼
              Evaluation & Metrics
                      │
                      ├── Single-Obj: Best/Mean/Std T_MAX, Speedup, Gap to MILP
                      └── Multi-Obj: Hypervolume (HV), Set Coverage C(A,B), Pareto Fronts
```

## How to Run

### Setup Virtual Environment
Make sure to activate your virtual environment before running the scripts:
```bash
source venv/bin/activate
```

### Master Benchmark Suite: Run and Compare All Instances in One Command

Run all benchmark instances (`R101`, `R201`, `RC101`, `RC201`) across multiple seeds, runs, and iterations in a single command, generating cross-instance comparison tables and visual dashboards:

```bash
# Run both Novelty 1 (BWO vs CT-ALNS) and Novelty 2 (MO-CTALNS) on all instances:
python run_benchmark_suite.py --instances R101 R201 RC101 RC201 --runs 10 --iterations 50 --seed 42 --mode both
```
*Options:*
- `--instances`: Specify instances (default: `R101 R201 RC101 RC201`).
- `--runs`: Number of independent random seeds per instance (e.g. `5`, `10`, `20`).
- `--iterations`: Search iterations per run (e.g. `50`, `100`).
- `--seed`: Base random seed (e.g. `42`).
- `--mode`: `comparison` (Novelty 1 only), `multiobjective` (Novelty 2 only), or `both`.
- Outputs generated in `results/benchmark_suite/MASTER_COMPARISON_REPORT.md` with cross-instance bar charts and Pareto subplots.

### Single-Instance Comparison: BWO vs CT-ALNS

To run both BWO and CT-ALNS side-by-side on any individual instance:

```bash
python run_comparison.py --instance R101 --runs 10 --iterations 50 --seed 42
```


### 1. Run Exact MILP (Gurobi)

Before running MILP, make sure Gurobi is set up (see `gurobi.md`).

Run the exact small instance solver comparing the corrected formulation against the paper's original formulation:
```bash
python run_milp.py --mode both --time-limit 300
```
*Note: The corrected formulation proves the true global minimum is **33.8125**, fixing the paper's single-vehicle TSP bug ($c5/c6$), start-time bug ($c17$), and departure-time interval bug ($c18/c19$).*

### 2. Run BWO (Baseline Metaheuristic)

**Small Instance**:
```bash
python run_experiments.py --kind small --runs 10 --seed 42 --output results/bwo_small
```

**Large Instance (e.g., R101)**:
```bash
python run_experiments.py --kind large --instance R101 --category catheg.txt --speed t_dep.txt --runs 5 --seed 42 --output results/bwo_R101
```

**All 24 Large Configurations Sweep**:
```bash
python run_experiments.py --kind large --all-large-configs --runs 1 --seed 42 --output results/bwo_all_configs
```

### 3. Run CT-ALNS (Novel Advanced Metaheuristic)

Our CT-ALNS features 12 specialized operators:
- **Routing:** Random destroy, worst marginal destroy, related destroy, critical route bottleneck destroy, rush-hour time-dependent destroy, regret-2 repair, and greedy repair.
- **Crew & Time:** Route relocate, route swap, crew reassignment, departure retiming, joint crew-time move, and critical crew-time enumeration.
- **Search Engine:** Simulated annealing acceptance and adaptive roulette-wheel operator weight adjustments.

**Small Instance**:
```bash
python run_ctalns.py --kind small --runs 5 --iterations 50 --seed 42 --output results/ctalns_small
```

**Large Instance (e.g., R101)**:
```bash
python run_ctalns.py --kind large --instance R101 --category catheg.txt --speed t_dep.txt --runs 5 --iterations 100 --seed 42 --output results/ctalns_R101
```

### 4. Single-Command Baseline vs CT-ALNS Comparison

Run both BWO and CT-ALNS across multiple seeds in a single automated step:
```bash
python run_comparison.py --instance R101 --runs 20 --iterations 100 --seed 42
```

### 5. Run Novelty 2: Time–Cost Multi-Objective CT-ALNS (MO-CTALNS)

Novelty 2 extends the formulation from makespan-only optimization to bi-objective optimization, explicitly exposing the trade-off between delivery completion time ($T_{MAX}$) and operational cost ($C_{total}$):

$$\min_S \Big( T_{MAX}(S), \; C_{total}(S) = C_{vehicle} + C_{distance} + C_{crew} + C_{overtime} \Big)$$

Execute the multi-objective Pareto search:
```bash
python run_multiobjective.py --instance R101 --iterations 100 --seed 42
```

Outputs generated:
* `results/multiobjective_R101/PARETO_REPORT.md` (Strategic comparison: Fastest vs Knee vs Cheapest plans)
* `results/multiobjective_R101/figures/pareto_frontier.png` (2D Pareto trade-off curve)
* `results/multiobjective_R101/figures/convergence_multiobjective.png` (Hypervolume growth)
* `results/multiobjective_R101/pareto_front.csv` and `pareto_front.json`

### 6. Head-to-Head Multi-Objective Benchmark: MO-CTALNS vs. MO-BWO

Directly benchmark the proposed **MO-CTALNS** against the **MO-BWO** baseline on the identical bi-objective problem:

$$\min_S \Big( T_{MAX}(S), \; C_{total}(S) \Big)$$

This executes both algorithms across multiple random runs, computes the **Common Hypervolume ($HV$)**, calculates the **Zitzler-Thiele Set Coverage metric $C(A, B)$**, and generates an overlapping Pareto frontier chart:

```bash
python compare_mo_algorithms.py --instance R101 --runs 5 --iterations 50 --seed 42
```

Outputs generated:
* `results/mo_comparison_R101/MO_COMPARISON_REPORT.md` (Executive summary with HV, Set Coverage, and extreme plan deltas)
* `results/mo_comparison_R101/figures/mo_comparison_pareto_fronts.png` (Overlapping 2D Pareto frontiers showing MO-CTALNS dominance)

### 7. Generate Presentation Dashboard & Analysis Plots

Generate a publication-ready report, convergence trajectories, route visualization, load-balancing diagnostics, and audit CSV tables:
```bash
python analyze_results.py \
  --ctalns results/comparison_R101/ctalns_R101.json \
  --bwo results/comparison_R101/bwo_R101.json \
  --out results/comparison_R101/dashboard
```

### 8. Run Automated Regression Tests

Run the complete test suite (30 unit & regression tests across both novelties):
```bash
pytest -v
```

