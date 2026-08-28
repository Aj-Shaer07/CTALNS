
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Vehicle:
    id: int
    capacity: float
    max_crew: int


@dataclass
class Solution:
    routes: Dict[int, List[int]]
    crew: Dict[int, int]
    start_interval: Dict[int, int]


@dataclass
class RouteEvaluation:
    vehicle: int
    route: List[int]
    crew: int
    start_interval: int
    departure_time: float
    completion_time: float
    load: float
    travel_time: float
    service_time: float
    arrival_times: Dict[int, float] = field(default_factory=dict)
    intervals: Dict[Tuple[int, int], int] = field(default_factory=dict)


@dataclass
class Evaluation:
    feasible: bool
    t_max: float
    route_evaluations: List[RouteEvaluation]
    violations: List[str]
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class Instance:
    customers: List[int]
    nodes: List[int]
    vehicles: Dict[int, Vehicle]
    crew_composition: Dict[int, Dict[int, int]]
    worker_limits: Dict[int, float]
    demand: Dict[int, float]
    distance: Dict[Tuple[int, int], float]
    speed: Dict[Tuple[int, int, int], float]
    service_time: Dict[Tuple[int, int, int], float]
    lower: Dict[int, float]
    upper: Dict[int, float]
    depot_start: int = 0
    depot_return: int = 11

    @property
    def crew_combinations(self) -> List[int]:
        return sorted(self.crew_composition)

    @property
    def time_intervals(self) -> List[int]:
        return sorted(self.lower)
