# CT-ALNS and MO-CTALNS: Technical Design and Operator Architecture

## 1. Research Motivation

The Time-Dependent Vehicle Routing Problem with Flexible Crew Assignment (TD-VRPFCA) couples three highly sensitive decision layers:
1. **Routing:** Which customers each vehicle visits, and in what order.
2. **Crew Assignment:** Which eligible crew (Driver, Delivery Person, Multi-Functional Delivery Person) operates each vehicle, subject to availability and overtime limits.
3. **Departure Timing:** When each vehicle departs, considering time-dependent travel speeds and congestion intervals.

Standard metaheuristics like Black Widow Optimization (BWO) rely on random crossover and cannibalism, which frequently shatter route structures, violate capacity/time constraints, and struggle to coordinate crew and timing choices.

**CT-ALNS (Crew-and-Time Aware Adaptive Large Neighborhood Search)** resolves these bottlenecks by treating routing, crew assignment, and departure scheduling as interconnected decisions through problem-specific destroy-and-repair neighborhoods and adaptive search steering.

---

## 2. Complete Operator Portfolio (14 Operators)

CT-ALNS integrates 14 specialized operators designed specifically for TD-VRPFCA:

### A. Routing Destroy & Repair
| Operator | Target | Description |
|---|---|---|
| `random_destroy_repair` | Diversification | Removes a random subset of customers and reinserts them at minimum cost positions. |
| `worst_destroy_repair` | Efficiency | Removes customers with the highest marginal distance/time contribution to the route. |
| `related_destroy_repair` | Clustering | Removes geographically related customers (using depot distance proxy) to facilitate route reorganization. |
| `critical_destroy_repair` | Bottleneck | Directly targets the bottleneck route currently determining $T_{MAX}$, stripping high-marginal customers. |
| `rush_hour_destroy_repair` | Traffic Avoidance | Identifies arrival timestamps falling within congested speed intervals and relocates affected customers. |
| `regret2_destroy_repair` | Lookahead | Inserts pending customers prioritizing those with the largest gap between best and second-best insertion positions. |
| `route_relocate` | Local Search | Relocates a single customer from one vehicle to another feasible vehicle position. |
| `route_swap` | Local Search | Swaps two customers across different vehicle routes. |

### B. Crew & Timing Optimization
| Operator | Target | Description |
|---|---|---|
| `crew_reassignment` | Feasibility & Speed | Explores alternative crew combination IDs for selected vehicles while preserving worker availability. |
| `time_retiming` | Congestion Shift | Evaluates alternative departure intervals to shift routes into faster travel-time regimes. |
| `joint_crew_time` | Coupled Decisions | Simultaneously perturbs both crew ID and departure interval for a vehicle. |
| `critical_crew_time` | Bottleneck Resolution | Exhaustively enumerates all feasible crew $\times$ departure interval combinations for the bottleneck vehicle. |

### C. Novelty 2 Cost-Aware Multi-Objective Operators
| Operator | Target | Description |
|---|---|---|
| `fleet_reduction_destroy_repair` | Capital Cost Reduction | Identifies vehicles with the lowest customer volume/load, attempts complete route evacuation, and saves the $\$100$ fixed vehicle cost if all customers can be feasibly absorbed. |
| `cost_conscious_crew_repair` | Wage Optimization | Analyzes route completion duration and tests cheaper crew combinations (e.g. replacing expensive MFDP with DP/Dr) when the route finishes well within shift limits. |

---

## 3. Search Engine & Acceptance Mechanisms

### Single-Objective CT-ALNS (Makespan Minimization $\min T_{MAX}$)
- **Simulated Annealing Acceptance:**
  $$\Pr(\text{accept}) = \exp\left(-\frac{\Delta}{T}\right), \quad \text{where } \Delta = T_{MAX}(S') - T_{MAX}(S)$$
  Permits controlled exploration of worsening moves early in the search, with geometric temperature cooling $T \leftarrow T \cdot \alpha$.
- **Adaptive Operator Weighting (Roulette Wheel):**
  $$P_i = \frac{w_i}{\sum_j w_j}$$
  Operator weights are dynamically updated based on search rewards:
  $$w_i \leftarrow \max\left(w_{\min}, \; (1-\rho)w_i + \rho \cdot r_i\right)$$
  where large rewards are awarded for discovering new global best solutions and moderate rewards for accepted improvements.

### Novelty 2 Multi-Objective Engine (MO-CTALNS: $\min \{ T_{MAX}, C_{total} \}$)
- **Chebyshev Scalarized Simulated Annealing:**
  Dynamically samples weight vectors $(\lambda_1, \lambda_2) \in [0, 1]^2$ with $\lambda_1 + \lambda_2 = 1$, minimizing the augmented Chebyshev distance to the current ideal point $(z_1^*, z_2^*)$:
  $$g(S \mid \lambda, z^*) = \max\left\{ \lambda_1 \frac{T_{MAX}(S) - z_1^*}{z_1^{nad} - z_1^*}, \; \lambda_2 \frac{C_{total}(S) - z_2^*}{z_2^{nad} - z_2^*} \right\} + \rho_{ch} \sum_{i=1}^2 \lambda_i \frac{f_i(S) - z_i^*}{z_i^{nad} - z_i^*}$$
- **Pareto Archive with NSGA-II Crowding Distance Pruning:**
  Maintains an unbounded external non-dominated set. When bounded capacity is enforced, boundary extremes are protected and solutions with smallest crowding distance are pruned to guarantee maximum frontier spread.
- **Knee Solution Detection:**
  Identifies the most balanced compromise plan using normalized Euclidean distance to the utopian ideal point $(z_1^*, z_2^*)$.

---

## 4. Multi-Objective Evaluation Metrics

1. **Hypervolume ($HV$):**
   Computes the measure of the objective space enclosed between the non-dominated Pareto front and a fixed reference point $R = (1.1 \cdot T_{MAX}^{nadir}, \; 1.1 \cdot C_{total}^{nadir})$. Higher hypervolume reflects superior convergence and diversity.
2. **Zitzler-Thiele Set Coverage Metric $C(A, B)$:**
   Measures the proportion of solutions in set $B$ strictly Pareto-dominated by at least one solution in set $A$:
   $$C(A, B) = \frac{|\{ b \in B \mid \exists a \in A: a \prec b \}|}{|B|}$$
   $C(\text{MO-CTALNS}, \text{MO-BWO}) = 1.0$ indicates total mathematical dominance.

---

## 5. Software Validation

- Complete unit test suite: **30 unit tests passing in 0.79s**.
- Exact mathematical benchmark: Small instance achieves $T_{MAX} = 34.31$ (within 1.5% of the exact Gurobi MILP optimal of $33.81$).
- Benchmarked on all 4 standard Solomon large instances (`R101`, `R201`, `RC101`, `RC201`).
