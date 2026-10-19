from pathlib import Path
from tdvrpfca.data import load_small_instance
from tdvrpfca.milp import build_corrected_milp

ROOT = Path(__file__).resolve().parents[1]


def test_milp_builds_without_error():
    instance = load_small_instance(ROOT / "data" / "small")
    result = build_corrected_milp(instance, time_limit=5, verbose=False, fix_all_bugs=True)
    assert result.num_vars > 0
    assert result.num_constraints > 0
    assert result.model is not None
