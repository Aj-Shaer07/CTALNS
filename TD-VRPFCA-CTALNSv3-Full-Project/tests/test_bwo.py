from pathlib import Path

from tdvrpfca.data import load_small_instance
from tdvrpfca.bwo import BWOOptimizer

ROOT = Path(__file__).resolve().parents[1]


def test_bwo_smoke_shared_time():
    inst = load_small_instance(ROOT / "data" / "small")
    opt = BWOOptimizer(inst, npop=6, procreation_rate=0.5, cannibalism_rate=0.5,
                       mutation_rate=0.2, seed=42, time_mode="shared")
    best, history, runtime = opt.run(max_iter=2)
    assert best.fitness < float("inf")
    assert len(history) == 3
    assert runtime >= 0
    solution = opt.decode_chromosome(best.chromosome)
    assert set(solution.routes) == {1, 2}
    assert set(solution.crew) == {1, 2}


def test_bwo_smoke_per_vehicle_time():
    inst = load_small_instance(ROOT / "data" / "small")
    opt = BWOOptimizer(inst, npop=6, procreation_rate=0.5, cannibalism_rate=0.5,
                       mutation_rate=0.2, seed=7, time_mode="per_vehicle")
    best, history, runtime = opt.run(max_iter=2)
    assert best.fitness < float("inf")
    sol = opt.decode_chromosome(best.chromosome)
    assert len(sol.start_intervals) == 2
