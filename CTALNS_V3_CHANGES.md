# CT-ALNS v3 Evolution and Multi-Objective Expansion

## 1. Context and Motivation

The original baseline (BWO) suffered from limited exploration across interconnected decisions, stagnation in local minima, and blind genetic crossover. Early ALNS prototypes (v1/v2) demonstrated that routing improvements drove most performance gains, while crew and timing decisions lacked targeted operators.

**CT-ALNS v3** directly addressed these deficiencies by introducing bottleneck-route prioritization, regret-2 lookahead reinsertion, rush-hour congestion avoidance, and dedicated critical-vehicle crew/time enumeration.

Subsequently, the framework was expanded with **Novelty 2**, transforming CT-ALNS into a bi-objective solver (**MO-CTALNS**) capable of optimizing both operational completion time ($T_{MAX}$) and logistics cost ($C_{total}$).

---

## 2. Core Architectural Upgrades

1. **`critical_destroy_repair`:** Focuses customer removal on the critical route determining $T_{MAX}$, directly alleviating the bottleneck makespan.
2. **`regret2_destroy_repair`:** Computes the difference between best and second-best insertion positions, preventing difficult-to-place customers from being forced into suboptimal late positions.
3. **`rush_hour_destroy_repair`:** Uses clock arrival calculations to pinpoint customers visited during congested speed intervals, relocating them to off-peak periods or less congested routes.
4. **`critical_crew_time`:** Exhaustively searches all feasible crew combination IDs and departure intervals for the vehicle determining $T_{MAX}$.
5. **Exact MILP Verification:** Corrected algebraic formulation bugs from the original paper (depot exclusion in flow conservation $c5/c6$, start-time aggregation $c17$, and departure-interval mapping $c18/c19$), establishing the true global optimum at $33.812$ for the small instance.
6. **Novelty 2 Multi-Objective Framework:**
   - Operational cost model: vehicle capitalization ($F_k = \$100$), mileage ($\$1.20/\text{unit}$), crew wages, and overtime penalties.
   - Cost-aware operators: `fleet_reduction_destroy_repair` (emptying underutilized vehicles to save $\$100$) and `cost_conscious_crew_repair` (downscaling crew wages on short routes).
   - Pareto tracking: unbounded external archive, NSGA-II crowding distance pruning, Knee point selection, 2D Hypervolume ($HV$), and Zitzler-Thiele Set Coverage $C(A, B)$.
   - MO-BWO baseline for rigorous multi-objective comparative evaluation.

---

## 3. Validation Summary

- **Automated Test Suite:** 30 unit and regression tests passing in 0.79s (`tests/test_novelty2_multiobjective.py`, `tests/test_ctalns.py`, `tests/test_bwo_*.py`, etc.).
- **Single-Objective Benchmark:** CT-ALNS achieves makespan reductions of $32\%\text{--}68\%$ relative to BWO across large instances `R101`, `R201`, `RC101`, and `RC201`.
- **Multi-Objective Benchmark:** MO-CTALNS achieves $100\%$ Set Coverage dominance over MO-BWO ($C(\text{CTALNS}, \text{BWO}) = 1.0$), $+1,580\%$ Hypervolume improvement, and $69\%$ cost reduction on `R101`.
