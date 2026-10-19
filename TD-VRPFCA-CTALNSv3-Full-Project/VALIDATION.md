# Validation performed for this bundle

- `python -m pytest -q`: **8 tests passed**.
- Small-instance BWO smoke run completed with 3 runs, population 10, 3 iterations.
- One R101 BWO smoke run completed with population 4 and 1 iteration.
- All 24 large configurations (R101/R201/RC101/RC201 × catheg/catheg_2 × t_dep/t_dep_2/t_dep_3) loaded and completed a 1-iteration smoke run.

These are software smoke tests, not paper-reproduction results. The reduced-population/iteration smoke runs must not be cited as benchmark performance. Reproduction requires the paper's full parameter settings and a like-for-like check of time units, start-time representation, crew availability, and dummy return-node convention.
