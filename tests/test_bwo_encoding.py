import pytest
from td_vrpfca.bwo import BWOOptimizer, BWOSolution
from td_vrpfca.loader import load_small_instance

@pytest.fixture
def small_inst():
    return load_small_instance("dataset/Small Intance")

def test_representation(small_inst):
    # n=10, k=2, d=8
    opt = BWOOptimizer(small_inst, seed=42)
    chrom = opt.create_random_route() + opt.create_random_crew() + [5]
    
    routes, crew, starts = opt.decode_chromosome(chrom)
    
    assert len(routes) == 2
    assert sum(len(r) for r in routes.values()) == 10
    
    assert len(crew) == 2
    assert all(c in range(1, 9) for c in crew.values())
    
    assert starts[1] == 5
    assert starts[2] == 5
