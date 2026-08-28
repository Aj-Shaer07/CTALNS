
from __future__ import annotations

import argparse
import json
import time

from td_vrpfca.constructive import deterministic_solution
from td_vrpfca.evaluator import TDVRPFCAEvaluator
from td_vrpfca.loader import load_small_or_case_instance
from td_vrpfca.report import print_evaluation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instance_folder")
    parser.add_argument(
        "--service-scale",
        type=float,
        default=1.0 / 60.0,
        help="Multiplier applied to raw t.txt service values. "
             "Repository t.txt values are minute-valued; default converts minutes to hours.",
    )
    args = parser.parse_args()

    instance = load_small_or_case_instance(args.instance_folder)

    start = time.perf_counter()
    solution = deterministic_solution(instance)
    result = TDVRPFCAEvaluator(
        instance, service_scale=args.service_scale
    ).evaluate(solution)
    runtime = time.perf_counter() - start

    print_evaluation(result)
    print(f"\nRUNTIME_SECONDS: {runtime:.6f}")

    with open("objective1_result.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "feasible": result.feasible,
                "T_MAX": result.t_max,
                "violations": result.violations,
                "runtime_seconds": runtime,
                "routes": [
                    {
                        "vehicle": r.vehicle,
                        "route": r.route,
                        "crew": r.crew,
                        "start_interval": r.start_interval,
                        "load": r.load,
                        "travel_time": r.travel_time,
                        "service_time": r.service_time,
                        "completion_time": r.completion_time,
                    }
                    for r in result.route_evaluations
                ],
            },
            f,
            indent=2,
        )


if __name__ == "__main__":
    main()
