# Context-Aware Timeline Scheduler (CATS) for Data Pipelines

This project is the CATS a pipeline scheduler that uses dry run results to estimate hardware requirements and timelines for pipelines. The scheduler can generate and display timelines based on different input volumes, deadlines, and budgets.

## Prerequisites

- Python 3.12 for the pinned reproduction environment
- `pip` (Python package installer)

## Installation

1. Clone the repository:

    ```sh
    git clone https://github.com/nvnikolov/cats.git
    cd cats/scheduler
    ```

2. Install the required Python libraries:

    ```sh
    pip install -r ../requirements-reproducible.txt
    ```

## Running CATS for the spot welding data preparation pipeline

1. Run the `main.py` script:

    ```sh
    python main.py --display_timelines 1
    ```

    The `--display_timelines` argument is optional. Set it to `1` to display the generated timelines, or `0` to skip displaying them.

## Files

- [main.py](main.py): The main script to run the scheduler.
- [requirements.txt](requirements.txt): The list of required Python libraries.
- [resources.csv](resources.csv): The CSV file containing resource descriptions.
- [step_metrics.csv](step_metrics.csv), [step_performance_metrics.csv](step_performance_metrics.csv), [deployment_metrics.csv](deployment_metrics.csv): CSV files containing dry run metrics for the steps.

The rest of the repository contains the implementation of the CATS scheduler, organized as a modular, object-oriented Python project.

## Output

The generated timelines will be saved as CSV files in the scheduler directory with filenames in the format:
timeline_metrics3_{current_time}_deadline{deadline}_budget{budget}_input{input_volume_MB}MB_maxscalability{max_scalability}.csv

> **Note:** The values of the variables in the format are set within the code in `main.py`.

## Running the budget-sensitivity cost sweep

To evaluate how the CATS budget parameter changes the selected cost-time trade-off, run:

```sh
python cost_sweep.py --output-dir ../analysis/output/new-cost-sweep
```

The script writes per-schedule timelines, `cost_sweep_summary.csv`, `budget_sensitivity_summary.csv`, and `cost_makespan_tradeoff.png` to `../scheduler-cost-sweep` by default. Reported costs are compute/rental costs using the same EC2 hourly prices as `resources.csv`; data-transfer cost is excluded from the reported totals because the serialized schedule CSVs do not contain edge-level data volumes needed for robust transfer pricing.

See [known limitations](../KNOWN_LIMITATIONS.md) for cost-model units, score semantics and the exclusive scaling endpoint. Archived rebuttal outputs are retained in `../scheduler-cost-sweep`; use a separate output directory for new runs.
