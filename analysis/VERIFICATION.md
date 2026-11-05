# Publication-package verification

Verified on 2026-11-05 using Python 3.12 on macOS arm64 and the dependencies in `requirements-reproducible.txt`.

- Regenerated the budget-sensitivity table. All three rows match `reference-budget-table.csv` exactly.
- Ran the full figure-generation script successfully and inspected the makespan figure.
- Compared all evaluation data arrays and makespan records produced by the packaged figure script with the original rebuttal script. They match exactly.
- Checked all 190 archived sweep timeline references and the imported artifact hashes.
- Verified that the original scheduler Python files are byte-for-byte unchanged from commit `8bd6a73`.
- Ran a fresh scheduler sweep for 1229 MB, scaling setting 1 and budgets 0.0005 and 100. Both schedules completed.
- Checked Python syntax and installed dependency consistency.

The fresh example matches the archived compute costs and makespans within relative tolerance 1e-7 and absolute tolerance 1e-8.

The full 180-setting sweep and the live AWS/k3s experiment were not rerun. No scheduler-model fixes were applied. See `../KNOWN_LIMITATIONS.md` for the transfer-cost issue.
