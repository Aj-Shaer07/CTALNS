import pytest

gp = pytest.importorskip("gurobipy")

from td_vrpfca.milp import build_paper_milp


def test_milp_builder_is_importable():
    assert callable(build_paper_milp)
