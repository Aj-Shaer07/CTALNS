# CT-ALNS novelty: design and status

## Research question
Can a component-tailored Adaptive Large Neighborhood Search improve the current BWO search on TD-VRPFCA by adapting search effort to three coupled decision layers: customer routes, crew composition, and vehicle start intervals?

## Representation and objective
CT-ALNS uses the shared `Solution` representation:

- `routes[k]`: ordered customers assigned to vehicle `k`;
- `crew[k]`: crew-combination ID assigned to vehicle `k`;
- `start_intervals[k]`: departure interval for vehicle `k`.

Every candidate is evaluated by the existing `evaluate_solution()` function. The objective remains minimization of `T_MAX`; feasibility uses the exact constraints implemented by that evaluator. This ensures BWO and CT-ALNS can be compared on a common evaluator, although that evaluator itself still needs the paper-alignment audit described in `REPRODUCTION_NOTES.md`.

## Current operator portfolio

| Operator | Target | Action |
|---|---|---|
| Random route destroy + greedy repair | Routing | Remove a random subset of customers and reinsert them at the best feasible route/position found by the evaluator |
| Worst route destroy + greedy repair | Routing | Remove customers with high approximate marginal distance contribution and reinsert them |
| Related route destroy + greedy repair | Routing | Remove customers with similar depot-distance proxy and reinsert them |
| Critical route destroy + greedy repair | Bottleneck Routing | Prioritize removing high-marginal-cost customers from the bottleneck route determining T_MAX |
| Rush-hour destroy + regret-2 repair | Time-Dependent Routing | Target customers traversed during slow, congested rush-hour speed intervals, reinserting via regret-2 |
| Regret-2 destroy + repair | Regret Routing | Destroy worst-marginal customers and reinsert prioritizing high-regret insertion gaps |
| Route relocate | Local search | Relocate a customer to an alternative vehicle/position |
| Route swap | Local search | Swap two customers across routes |
| Crew reassignment | Crew | Try alternative crew IDs for a selected vehicle and keep the best feasible choice |
| Time retiming | Departure time | Try alternative start intervals for a selected vehicle |
| Joint crew-time move | Coupled crew/time | Apply crew and interval improvement moves together |
| Critical crew-time | Bottleneck Crew/Time | Enumerate all crew x interval combinations specifically for the vehicle determining T_MAX |

The relatedness proxy is intentionally simple because the current shared `Instance` model does not retain explicit coordinates. It uses distance from the depot. A future improvement can add coordinates to the data model or use time-dependent travel/service signatures for richer relatedness.

## Adaptive mechanism
Operator selection is roulette-wheel sampling using weights

\[P_i = \frac{w_i}{\sum_j w_j}.\]

After applying an operator, the candidate is evaluated. Improving the current solution earns a reward; discovering a new global best earns a larger reward. The operator score and weight are updated with reaction factor \(\rho\):

\[s_i \leftarrow (1-\rho)s_i + \rho r_i,\]

\[w_i \leftarrow \max(w_{\min},(1-\rho)w_i+\rho\max(w_{\min},s_i)).\]

A simulated-annealing acceptance rule permits some worsening moves:

\[\Pr(\text{accept}) = \exp(-\Delta/T),\quad \Delta>0.\]

The temperature cools geometrically. This is an initial adaptive scheme; operator reward calibration, segment removal, crew-role-specific neighborhoods, and richer acceptance criteria are future experimental choices, not claimed completed features.

## Initial validation
- Automated test suite: 9 tests passed in the development environment.
- Small-instance smoke run: 2 runs × 5 iterations completed and returned feasible solutions under the current evaluator.
- These are software smoke tests only, not evidence of superiority or paper-level reproduction.

## Important limitations before publication
1. The evaluator ignores Solomon ready/due time windows and uses the documented source-compatible return-leg convention by default.
2. The current service-time table is constant across intervals for large instances.
3. Crew reassignment is tested against current worker-availability constraints; no extra constraints beyond the shared evaluator are invented here.
4. The current initialization uses the BWO feasible initializer. This is deliberate for a controlled initial comparison, but a final experiment should either use the same initial solution(s) for both methods or explicitly report initialization costs and policies.
5. Current CT-ALNS is a prototype. It must be benchmarked over multiple seeds and against BWO under identical instances, evaluator settings, and runtime/iteration budgets. Ablation experiments should disable route, crew, time, and adaptive weighting separately.

## Recommended experimental sequence
1. Validate the evaluator/formulation against the paper and decide the time-window and return-leg convention.
2. Freeze a common evaluator and seed protocol.
3. Run smoke tests on small, then one large configuration.
4. Run BWO and CT-ALNS with identical instance files and multiple seeds.
5. Report best/mean/std of `T_MAX`, feasibility rate, runtime, convergence, and per-operator usage/reward.
6. Run ablations: no crew operators, no time operators, fixed uniform operator weights, and full CT-ALNS.
