"""Reproduce the revised manuscript's budget-sensitivity table from saved results."""

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIELDS = [
    "input_mb",
    "low_budget_cost_saving_pct",
    "low_budget_makespan_penalty_pct",
    "budget_1_cost_saving_pct",
    "budget_1_makespan_penalty_pct",
]


def read_outcome(rows, input_mb, budget):
    """Require returned candidates to agree on the table's two reported metrics."""
    outcomes = {
        (float(row["compute_cost_usd"]), float(row["makespan_s"]))
        for row in rows
        if float(row["input_mb"]) == input_mb
        and int(row["max_scalability"]) == 6
        and float(row["budget"]) == budget
    }
    if len(outcomes) != 1:
        raise ValueError(
            f"Expected one cost/makespan outcome for input={input_mb}, budget={budget}; "
            f"found {len(outcomes)}. Inspect the candidate schedules."
        )
    return outcomes.pop()


def reproduce_table(summary_path):
    with summary_path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    table = []
    for input_mb in (1229, 6143, 36955):
        baseline_cost, baseline_time = read_outcome(rows, input_mb, 100)
        values = [input_mb]
        for budget in (0.0005, 1):
            cost, makespan = read_outcome(rows, input_mb, budget)
            values.extend([
                f"{100 * (1 - cost / baseline_cost):.1f}",
                f"{100 * (makespan / baseline_time - 1):.1f}",
            ])
        table.append(dict(zip(FIELDS, values)))
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=ROOT / "scheduler-cost-sweep/cost_sweep_summary.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "analysis/output/budget_sensitivity_table.csv")
    args = parser.parse_args()
    table = reproduce_table(args.summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(table)
    print(args.output)


if __name__ == "__main__":
    main()
