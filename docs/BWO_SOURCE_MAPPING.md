# BWO Source Mapping

| Component | Author Source | Our Code | Status |
| :--- | :--- | :--- | :--- |
| Encoding | `BWO_etapas.py` | `bwo.py` | Source-faithful |
| Fitness | `Fitness.py` | `evaluator.py` | Source-faithful |
| Initialization | `BWO_etapas.py` | `bwo.py` | Reconstructed |
| Crossover | `BWO_etapas.py` | `bwo.py` | Reconstructed/source-faithful |
| Cannibalism | `BWO_etapas.py` + paper | `bwo.py` | Reconstructed |
| Mutation | `BWO_etapas.py` | `bwo.py` | Source-faithful |
| Parameters | Paper Section IV | experiment runners | Source-faithful |
| Seed | Not in source | experiment runners | Our addition |
| JSON | Not in source | `report.py` | Our addition |
| TXT | Not in source | `report.py` | Our addition |

### Inconsistencies Discovered
1. **Repository initialization mismatch**: `BWO.py` calls `inicializar_GA()` while `BWO_etapas.py` contains `inicializar()`.
2. **Repository `cr` naming conflict**: The paper defines `cr` as cannibalism survival rate, but repository uses `cr` for number of worker types/resources.
3. **Time representation ambiguity**: The repository appends a single final interval value for all vehicles, contrasting with the paper's description of per-vehicle intervals.
4. **Broken append operation**: `child = child.append(0)` sets the child to `None`.
5. **Undefined population state**: Cannibalism uses `self.pop` without initialization.
6. **Customer time-window enforcement**: `Fitness.py` does not explicitly enforce Solomon time windows.
