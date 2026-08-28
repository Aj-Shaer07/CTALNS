from td_vrpfca.evaluator import TDVRPFCAEvaluator
from td_vrpfca.model import Instance, Solution, Vehicle


def make_instance():
    return Instance(
        customers=[1],
        nodes=[0, 1, 2],
        vehicles={1: Vehicle(1, 100, 2)},
        crew_composition={1: {1: 1, 2: 1}},
        worker_limits={},
        demand={0: 0, 1: 10, 2: 0},
        distance={(0, 1): 10.0, (1, 2): 10.0},
        speed={(0, 1, 1): 20.0, (1, 2, 1): 20.0},
        service_time={(1, 1, 1): 30.0},
        lower={1: 0.0},
        upper={1: 2.0},
        depot_start=0,
        depot_return=2,
    )


def test_service_minutes_are_scaled_to_hours():
    instance = make_instance()
    solution = Solution(
        routes={1: [0, 1, 2]},
        crew={1: 1},
        start_interval={1: 1},
    )
    result = TDVRPFCAEvaluator(instance).evaluate(solution)
    assert result.feasible
    assert result.route_evaluations[0].service_time == 0.5
    assert result.route_evaluations[0].travel_time == 1.0
    assert result.t_max == 1.5


def test_customer_coverage_violation():
    instance = make_instance()
    solution = Solution(
        routes={1: [0, 2]},
        crew={},
        start_interval={},
    )
    result = TDVRPFCAEvaluator(instance).evaluate(solution)
    assert not result.feasible
    assert "Customer 1: not served" in result.violations


def test_capacity_violation():
    instance = make_instance()
    instance.vehicles[1] = Vehicle(1, 5, 2)
    solution = Solution(
        routes={1: [0, 1, 2]},
        crew={1: 1},
        start_interval={1: 1},
    )
    result = TDVRPFCAEvaluator(instance).evaluate(solution)
    assert not result.feasible
    assert any("Vehicle 1 capacity" in x for x in result.violations)


def test_missing_arc_speed_uses_unique_interval_speed():
    instance = make_instance()
    instance.speed.pop((1, 2, 1))
    solution = Solution(
        routes={1: [0, 1, 2]},
        crew={1: 1},
        start_interval={1: 1},
    )
    result = TDVRPFCAEvaluator(instance).evaluate(solution)
    assert result.feasible
    assert result.route_evaluations[0].travel_time == 1.0
