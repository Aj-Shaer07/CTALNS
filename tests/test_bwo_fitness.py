import pytest
from td_vrpfca.bwo import BWOOptimizer
from td_vrpfca.loader import load_small_instance

@pytest.fixture
def small_inst():
    return load_small_instance("dataset/Small Intance")

def test_time_dependency(small_inst):
    opt = BWOOptimizer(small_inst, seed=42)
    
    # Construct a chromosome
    route = [0, 1, 2, 3, 4, 5, 0, 6, 7, 8, 9, 10, 0]
    crew = [1, 1, 0, 0, 0, 0, 0, 0] # Vehicle 1 gets crew 1, Vehicle 2 gets crew 2
    
    chrom1 = route + crew + [1]
    chrom2 = route + crew + [9] # Later interval
    
    fit1 = opt.evaluate(chrom1)
    fit2 = opt.evaluate(chrom2)
    
    assert fit1 != float('inf')
    assert fit2 != float('inf')
    # Since speed profiles vary across intervals, travel times and therefore TMAX should change
    assert fit1 != fit2

def test_interval_transition(small_inst):
    # Verify that a long route crosses interval boundaries properly 
    # (implicitly handled by evaluate_routes, which we verified does this)
    opt = BWOOptimizer(small_inst, seed=42)
    route = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0, 0] # all on one vehicle
    crew = [1, 1, 0, 0, 0, 0, 0, 0]
    chrom = route + crew + [1]
    
    # Just check it evaluates without error and gives a valid positive number
    fit = opt.evaluate(chrom)
    assert fit > 0
    assert fit != float('inf')
