# Reproduce the paper analysis

Run from the repository root after installing `requirements-reproducible.txt`:

```sh
python analysis/reproduce_budget_table.py
python analysis/rebuild_pipeline_step_figures.py
```

Both scripts write into `analysis/output/`, which is ignored by Git.

## Figure and table inputs

| Paper output | Script output | Inputs |
| --- | --- | --- |
| Budget-sensitivity table | `output/budget_sensitivity_table.csv` | `../scheduler-cost-sweep/cost_sweep_summary.csv` |
| Step-time prediction error | `output/Plots/sp_diff.pdf` | Historical schedules, measured step times and selected replay |
| Makespan prediction error | `output/Plots/makespan_diff.pdf` | Historical schedules, deployment times and selected replay |
| Absolute step execution time | `output/Plots/sp.pdf` | Historical schedules, measured step times and selected replay |
| Absolute pipeline makespan | `output/Plots/makespan.pdf` | Historical schedules, deployment times and selected replay |
| CPU usage | `output/Plots/cpu.pdf` | Historical schedules and `data/step_performance_metrics_exp2.csv` |
| Memory usage | `output/Plots/mem.pdf` | Historical schedules and `data/step_performance_metrics_exp2.csv` |

The figure script also produces pipeline diagrams, combined figures and an additional makespan plot. The six `reference-plots/*.pdf` files were copied from the revised manuscript. `reference-budget-table.csv` records its three budget-table rows.

## Measurements and replay selection

`data/` contains 18 historical schedule CSVs, 16 deployment measurements, per-step timings, resource measurements and deployment overhead measurements. The original dry-run inputs used for scheduling remain in `../scheduler/`.

For the scaled schedule with input 24664 MB, the rebuttal figure script replaces the original 10482-second makespan with the completed replay's 5951-second makespan. It uses the replay's event-level step times for this schedule. The corresponding files are pinned explicitly:

- `data/replay/main_deployment_times.csv`
- `data/replay/main_step_times.csv`

They come from completed replay `full_cachefix_20260613_233836`, dry-run ID 9631. The original CSVs remain unchanged. The figure script's original selection by filesystem modification time was replaced with this explicit path; its statistical and plotting calculations are unchanged. Output paths were also changed to keep generated figures separate from reference artifacts. Optional aborted-run diagnostics are not included or used.

The budget sweep contains 190 rows for 180 settings: nine volumes, ten budgets and two scaling settings. Multiple candidates at 6143 MB/scaling 6 account for the additional rows. They agree on the reported cost and makespan for each setting. The table helper requires that agreement and compares budgets 0.0005 and 1 against budget 100, with one-decimal rounding.

## Provenance and validation

`provenance.json` records source descriptions and SHA-256 hashes. Imported data, timelines and reference plots are unchanged. For adapted source files it also records their source hash.

The archived results remain the reference outputs. See `../KNOWN_LIMITATIONS.md` for the historical transfer-cost issue and parameter semantics. See `VERIFICATION.md` for the checks performed while packaging this repository.
