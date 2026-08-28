from __future__ import annotations

from .model import Evaluation


def _format_hours(hours: float) -> str:
    """Format decimal hours as Hh MMm SSs."""
    total_seconds = round(hours * 3600)
    h, remainder = divmod(total_seconds, 3600)
    m, s = divmod(remainder, 60)

    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def _format_minutes(hours: float) -> str:
    return f"{hours * 60:.2f} min"


def _format_crew(crew) -> str:
    if isinstance(crew, (list, tuple)):
        return "{" + ", ".join(str(x) for x in crew) + "}"
    return str(crew)


def print_evaluation(result: Evaluation) -> None:
    print("=" * 72)
    print("TD-VRPFCA EVALUATION")
    print("=" * 72)

    status = "FEASIBLE" if result.feasible else "INFEASIBLE"
    print(f"Status : {status}")
    print(
        f"T_MAX  : {_format_hours(result.t_max)} "
        f"({_format_minutes(result.t_max)})"
    )

    if result.violations:
        print("\nVIOLATIONS")
        print("-" * 72)
        for item in result.violations:
            print(f"  - {item}")

    print("\nROUTES")
    print("-" * 72)

    if not result.route_evaluations:
        print("  No route evaluations available.")
        return

    for r in result.route_evaluations:
        print(f"\nVehicle {r.vehicle}")
        print(f"  Start depot    : 0")
        print(f"  Route          : {' -> '.join(map(str, r.route[1:-1]))}")
        print(f"  End depot      : 11")
        print(f"  Crew           : {_format_crew(r.crew)}")
        print(f"  Start interval : {r.start_interval}")
        print(f"  Load           : {r.load:g}")
        print(
            f"  Travel time    : {_format_hours(r.travel_time)} "
            f"({_format_minutes(r.travel_time)})"
        )
        print(
            f"  Service time   : {_format_hours(r.service_time)} "
            f"({_format_minutes(r.service_time)})"
        )
        print(
            f"  Completion     : {_format_hours(r.completion_time)} "
            f"({_format_minutes(r.completion_time)})"
        )

    print("\n" + "=" * 72)
