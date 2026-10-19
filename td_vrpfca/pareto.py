"""Novelty 2: Pareto Archive and Dominance for Bi-Objective TD-VRPFCA.

Handles Pareto dominance checking, archive maintenance, crowding distance
estimation, and 2D hypervolume computation for the (T_MAX, C_total) trade-off.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any

from .model import Solution
from .cost import CostBreakdown


@dataclass
class ParetoPoint:
    """A single non-dominated trade-off solution on the Pareto frontier."""
    solution: Solution
    t_max: float
    cost: float
    cost_breakdown: Optional[CostBreakdown] = None
    evaluation: Optional[Dict[str, Any]] = None
    crowding_distance: float = 0.0
    iteration_found: int = 0
    operator_used: str = ""

    def dominates(self, other: ParetoPoint, eps: float = 1e-6) -> bool:
        """Check if self Pareto-dominates other.

        self dominates other iff self is no worse than other in both objectives,
        and strictly better in at least one objective.
        """
        no_worse = (self.t_max <= other.t_max + eps) and (self.cost <= other.cost + eps)
        strictly_better = (self.t_max < other.t_max - eps) or (self.cost < other.cost - eps)
        return no_worse and strictly_better

    def is_close(self, other: ParetoPoint, eps: float = 1e-4) -> bool:
        """Check if two points are essentially identical in objective space."""
        return abs(self.t_max - other.t_max) <= eps and abs(self.cost - other.cost) <= eps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "T_MAX": self.t_max,
            "C_total": self.cost,
            "crowding_distance": self.crowding_distance,
            "iteration_found": self.iteration_found,
            "operator_used": self.operator_used,
            "active_vehicles": len([r for r in self.solution.routes.values() if r]),
            "cost_breakdown": self.cost_breakdown.to_dict() if self.cost_breakdown else None,
            "routes": self.solution.routes,
            "crew": self.solution.crew,
            "start_intervals": self.solution.start_intervals,
        }


class ParetoArchive:
    """Bounded external archive maintaining non-dominated solutions."""

    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self.points: List[ParetoPoint] = []

    def __len__(self) -> int:
        return len(self.points)

    def is_dominated_by_archive(self, candidate: ParetoPoint) -> bool:
        """Check if candidate is dominated by any solution already in the archive."""
        return any(pt.dominates(candidate) for pt in self.points)

    def add(self, candidate: ParetoPoint) -> bool:
        """Attempt to add candidate to the Pareto archive.

        Returns
        -------
        bool
            True if candidate entered the archive (non-dominated), False if rejected.
        """
        # 1. Reject if candidate is dominated by any archive member
        for pt in self.points:
            if pt.dominates(candidate):
                return False

        # 2. Reject if candidate is identical in objective values to an existing member
        if any(pt.is_close(candidate) for pt in self.points):
            return False

        # 3. Prune all current archive points dominated by the new candidate
        survivors = [pt for pt in self.points if not candidate.dominates(pt)]
        survivors.append(candidate)
        self.points = survivors

        # 4. If archive exceeds maximum capacity, prune using crowding distance
        if len(self.points) > self.max_size:
            self._prune_by_crowding()

        return True

    def update_crowding_distances(self) -> None:
        """Compute NSGA-II crowding distances for all points in the archive."""
        n = len(self.points)
        if n <= 2:
            for pt in self.points:
                pt.crowding_distance = float("inf")
            return

        for pt in self.points:
            pt.crowding_distance = 0.0

        # Objective 1: T_MAX
        self.points.sort(key=lambda p: p.t_max)
        self.points[0].crowding_distance = float("inf")
        self.points[-1].crowding_distance = float("inf")
        t_span = self.points[-1].t_max - self.points[0].t_max
        if t_span > 1e-6:
            for i in range(1, n - 1):
                self.points[i].crowding_distance += (
                    (self.points[i + 1].t_max - self.points[i - 1].t_max) / t_span
                )

        # Objective 2: C_total
        self.points.sort(key=lambda p: p.cost)
        self.points[0].crowding_distance = float("inf")
        self.points[-1].crowding_distance = float("inf")
        c_span = self.points[-1].cost - self.points[0].cost
        if c_span > 1e-6:
            for i in range(1, n - 1):
                self.points[i].crowding_distance += (
                    (self.points[i + 1].cost - self.points[i - 1].cost) / c_span
                )

    def _prune_by_crowding(self) -> None:
        """Remove the point with the lowest crowding distance (least diverse)."""
        self.update_crowding_distances()
        # Do not prune boundary/infinite distance solutions
        candidates = [p for p in self.points if not math.isinf(p.crowding_distance)]
        if candidates:
            worst = min(candidates, key=lambda p: p.crowding_distance)
            self.points.remove(worst)
        else:
            self.points.pop()

    def get_sorted_front(self) -> List[ParetoPoint]:
        """Return the Pareto frontier sorted by T_MAX ascending (cost descending)."""
        return sorted(self.points, key=lambda p: (p.t_max, p.cost))

    def get_fastest_solution(self) -> Optional[ParetoPoint]:
        """Return the extreme solution with the absolute minimum makespan (T_MAX)."""
        if not self.points:
            return None
        return min(self.points, key=lambda p: p.t_max)

    def get_cheapest_solution(self) -> Optional[ParetoPoint]:
        """Return the extreme solution with the absolute minimum total cost (C_total)."""
        if not self.points:
            return None
        return min(self.points, key=lambda p: p.cost)

    def get_knee_solution(self) -> Optional[ParetoPoint]:
        """Identify the compromise 'knee' solution closest to the ideal point in normalized space."""
        if not self.points:
            return None
        if len(self.points) <= 2:
            return self.points[0]

        min_t = min(p.t_max for p in self.points)
        max_t = max(p.t_max for p in self.points)
        min_c = min(p.cost for p in self.points)
        max_c = max(p.cost for p in self.points)

        span_t = max_t - min_t or 1.0
        span_c = max_c - min_c or 1.0

        def dist_to_ideal(pt: ParetoPoint) -> float:
            norm_t = (pt.t_max - min_t) / span_t
            norm_c = (pt.cost - min_c) / span_c
            return math.sqrt(norm_t ** 2 + norm_c ** 2)

        return min(self.points, key=dist_to_ideal)

    def calculate_hypervolume(self, ref_point: Optional[Tuple[float, float]] = None) -> float:
        """Compute the 2D Hypervolume bounded by the Pareto front and a reference nadir point.

        Parameters
        ----------
        ref_point : (T_ref, C_ref), optional
            Upper bound coordinates. If omitted, uses 1.1x the maximum observed coordinates.
        """
        if not self.points:
            return 0.0

        sorted_pts = self.get_sorted_front()
        max_t = max(p.t_max for p in sorted_pts)
        max_c = max(p.cost for p in sorted_pts)

        if ref_point is None:
            r_t = max_t * 1.10
            r_c = max_c * 1.10
        else:
            r_t, r_c = ref_point

        # Hypervolume integration: sum of rectangular slices
        hv = 0.0
        current_c = r_c

        for pt in sorted_pts:
            if pt.t_max < r_t and pt.cost < current_c:
                width = r_t - pt.t_max
                height = current_c - pt.cost
                hv += width * height
                current_c = pt.cost

        return hv
