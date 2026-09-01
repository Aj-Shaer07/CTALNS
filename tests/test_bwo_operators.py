import pytest
from td_vrpfca.bwo import BWOOptimizer, BWOSolution
from td_vrpfca.loader import load_small_instance

@pytest.fixture
def small_inst():
    return load_small_instance("dataset/Small Intance")

def test_mutation(small_inst):
    opt = BWOOptimizer(small_inst, seed=42, mutation_rate=1.0) # force mutation
    pop = opt.initialize_population()
    orig = list(pop[0].chromosome)
    
    mutants = opt.mutate([pop[0]])
    mutant = mutants[0].chromosome
    
    # Same elements
    assert sorted(orig[:opt.corte_cadena]) == sorted(mutant[:opt.corte_cadena])
    # But order is different
    assert orig[:opt.corte_cadena] != mutant[:opt.corte_cadena]

def test_crossover(small_inst):
    opt = BWOOptimizer(small_inst, seed=42)
    pop = opt.initialize_population()
    
    c1, c2 = opt.breed(pop[0].chromosome, pop[1].chromosome)
    
    # Validate coverage
    customers_c1 = [c for c in c1[:opt.corte_cadena] if c != 0]
    assert len(customers_c1) == 10
    assert set(customers_c1) == set(range(1, 11))

def test_cannibalism(small_inst):
    opt = BWOOptimizer(small_inst, seed=42, cannibalism_rate=0.5)
    pop = opt.initialize_population()
    
    # Just run one step of procreate_and_cannibalize
    # The output population size might fluctuate locally but it shouldn't crash
    # and should be mostly healthy solutions.
    survivors = opt.procreate_and_cannibalize(pop)
    assert len(survivors) > 0
