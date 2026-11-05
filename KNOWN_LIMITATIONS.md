# Known limitations of the preserved implementation

This package preserves the scheduler used in the research and the rebuttal sweep. The following issues were identified while preparing the publication repository. Their end-to-end effect on the reported schedules has not been quantified.

## Transfer-cost units and volume

`StepTimelineEstimator.estimate_timeline` stores pipeline input volume in MB. `Timeline.calculate_total_data_transmission_cost` passes that number directly to pricing methods documented to accept GB. It also uses pipeline input volume rather than the volume transferred on each edge. Charged transfers can therefore be mispriced. The scheduler includes that transfer cost in candidate selection.

The budget-sweep CSV reports compute-only costs and a compute-only score. `transfer_cost_usd=0` and `transfer_cost_included=False` mean transfer cost was excluded from the report, not that the selected schedule has zero transfer cost. The reported score is not necessarily the scheduler's selection score.

The historical implementation and archived results have been retained. A corrected model should be evaluated separately and released with a clear account of any changed results.

## Interpretation of parameters and costs

- Budget and deadline are normalization parameters, not feasibility bounds. Some archived schedules exceed the nominal deadline.
- Fog compute is modeled as free. A 100% compute-cost saving means eliminating modeled cloud compute charges, not eliminating the complete cost of operating the testbed.
- Scaling value 6 permits up to five replicas because the implementation uses `range(2, max_scalability)`.
- Prices are historical model inputs, not current AWS billing estimates.

## Reproduction boundaries

The pinned dependencies describe the packaging verification environment rather than the undocumented original environment. Archived CSVs and reference plots preserve the original outputs. Scheduling has a combinatorial search and a full sweep can take substantial time. Reference plot PDFs may differ byte-for-byte from regenerated PDFs because of renderer versions, fonts and metadata.

The figure builder explicitly uses completed replay 9631 for the 24664 MB scaled run's makespan and step timings. Other performance measurements remain those in the original evaluation CSVs. The original measurements and replay measurements are both retained and documented in `analysis/README.md`.
