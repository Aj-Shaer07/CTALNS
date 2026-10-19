# Reproduction notes and provenance

## Source priority

1. **Friend's project (`CTALNS-main`)** is the primary implementation reference,
   because it already reconstructed the loaders, BWO chromosome, evaluator and
   experiment runners and recorded discrepancies.
2. The **authors' public `TD-VRP-FCA` repository** is used to verify original
   data files and algorithm stages.
3. The **2025 paper** is used to resolve missing crew combinations and clarify
   the mathematical formulation.

The included raw data files are copied from the authors' public repository.
Only the instances used by the project are retained: the small instance and
R101, R201, RC101, RC201. C101, C201 and the separate case-study dataset are
not included.

## Confirmed data choices

- Small: `I.txt`, `K.txt`, `C.txt`, `Distances.txt`, `coord.csv`, `t.txt`, `v.txt`.
- Large: R101, R201, RC101, RC201; `D.txt`; `catheg.txt`, `catheg_2.txt`;
  `t_dep.txt`, `t_dep_2.txt`, `t_dep_3.txt`.
- Small crew table: paper Table 3 completes the five rows in the public `C.txt`
  to eight combinations.
- Small worker availability `{1:4, 2:2, 3:2}` comes from the friend's small
  experiment runner; it is not in the original small data. The code makes this
  visible as a data file.
- Large worker availability `{DP:50, Dr:20, MFDP:20}` and capacities are taken
  from the friend's loader and its documented public-source preprocessing.

## BWO mechanics preserved from friend's code

- Route chromosome with depot separators.
- Crew-combination count segment.
- Shared start-interval gene by default.
- Route crossover using a segment from one parent and the remaining customer
  sequence from the other.
- Route-swap mutation.
- Sexual/sibling/parental cannibalism interpretation used in friend's code.
- Sorting by fitness and truncating to population size.
- Experiment parameters used by the friend's runners.

## Deliberate software corrections

The public authors' source contains a call `child = child.append(0)`, which sets
`child` to `None`, and a parent-cannibalism branch that references `self.pop`
without initializing it. The friend's code already avoids those crashes by
reconstructing the operators. This project retains the friend's reconstructed
operators and adds additional structural guards, bounded initialization, and
final-generation best tracking. These fixes can change stochastic results; do
not expect bit-for-bit identity with a buggy source run.

## Discrepancies that must remain explicit

1. **Starting-time representation:** the paper describes vehicle-specific
   starting intervals, while the friend's chromosome and public BWO fitness
   use a single interval shared by all vehicles. The default is `shared` for
   friend-baseline comparability; `per_vehicle` is available as a separate mode.
2. **Small travel-time units:** friend/public fitness uses `distance/speed`
   directly. The source's 60-minute intervals and stated km/h interpretation
   suggest a possible factor-of-60 inconsistency. Default factor 1 preserves
   historical comparability; factor 60 is a separate sensitivity mode.
3. **Large return leg:** the public authors' large-instance Tabu Search
   preprocessing sets distance to dummy node 101 to zero. This is retained by
   default to match the source. `physical` mode is available for sensitivity
   checks, but it is a different objective model.
4. **Time windows:** large Solomon READYTIME/DUEDATE values are not enforced by
   the friend's BWO evaluator or the authors' public TS preprocessing.
5. **Crew availability:** the small worker-availability vector is reconstructed
   from the friend's runner, not a value explicitly present in the original
   small dataset.

## Comparison protocol

To compare BWO and CT-ALNS fairly, use the same:
- loaded instance and data files;
- `travel_time_factor`, `time_mode`, and `return_leg_mode`;
- feasibility and objective evaluator;
- constraints and stopping budget;
- hardware, and multiple seeds.

Report best, mean, standard deviation, runtime, convergence and feasibility.
