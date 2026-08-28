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

An **adaptive operator selection mechanism** will be implemented to dynamically select operators based on their search performance.

### 5. Experimental Comparison

Conduct comprehensive experiments comparing **BWO** and **CT-ALNS** on the same benchmark and real-world instances.

The algorithms will be evaluated using the following criteria:

| Evaluation Criterion | Description |
|---|---|
| Solution Quality | Quality of the obtained \(T_{MAX}\) solutions |
| Consistency | Stability of results across multiple runs |
| Computational Time | Time required to obtain solutions |
| Convergence | Rate at which solution quality improves |
| Scalability | Performance as instance size increases |

## Overall Workflow

```text
TD-VRPFCA Formulation
        │
        ├── MILP
        │    └── Small Instances
        │         └── Exact Reference Solutions
        │
        ├── BWO
        │    └── Medium & Large Instances
        │
        └── CT-ALNS
             ├── Route Destroy/Repair
             ├── Crew Destroy/Repair
             ├── Time Destroy/Repair
             └── Adaptive Operator Selection
                      │
                      ▼
              Experimental Evaluation
                      │
                      ├── Solution Quality
                      ├── Consistency
                      ├── Computational Time
                      ├── Convergence
                      └── Scalability
