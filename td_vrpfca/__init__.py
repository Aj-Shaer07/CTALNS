"""TD-VRPFCA project package.

Supports:
- Original TD-VRPFCA with exact MILP and BWO baseline
- Novelty 1: CT-ALNS (Crew-and-Time Adaptive Large Neighborhood Search)
- Novelty 2: MO-CTALNS (Time-Cost Trade-off Multi-Objective Optimization)
"""

from .model import Instance, Vehicle, Solution, RouteResult, evaluate_solution
from .cost import CostConfig, CostBreakdown, evaluate_cost
from .pareto import ParetoPoint, ParetoArchive
from .bwo import BWOOptimizer
from .ctalns import CTALNSOptimizer
from .mo_ctalns import MOCTALNSOptimizer
from .mo_bwo import MOBWOOptimizer

__all__ = [
    "Instance",
    "Vehicle",
    "Solution",
    "RouteResult",
    "evaluate_solution",
    "CostConfig",
    "CostBreakdown",
    "evaluate_cost",
    "ParetoPoint",
    "ParetoArchive",
    "BWOOptimizer",
    "CTALNSOptimizer",
    "MOCTALNSOptimizer",
    "MOBWOOptimizer",
]
