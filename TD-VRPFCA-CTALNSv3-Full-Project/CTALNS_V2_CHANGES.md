# CT-ALNS v2: changes after code audit

## Why v1 should not be used for comparative claims

The route destroy-and-repair implementation called the strict evaluator while some customers were intentionally removed. Since the strict evaluator checks complete customer coverage, every partial insertion was marked infeasible. As a result, route repair could return early without reinserting removed customers.

## Changes in v2

1. `evaluate_solution(..., check_customer_coverage=True)` keeps strict coverage validation as the default. Repair scoring can explicitly set it to `False`; the final repaired candidate is always rechecked with strict coverage.
2. Destroy/repair now scores insertions with the partial evaluator and validates full coverage after all removed customers have been reinserted.
3. Expensive candidate evaluation is bounded by `--insertion-positions-per-vehicle` (default 2) after ranking positions by distance-based insertion delta.
4. Related removal uses pairwise customer distances, rather than a one-dimensional depot-distance proxy.
5. Added route relocate and swap neighborhoods, in addition to random, worst and related destroy/repair, crew reassignment, time retiming, and joint crew-time moves.
6. Crew/time operators generate a neighbor rather than greedily returning only an improving move. Simulated annealing now has a meaningful chance to accept a worsening move.
7. Initialization uses 20 BWO-generated candidates by default and selects the best feasible candidate. This matches the BWO population size, but not BWO's full optimization run.
8. Added regression tests for partial-evaluation semantics and customer coverage after all three destroy/repair operators.

## Test status

`python -m pytest -q`: 11 passed.

Small smoke test: 2 runs x 5 iterations; both feasible.
R101 smoke test: 1 run x 10 iterations; feasible.

These are software checks only. The formulation/evaluator still needs paper alignment, and the CT-ALNS result has not been shown to outperform BWO.

## Fair comparison warning

The earlier BWO results used `--time-mode shared` by default, while CT-ALNS permits per-vehicle departure intervals. For a fair comparison of the intended vehicle-specific departure decisions, rerun BWO with `--time-mode per_vehicle` and run CT-ALNS with `--initial-time-mode per_vehicle`. Both algorithms must use the same evaluator and return-leg convention. Report initialization time separately or include it consistently in total runtime.
