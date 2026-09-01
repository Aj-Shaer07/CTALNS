import pytest
from td_vrpfca.bwo import BWOOptimizer
from td_vrpfca.loader import load_small_instance

@pytest.fixture
def small_inst():
    return load_small_instance("dataset/Small Intance")

def test_reproducibility(small_inst):
    opt1 = BWOOptimizer(small_inst, seed=42)
    pop1 = opt1.initialize_population()
    
    opt2 = BWOOptimizer(small_inst, seed=42)
    pop2 = opt2.initialize_population()
    
    for s1, s2 in zip(pop1, pop2):
        assert s1.chromosome == s2.chromosome
        
    opt3 = BWOOptimizer(small_inst, seed=99)
    pop3 = opt3.initialize_population()
    
    assert pop1[0].chromosome != pop3[0].chromosome
