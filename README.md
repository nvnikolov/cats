# CATS: Context-aware Timeline Scheduler

Code and evaluation artifacts for **CATS: Context-aware Timeline Scheduler for Data Pipelines on the Computing Continuum**, submitted to the *Journal of Cloud Computing*.

Paper authors: Nikolay Nikolov, Narges Mehran, Ahmet Soylu, Radu Prodan and Dumitru Roman.

This repository contains the original scheduler and pipeline implementation plus supporting code and results added during rebuttal. The scheduler calculations are preserved, including the limitations described in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Versions and provenance

- Author-maintained repository: https://github.com/nvnikolov/cats
- Original anonymous review snapshot: commit `8bd6a739ef547c586a668c3c2fcbc77bdf995fa2`, preserved by tag `review-submission-2024`.
- Publication package: tag `paper-artifact-2026-11-05`.
- Original review repository: https://github.com/anonymousuni/cats

The publication package adds rebuttal artifacts and reproduction instructions. It removes generated Python bytecode from the current tree. It does not correct the scheduler's historical cost model. See [analysis/provenance.json](analysis/provenance.json) for imported artifact hashes and provenance. A Zenodo DOI has not yet been assigned.

## Contents

| Directory | Contents |
| --- | --- |
| `scheduler/` | Scheduler implementation, dry-run inputs and budget sweep |
| `pipeline/` | Processing steps and container build files |
| `experiment/` | Original testbed setup, dry-run and deployment scripts |
| `samples/` | Original 14 MB sample archive |
| `scheduler-cost-sweep/` | Archived rebuttal sweep: 190 candidate schedules across 180 settings |
| `analysis/` | Measured evaluation data, historical schedules, selected replay, figure and table scripts |

## Install

The packaging verification uses Python 3.12. The pinned environment records the dependencies used for that verification; the original 2024 environment was not recorded.

```sh
git clone https://github.com/nvnikolov/cats.git
cd cats
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements-reproducible.txt
```

## Reproduce the archived analysis

These commands use the included measurements and require no AWS account:

```sh
python analysis/reproduce_budget_table.py
python analysis/rebuild_pipeline_step_figures.py
```

Outputs go to `analysis/output/`. The budget table can also be generated using Python's standard library alone. See [analysis/README.md](analysis/README.md) for the mapping to paper figures and input provenance.

## Run the scheduler

```sh
cd scheduler
python main.py --display_timelines 0
```

The original entry point schedules nine input volumes with scaling settings 1 and 6 and writes timeline CSVs in `scheduler/`. Setting 6 allows up to five replicas because the historical implementation uses an exclusive range endpoint.

A full budget sweep is computationally expensive. Write new results to a separate directory to preserve the archived rebuttal results:

```sh
python cost_sweep.py --output-dir ../analysis/output/new-cost-sweep
```

For a smaller example:

```sh
python cost_sweep.py --input-volumes 1229 --budgets 0.0005 100 --max-scalability-values 1 --representative-inputs 1229 --output-dir ../analysis/output/example-sweep
```

Budget and deadline normalize the objective and are not hard constraints. Reported sweep costs cover modeled cloud compute; Fog compute is modeled as free. Transfer cost still participates in scheduler selection. Read the known limitations before interpreting costs.

## Deploy the pipeline

Follow [experiment/README.md](experiment/README.md) and [pipeline/README.md](pipeline/README.md). These are the original AWS/k3s testbed instructions. Deployment incurs cloud charges. Container image tags and infrastructure packages are not locked to historical digests, and the live cloud deployment has not been revalidated for this package.

The included sample supports a small pipeline run. Larger raw input archives used in the evaluation are not included; the measured CSVs needed to regenerate the published analysis are included. The original experiment documentation describes obtaining additional samples on request.

## Citation and license

Use [CITATION.cff](CITATION.cff) to cite the software artifact. The accompanying article's DOI can be added when available.

Project code is distributed under the [MIT license](LICENSE). The original copyright notice is retained. Bundled third-party utilities retain their own notices.
