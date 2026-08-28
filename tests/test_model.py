import importlib.util
import pytest


def test_gurobi_presence():
    if importlib.util.find_spec("gurobipy") is None:
        pytest.skip("gurobipy is not installed in this environment")
    import gurobipy
    assert gurobipy is not None
