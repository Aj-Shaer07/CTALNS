from pathlib import Path

from tdvrpfca.data import load_small_instance
from tdvrpfca.model import Solution, evaluate_solution

ROOT = Path(__file__).resolve().parents[1]


def test_hand_checkable_small_solution_is_feasible():
    inst = load_small_instance(ROOT / "data" / "small")
    # Two routes and crew assignments from the project's earlier hand-check.
    solution = Solution(
        routes={1: [1, 3, 4, 8, 9], 2: [2, 5, 6, 7, 10]},
        crew={1: 1, 2: 5},
        start_intervals={1: 1, 2: 1},
    )
    result = evaluate_solution(inst, solution)
    assert result["feasible"], result["violations"]
    assert result["T_MAX"] > 0
    assert len(result["route_results"]) == 2


def test_minutes_factor_changes_travel_component():
    root = ROOT / "data" / "small"
    inst_source = load_small_instance(root, travel_time_factor=1.0)
    inst_minutes = load_small_instance(root, travel_time_factor=60.0)
    solution = Solution(
        routes={1: [1, 3, 4, 8, 9], 2: [2, 5, 6, 7, 10]},
        crew={1: 1, 2: 5},
        start_intervals={1: 1, 2: 1},
    )
    source = evaluate_solution(inst_source, solution)
    minutes = evaluate_solution(inst_minutes, solution)
    assert source["feasible"] and minutes["feasible"]
    # Time-dependent intervals change during the route, so multiplying speeds
    # by 60 does not simply multiply the final total by 60.
    assert minutes["route_results"][0]["travel_time"] > source["route_results"][0]["travel_time"]
    assert abs(minutes["T_MAX"] - 104.7) < 1e-6
