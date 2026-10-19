# CT-ALNS v3 changes and validation

## Why v3 exists

The v2 R101 diagnostic showed that routing destroy/repair was responsible for observed improvements, while crew/time operators had little evidence of useful contribution in that short run. v3 adds explicit bottleneck-route targeting, regret-2 reinsertion, and a joint crew/start-interval neighborhood focused on the route currently determining `T_MAX`.

## Changes

1. `critical_destroy_repair`: remove high marginal-cost customers from the route with the maximum completion time first, then fill any remaining removal quota from other routes.
2. `regret2_destroy_repair`: select the pending customer with the largest gap between its best and second-best insertion candidates. The evaluator's `check_customer_coverage=False` mode is used only while customers are temporarily missing during repair. Final solutions are evaluated with strict full coverage.
3. `critical_crew_time`: find the bottleneck vehicle and enumerate all crew-ID × departure-interval combinations for that vehicle, retaining the best feasible combination found.
4. Current and best histories are both saved. Best-so-far history must be non-increasing; current-solution objective can rise or fall under simulated annealing.
5. Operator stats include uses, accepted moves, improving moves, rewards, and final weights.
6. `rush_hour_destroy_repair`: time-dependent destroy operator that traces clock arrival times and removes customers traversed during low-speed congestion intervals (especially on the critical/bottleneck route), reinserting them via regret-2 repair.
7. Exact mathematical solver (`tdvrpfca/milp.py` and `run_milp.py`): integrated our verified algebraic bug fixes (depot exclusion in c5/c6, start-time quicksum in c17, departure-based time-windows in c18/c19), yielding a provable 33.812 benchmark on the small instance.

## Validation run in the development environment

- `python -m pytest -q`: 14 passed.
- Small smoke: 2 runs × 5 iterations; both feasible.
- Small optimization: 5 runs × 50 iterations; feasible, best `T_MAX = 34.3175` (within 1.5% of the exact MILP optimal 33.812).
- R101 smoke: 1 run × 10 iterations; feasible, `T_MAX = 1010.9257` under the current evaluator.
- History lengths matched iteration count + 1, and best-so-far histories were monotone in smoke tests.

These are software validation checks, not evidence that v3 outperforms BWO. Run multiple seeds and use matched representation/evaluator settings before making a performance claim.

## Known limitations

- The common evaluator still has the modelling caveats documented in `REPRODUCTION_NOTES.md`, including time-window handling and the default return-leg convention.
- CT-ALNS initialization reuses the BWO population initializer; include initialization cost for a rigorous wall-clock comparison, and consider a separate common-start experiment.
- Matching iteration counts does not equalize objective-evaluation work. Report runtime and, for a stronger comparison, evaluator-call counts.
- The regret-2 insertion score uses objective gap plus a small distance-delta tie-breaker; this is a practical heuristic and should be ablated against greedy insertion.
- Crew/time joint search currently optimizes the critical vehicle's assignment pair with the shared evaluator; it is not a proof of global optimality over all vehicles.
