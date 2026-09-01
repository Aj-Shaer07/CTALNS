import pytest
from td_vrpfca.bwo import BWOOptimizer
from td_vrpfca.loader import load_small_instance

@pytest.fixture
def small_inst():
    return load_small_instance("dataset/Small Intance")

def test_customer_coverage(small_inst):
    opt = BWOOptimizer(small_inst, seed=42)
    route = opt.create_random_route()
    customers_in_route = [c for c in route if c != 0]
    assert len(customers_in_route) == 10
    assert set(customers_in_route) == set(range(1, 11))

def test_capacity_feasibility(small_inst):
    opt = BWOOptimizer(small_inst, seed=42)
    assert opt.is_route_feasible(opt.create_random_route())
    
    # Force a demand that exceeds capacity
    # Vehicle capacity is 600. Let's just mock demand of a node.
    small_inst.demand[1] = 10000.0
    
    bad_route = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0, 0]
    assert not opt.is_route_feasible(bad_route)

def test_crew_feasibility(small_inst):
    opt = BWOOptimizer(small_inst, seed=42)
    crew = opt.create_random_crew()
    
    assert sum(crew) == 2 
    assert len(crew) == 8 
