from pathlib import Path

from tdvrpfca.data import load_small_instance
from tdvrpfca.ctalns import CTALNSOptimizer
from tdvrpfca.model import evaluate_solution

ROOT = Path(__file__).resolve().parents[1]


def test_ctalns_smoke_returns_feasible_solution_and_history():
    instance = load_small_instance(ROOT / "data" / "small")
    optimizer = CTALNSOptimizer(instance, seed=42, removal_fraction=0.2)
    best, history, current_history, runtime, stats = optimizer.run(iterations=3)
    result = evaluate_solution(instance, best)

    assert result["feasible"], result["violations"]
    assert len(history) == 4
    assert len(current_history) == 4
    assert all(history[i] <= history[i - 1] + 1e-9 for i in range(1, len(history)))
    assert history[-1] <= history[0] + 1e-9
    assert runtime >= 0
    assert set(stats) == set(optimizer.operator_names)
    assert sum(item["uses"] for item in stats.values()) == 3


def test_partial_evaluation_is_explicit_and_default_still_checks_coverage():
    instance = load_small_instance(ROOT / "data" / "small")
    optimizer = CTALNSOptimizer(instance, seed=42)
    partial = optimizer._copy(optimizer.current)
    removed = None
    for vehicle in optimizer.vehicle_ids:
        if partial.routes[vehicle]:
            removed = partial.routes[vehicle].pop()
            break
    assert removed is not None

    partial_result = evaluate_solution(
        instance, partial, check_customer_coverage=False
    )
    strict_result = evaluate_solution(instance, partial)
    assert partial_result["feasible"], partial_result["violations"]
    assert not strict_result["feasible"]
    assert any("Customer coverage missing" in v for v in strict_result["violations"])


def test_destroy_repair_reinserts_every_customer():
    instance = load_small_instance(ROOT / "data" / "small")
    optimizer = CTALNSOptimizer(instance, seed=7, removal_fraction=0.2)

    for name in (
        "random_destroy_repair",
        "worst_destroy_repair",
        "related_destroy_repair",
    ):
        candidate = optimizer._apply_operator(name, optimizer.current)
        assert candidate is not None, name
        result = evaluate_solution(instance, candidate)
        assert result["feasible"], (name, result["violations"])
        served = [c for route in candidate.routes.values() for c in route]
        assert len(served) == len(instance.customers)
        assert set(served) == set(instance.customers)


def test_v3_critical_and_regret_operators_preserve_feasibility():
    instance = load_small_instance(ROOT / "data" / "small")
    optimizer = CTALNSOptimizer(instance, seed=19, removal_fraction=0.2)

    for name in ("critical_destroy_repair", "rush_hour_destroy_repair", "regret2_destroy_repair", "critical_crew_time"):
        candidate = optimizer._apply_operator(name, optimizer.current)
        assert candidate is not None, name
        result = evaluate_solution(instance, candidate)
        assert result["feasible"], (name, result["violations"])
        served = [c for route in candidate.routes.values() for c in route]
        assert len(served) == len(instance.customers)
        assert set(served) == set(instance.customers)


def test_v3_critical_vehicle_is_a_route_with_max_completion_time():
    instance = load_small_instance(ROOT / "data" / "small")
    optimizer = CTALNSOptimizer(instance, seed=23)
    critical = optimizer._critical_vehicle(optimizer.current)
    result = evaluate_solution(instance, optimizer.current)
    route_results = result["route_results"]
    expected = max(route_results, key=lambda r: r["completion_time"])["vehicle"]
    assert critical == expected
