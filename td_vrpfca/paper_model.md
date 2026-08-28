# Paper → implementation notes

## Solver

The paper states that the MILP was coded in Python 3.12 and solved with
Gurobi 10.0.2.

## Mathematical source

The MILP implementation follows equations (1)–(22) as printed in the paper.
No depot/flow constraint is silently corrected.

## Crew combinations

The paper's Table 3 contains eight crew combinations:

| d | Dr | DP | MFDP |
|---|---:|---:|---:|
| 1 | 1 | 1 | 0 |
| 2 | 1 | 2 | 0 |
| 3 | 1 | 3 | 0 |
| 4 | 1 | 4 | 0 |
| 5 | 0 | 0 | 1 |
| 6 | 0 | 1 | 1 |
| 7 | 0 | 2 | 1 |
| 8 | 0 | 3 | 1 |

The public repository's `Small Intance/C.txt` contains five rows instead.
The loader records this discrepancy and uses the paper table for the MILP.

## Worker availability V^c

Constraint (13) requires `V^c`. The public Small Intance files do not contain
a separate `V^c` vector. The implementation therefore refuses to invent one.
If an explicitly sourced `V.txt`, `worker_availability.txt`,
`worker_availability.json`, or `V.json` is placed in the instance directory,
the loader reads it.

Without `V^c`, an exact execution of the published MILP is **not reproducible
from the public Small Intance files alone**.

## Time-dependent evaluation

The paper's Algorithm 1 uses the selected interval, `delta_ij / v_ij^l`,
and the selected crew's service time `t_id^l`, updating the interval when
the current time crosses an interval boundary.

The repository's `Fitness.py` implements this same overall structure.
