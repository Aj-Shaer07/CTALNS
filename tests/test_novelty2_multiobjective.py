"""Unit and regression tests for Novelty 2: Multi-Objective Time-Cost TD-VRPFCA."""
from pathlib import Path
import pytest

from td_vrpfca.data import load_small_instance
from td_vrpfca.model import Solution, evaluate_solution
from td_vrpfca.cost import CostConfig, CostBreakdown, evaluate_cost, calculate_route_distance
from td_vrpfca.pareto import ParetoPoint, ParetoArchive
from td_vrpfca.mo_ctalns import MOCTALNSOptimizer

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def small_instance():
    return load_small_instance(ROOT / "data" / "small")


def test_cost_model_empty_vs_active_vehicles(small_instance):
    """Empty vehicles should not incur fixed vehicle costs or crew wages."""
    # Dummy solution where vehicle 1 has customer 1, vehicle 2 is empty
    sol = Solution(
        routes={1: [1], 2: []},
        crew={1: 1, 2: 1},
        start_intervals={1: 1, 2: 1},
    )
    cfg = CostConfig(vehicle_fixed_cost=100.0, distance_cost_per_unit=2.0)
    cost = evaluate_cost(small_instance, sol, cost_config=cfg)

    # Exactly 1 vehicle active
    assert cost.active_vehicles == 1
    assert cost.vehicle_fixed_cost == 100.0
    assert cost.total_cost > 100.0


def test_cost_model_overtime_calculation(small_instance):
    """Test that routes exceeding regular shift threshold incur overtime penalty."""
    sol = Solution(
        routes={1: [1, 2], 2: []},
        crew={1: 1, 2: 1},
        start_intervals={1: 1, 2: 1},
    )
    # Set a tiny regular shift limit so that the route triggers overtime
    cfg_no_ot = CostConfig(regular_shift_limit_minutes=99999.0)
    cfg_with_ot = CostConfig(regular_shift_limit_minutes=0.0, overtime_multiplier=2.0)

    cost_no_ot = evaluate_cost(small_instance, sol, cost_config=cfg_no_ot)
    cost_with_ot = evaluate_cost(small_instance, sol, cost_config=cfg_with_ot)

    assert cost_no_ot.overtime_crew_cost == 0.0
    assert cost_with_ot.overtime_crew_cost > 0.0
    assert cost_with_ot.total_cost > cost_no_ot.total_cost


def test_pareto_dominance_rules():
    """Verify Pareto dominance logic."""
    sol = Solution(routes={}, crew={}, start_intervals={})
    p1 = ParetoPoint(solution=sol, t_max=100.0, cost=1000.0)
    p2 = ParetoPoint(solution=sol, t_max=120.0, cost=1200.0)  # Dominated by p1
    p3 = ParetoPoint(solution=sol, t_max=90.0, cost=1500.0)   # Non-dominated trade-off
    p4 = ParetoPoint(solution=sol, t_max=100.0, cost=1000.0)  # Identical to p1

    assert p1.dominates(p2) is True
    assert p2.dominates(p1) is False
    assert p1.dominates(p3) is False
    assert p3.dominates(p1) is False
    assert p1.is_close(p4) is True


def test_pareto_archive_pruning():
    """Verify ParetoArchive adds non-dominated points and prunes dominated ones."""
    sol = Solution(routes={}, crew={}, start_intervals={})
    archive = ParetoArchive(max_size=10)

    p1 = ParetoPoint(solution=sol, t_max=100.0, cost=1000.0)
    p2 = ParetoPoint(solution=sol, t_max=150.0, cost=1200.0)
    p3 = ParetoPoint(solution=sol, t_max=80.0, cost=1400.0)

    assert archive.add(p1) is True
    assert archive.add(p2) is False  # p2 is dominated by p1
    assert len(archive) == 1

    assert archive.add(p3) is True   # p3 is a valid trade-off (faster but more expensive)
    assert len(archive) == 2

    # Now add p_super which dominates p1: faster and cheaper than p1
    p_super = ParetoPoint(solution=sol, t_max=95.0, cost=950.0)
    assert archive.add(p_super) is True
    # p1 should now be pruned!
    assert len(archive) == 2
    pts = archive.get_sorted_front()
    assert pts[0].t_max == 80.0
    assert pts[1].t_max == 95.0


def test_pareto_archive_hypervolume():
    """Verify 2D hypervolume calculation."""
    sol = Solution(routes={}, crew={}, start_intervals={})
    archive = ParetoArchive(max_size=10)
    # Single point (10, 10) with reference point (20, 20) -> Area should be (20-10)*(20-10) = 100
    p = ParetoPoint(solution=sol, t_max=10.0, cost=10.0)
    archive.add(p)

    hv = archive.calculate_hypervolume(ref_point=(20.0, 20.0))
    assert abs(hv - 100.0) < 1e-6


def test_mo_ctalns_optimization_small(small_instance):
    """Test that MO-CTALNS runs end-to-end and returns a valid Pareto archive."""
    optimizer = MOCTALNSOptimizer(
        small_instance,
        archive_size=10,
        seed=42,
    )
    archive, history, runtime, stats = optimizer.run_multiobjective(iterations=5)

    assert len(archive) >= 1
    assert runtime > 0.0
    assert len(history) == 5

    # Check that all points in the archive are valid feasible solutions
    for pt in archive.points:
        eval_res = evaluate_solution(small_instance, pt.solution)
        assert eval_res["feasible"] is True
        assert pt.t_max > 0.0
        assert pt.cost > 0.0

    fastest = archive.get_fastest_solution()
    cheapest = archive.get_cheapest_solution()
    assert fastest is not None
    assert cheapest is not None
    assert fastest.t_max <= cheapest.t_max
    assert cheapest.cost <= fastest.cost
