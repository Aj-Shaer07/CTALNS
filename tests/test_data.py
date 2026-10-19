from pathlib import Path

from tdvrpfca.data import load_small_instance, load_large_instance

ROOT = Path(__file__).resolve().parents[1]


def test_small_data_and_paper_crew_completion():
    inst = load_small_instance(ROOT / "data" / "small")
    assert len(inst.customers) == 10
    assert len(inst.vehicles) == 2
    assert len(inst.crew) == 8
    assert len(inst.intervals) == 10
    assert inst.crew[8] == {1: 3.0, 2: 0.0, 3: 1.0}
    assert inst.worker_availability == {1: 4.0, 2: 2.0, 3: 2.0}


def test_large_data_loader():
    inst = load_large_instance(ROOT / "data" / "large", "R101")
    assert len(inst.customers) == 100
    assert len(inst.vehicles) == 25
    assert len(inst.crew) == 8
    assert len(inst.intervals) == 3
    assert inst.distance[(1, 101)] == 0.0
    assert inst.metadata["return_leg_mode"] == "source"


def test_physical_return_distance_variant():
    inst = load_large_instance(ROOT / "data" / "large", "R101", return_leg_mode="physical")
    assert inst.distance[(1, 101)] > 0.0


def test_all_24_project_large_configurations_load():
    root = ROOT / "data" / "large"
    for name in ("R101", "R201", "RC101", "RC201"):
        for category in ("catheg.txt", "catheg_2.txt"):
            for speed in ("t_dep.txt", "t_dep_2.txt", "t_dep_3.txt"):
                inst = load_large_instance(
                    root, name, category_matrix=category, speed_profile=speed
                )
                assert len(inst.customers) == 100
                assert len(inst.intervals) == 3
