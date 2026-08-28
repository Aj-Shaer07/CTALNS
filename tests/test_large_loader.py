from pathlib import Path
import pytest

from td_vrpfca.large_loader import load_large_instance

def test_large_loader_requires_real_dataset():
    p = Path("dataset/Large Intance")
    if not p.exists():
        pytest.skip("Large dataset not present in this checkout")
    inst = load_large_instance(p, "C101")
    assert len(inst.customers) == 100
    assert len(inst.vehicles) == 25
    assert len(inst.crew) == 8
    assert len(inst.intervals) == 3
