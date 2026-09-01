import json
import argparse
from pathlib import Path


def format_report(data):
    instance = data.get("instance", "N/A")
    mode = data.get("mode", "N/A")
    dataset = data.get("dataset", "N/A")
    status = data.get("status", "N/A")

    objective = data.get("objective_TMAX")
    best_bound = data.get("best_bound")
    mip_gap = data.get("mip_gap")
    runtime = data.get("runtime")
    solution_count = data.get("solution_count")

    num_variables = data.get("num_variables")
    num_constraints = data.get("num_constraints")

    solution = data.get("solution", {})
    feasible = solution.get("feasible_solution", data.get("feasible_solution", False))
    tmax = solution.get("TMAX", objective)

    routes = solution.get("routes", {})
    crews = solution.get("crews", {})
    visits = solution.get("visits", {})
    arrival_times = solution.get("arrival_times", {})

    lines = []

    lines.append("=" * 64)
    lines.append("              TD-VRPFCA — MILP RESULTS")
    lines.append("=" * 64)
    lines.append("")

    lines.append(f"Instance        : {instance}")
    lines.append(f"Mode            : {mode}")
    lines.append("Solver          : Gurobi")
    lines.append(f"Status          : {status}")
    lines.append("")

    lines.append("-" * 64)
    lines.append("PERFORMANCE")
    lines.append("-" * 64)

    if objective is not None:
        lines.append(f"Objective TMAX  : {objective:.3f}")
    else:
        lines.append("Objective TMAX  : N/A")

    if best_bound is not None:
        lines.append(f"Best Bound      : {best_bound:.3f}")
    else:
        lines.append("Best Bound      : N/A")

    if mip_gap is not None:
        lines.append(f"MIP Gap         : {mip_gap * 100:.2f} %")
    else:
        lines.append("MIP Gap         : N/A")

    if runtime is not None:
        lines.append(
            f"Runtime         : {runtime:.2f} seconds "
            f"({runtime / 60:.2f} minutes)"
        )
    else:
        lines.append("Runtime         : N/A")

    if solution_count is not None:
        lines.append(f"Solutions Found : {solution_count}")

    lines.append("")

    lines.append("-" * 64)
    lines.append("MODEL SIZE")
    lines.append("-" * 64)

    lines.append(
        f"Variables       : "
        f"{num_variables:,}" if num_variables is not None
        else "Variables       : N/A"
    )

    lines.append(
        f"Constraints     : "
        f"{num_constraints:,}" if num_constraints is not None
        else "Constraints     : N/A"
    )

    lines.append("")

    lines.append("-" * 64)
    lines.append("SOLUTION")
    lines.append("-" * 64)

    lines.append(f"Feasible        : {'Yes' if feasible else 'No'}")

    if tmax is not None:
        lines.append(f"Maximum TMAX    : {tmax:.3f}")

    lines.append("")

    # ---------------------------------------------------------
    # Routes
    # ---------------------------------------------------------

    if routes:
        lines.append("ROUTES")
        lines.append("-" * 64)

        for vehicle, route_data in routes.items():

            crew = crews.get(vehicle, "N/A")

            if route_data:
                route_nodes = []

                for arc in route_data:
                    i = arc.get("i")
                    j = arc.get("j")
                    route_nodes.append(str(i))

                # Add final destination
                if route_data:
                    route_nodes.append(str(route_data[-1].get("j")))

                route_string = " → ".join(route_nodes)

                lines.append(
                    f"Vehicle {vehicle} | Crew {crew} | "
                    f"Route: {route_string}"
                )
            else:
                lines.append(
                    f"Vehicle {vehicle} | Crew {crew} | Route: Unused"
                )

        lines.append("")

    # ---------------------------------------------------------
    # Vehicle visits
    # ---------------------------------------------------------

    if visits:
        lines.append("VEHICLE VISITS")
        lines.append("-" * 64)

        for vehicle, nodes in visits.items():
            node_string = " → ".join(str(x) for x in nodes)
            lines.append(f"Vehicle {vehicle}: {node_string}")

        lines.append("")

    # ---------------------------------------------------------
    # Arrival times
    # ---------------------------------------------------------

    if arrival_times:
        lines.append("ARRIVAL TIMES")
        lines.append("-" * 64)

        for key, value in sorted(arrival_times.items()):
            lines.append(f"{key:<10} : {value:.3f}")

        lines.append("")

    # ---------------------------------------------------------
    # Source metadata
    # ---------------------------------------------------------

    metadata = data.get("source_metadata", {})

    if metadata:
        lines.append("SOURCE / MODEL METADATA")
        lines.append("-" * 64)

        for key, value in metadata.items():
            lines.append(f"{key:<30}: {value}")

        lines.append("")

    # ---------------------------------------------------------
    # Dataset
    # ---------------------------------------------------------

    lines.append("DATASET")
    lines.append("-" * 64)
    lines.append(dataset)
    lines.append("")

    lines.append("=" * 64)
    lines.append("End of MILP Report")
    lines.append("=" * 64)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert a TD-VRPFCA MILP JSON result into a readable TXT report."
    )

    parser.add_argument(
        "json_file",
        help="Path to the generated MILP JSON result"
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output TXT file path (optional)"
    )

    args = parser.parse_args()

    json_path = Path(args.json_file)

    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}")
        return 1

    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Generate report
    report = format_report(data)

    # Output filename
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = json_path.with_suffix(".txt")

    # Save report
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report created successfully:")
    print(output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())