from pipelines.pipeline import *
from resources.computing_resources import *
from scheduling.estimations import *
from dry_runs.dry_run import *
from scheduling.timeline import *
from scheduling.timeline_scheduler import TimelineScheduler, ForcedDeployment

import argparse
import csv
import datetime
import math
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm


DEFAULT_INPUT_VOLUMES = [1229, 2483, 3694, 4914, 6143, 7388, 12296, 24664, 36955]
DEFAULT_BUDGETS = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 1, 100]
DEFAULT_MAX_SCALABILITY_VALUES = [1, 6]
DEFAULT_DEADLINE = 1000
REPRESENTATIVE_INPUTS = [1229, 6143, 36955]


def parse_resources_csv(file_path, network_graph: NetworkGraph) -> List[SimpleComputingResource]:
    resources: List[SimpleComputingResource] = []

    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            name = row['Name']
            memory_capacity = float(row['Memory capacity (GiB)'])
            num_cpus = int(row['Number of CPUs'])
            cpu_frequency = float(row['CPU frequency (GHz)'])
            num_nodes = int(row['Number of nodes'])
            node_type = row['Node type']
            availability_zone = row['AZ']
            on_demand_hourly_rate = float(row['On-demand hourly rate (USD)'])

            for _ in range(num_nodes):
                if node_type == 'EC2':
                    resource = AmazonOnDemandEC2Instance(
                        name=name,
                        num_cpus=num_cpus,
                        cpu_frequency=cpu_frequency,
                        ram_capacity=memory_capacity,
                        availability_zone=availability_zone,
                        on_demand_price_per_hour=on_demand_hourly_rate
                    )
                    network_graph.add_node(resource, [])

                    for existing_node in network_graph.nodes:
                        if existing_node is not resource:
                            if isinstance(existing_node, AmazonOnDemandEC2Instance):
                                network_graph.add_edge(resource, existing_node, 1000)
                                network_graph.add_edge(existing_node, resource, 1000)
                            elif isinstance(existing_node, SimpleComputingResource):
                                network_graph.add_edge(resource, existing_node, 50)
                                network_graph.add_edge(existing_node, resource, 50)
                else:
                    resource = SimpleComputingResource(
                        name=name,
                        num_cpus=num_cpus,
                        cpu_frequency=cpu_frequency,
                        ram_capacity=memory_capacity,
                        total_price=0
                    )
                    network_graph.add_node(resource, [])

                    for existing_node in network_graph.nodes:
                        if existing_node is not resource:
                            if isinstance(existing_node, AmazonOnDemandEC2Instance):
                                network_graph.add_edge(resource, existing_node, 50)
                                network_graph.add_edge(existing_node, resource, 50)
                            elif isinstance(existing_node, SimpleComputingResource):
                                network_graph.add_edge(resource, existing_node, 1000)
                                network_graph.add_edge(existing_node, resource, 1000)

                resources.append(resource)

    return resources


def read_csv(file_path):
    with open(file_path, mode='r') as file:
        reader = csv.DictReader(file)
        return [row for row in reader]


def find_resource_by_name(resources: List[SimpleComputingResource], name):
    for resource in resources:
        if resource.name == name:
            return resource
    return None


def find_step_by_name(steps, name):
    for step in steps:
        if step.name == name:
            return step
    return None


def read_deployment_metrics(file_path):
    deployment_metrics = {}
    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            step_name = row['step_name'].lower()
            node_name = row['node_name'].lower()
            average_instance_start_time_seconds = float(row['average_instance_start_time_seconds'])
            deployment_metrics[(step_name, node_name)] = average_instance_start_time_seconds
    return deployment_metrics


def populate_dry_runs(step_metrics_file, step_performance_metrics_file, deployment_metrics_file, pipeline: Pipeline, eligible_resources: List[SimpleComputingResource], fog1: SimpleComputingResource):
    step_metrics = read_csv(step_metrics_file)
    step_performance_metrics = read_csv(step_performance_metrics_file)
    deployment_metrics = read_deployment_metrics(deployment_metrics_file)

    dry_runs: Dict[int, DryRun] = {}
    zero_timeline = StepExecutionTimeline(
        provisioning_and_deployment_time=1.0,
        data_transmission_time=0.0,
        step_processing_time=0.0
    )

    for metric in step_metrics:
        source = None
        for step in pipeline.steps:
            if step.name == 'source':
                source = step
                break

        dry_run_id = int(metric['DRY_RUN_ID'])
        step_name = metric['STEP_NAME']
        resource_name = metric['RESOURCE_NAME']

        resource = find_resource_by_name(eligible_resources, resource_name)
        step = find_step_by_name(pipeline.steps, step_name)

        if not resource or not step:
            continue

        if dry_run_id not in dry_runs:
            dry_runs[dry_run_id] = DryRun(pipeline)

        provisioning_and_deployment_time = deployment_metrics.get((step_name, resource_name), 0.0)

        timeline = StepExecutionTimeline(
            provisioning_and_deployment_time=provisioning_and_deployment_time,
            data_transmission_time=float(metric['DATA_TRANSMISSION_TIME']) / 1000,
            step_processing_time=float(metric['STEP_PROCESSING_TIME']) / 1000
        )

        if step_name == "02-01-retrieve":
            input_size = float(metric['INPUT_DATA_VOLUME']) / (1024 * 1024)
            source_dry_run_result = StepDryRunResult(
                step=source,
                resource=fog1,
                num_inputs=0,
                input_data_volume=input_size,
                avg_cpu_percentage=0.0,
                max_cpu_percentage=0.0,
                max_memory_usage=0.0,
                timeline=zero_timeline,
                num_outputs=0,
                avg_output_size=0.0,
                pipeline_input_volume=input_size
            )
            dry_runs[dry_run_id].add_step_dry_run(source_dry_run_result)

        step_dry_run_result = StepDryRunResult(
            step=step,
            resource=resource,
            num_inputs=int(metric['NUM_INPUTS']),
            input_data_volume=float(metric['INPUT_DATA_VOLUME']) / (1024 * 1024),
            avg_cpu_percentage=0,
            max_cpu_percentage=0,
            max_memory_usage=0,
            timeline=timeline,
            num_outputs=int(metric['NUM_OUTPUTS']),
            avg_output_size=float(metric['OUTPUT_DATA_VOLUME']) / (1024 * 1024)
        )

        dry_runs[dry_run_id].add_step_dry_run(step_dry_run_result)

    for metric in step_performance_metrics:
        dry_run_id = int(metric['DRY_RUN_ID'])
        step_name = metric['STEP_NAME']
        resource_name = metric['RESOURCE_NAME']

        resource = find_resource_by_name(eligible_resources, resource_name)
        step = find_step_by_name(pipeline.steps, step_name)

        if not resource or not step:
            continue

        for step_dry_run in dry_runs[dry_run_id].step_dry_runs:
            if step_dry_run.step == step and step_dry_run.resource == resource:
                step_dry_run.avg_cpu_percentage = float(metric['AVG_CPU']) if metric['AVG_CPU'] else 0.0
                step_dry_run.max_cpu_percentage = float(metric['MAX_CPU']) if metric['MAX_CPU'] else 0.0
                step_dry_run.max_memory_usage = float(metric['MAX_MEM']) if metric['MAX_MEM'] else 0.0

    return dry_runs


def build_experiment_context(scheduler_dir: Path):
    source = DataSource("source")
    retrieve_1_1 = BatchStep("01-01-retrieve")
    process_1_2 = BatchStep("01-02-prepare-and-store")

    retrieve_2_1 = BatchStep("02-01-retrieve")
    slice_2_2 = ProducerStep("02-02-slice")
    process_2_3 = ConsumerStep("02-03-prepare")

    pipeline = Pipeline()
    pipeline.add_connection(source, retrieve_1_1)
    pipeline.add_connection(retrieve_1_1, process_1_2)
    pipeline.add_connection(source, retrieve_2_1)
    pipeline.add_connection(retrieve_2_1, slice_2_2)
    pipeline.add_connection(slice_2_2, process_2_3)
    pipeline.add_dependency("asynchronous", process_2_3, slice_2_2)
    pipeline.add_dependency("synchronous", process_2_3, process_1_2)

    network_graph = NetworkGraph()
    resources = parse_resources_csv(scheduler_dir / 'resources.csv', network_graph=network_graph)
    fog1 = find_resource_by_name(resources, "fog1")
    forced_deployment = ForcedDeployment(source, fog1)
    fog1.disable_scheduling()

    eligible_resources = network_graph.get_eligible_computing_resources()
    dry_runs = populate_dry_runs(
        scheduler_dir / 'step_metrics.csv',
        scheduler_dir / 'step_performance_metrics.csv',
        scheduler_dir / 'deployment_metrics.csv',
        pipeline,
        eligible_resources,
        fog1
    )

    return pipeline, network_graph, list(dry_runs.values()), forced_deployment


def budget_label(budget: float) -> str:
    return f"{budget:g}".replace(".", "p")


def resource_signature(timeline: Timeline) -> str:
    return "|".join(
        f"{event.step_execution_timeline_estimation.pipeline_step.name}@{event.resource_reservation.resource.name}"
        for event in timeline.events
    )


def cloud_step_placements(timeline: Timeline) -> int:
    return sum(
        1
        for event in timeline.events
        if isinstance(event.resource_reservation.resource, AmazonOnDemandEC2Instance)
    )


def compute_cost(timeline: Timeline) -> float:
    return timeline.calculate_timeline_resource_cost()


def write_summary_csv(rows, path: Path):
    fieldnames = [
        'input_mb',
        'max_scalability',
        'deadline',
        'budget',
        'makespan_s',
        'compute_cost_usd',
        'transfer_cost_usd',
        'total_cost_usd',
        'transfer_cost_included',
        'time_fraction',
        'cost_fraction',
        'score',
        'cloud_step_placements',
        'resource_signature',
        'timeline_file'
    ]
    with open(path, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_sensitivity_summary(rows, path: Path):
    fieldnames = [
        'input_mb',
        'max_scalability',
        'baseline_budget',
        'baseline_cost_usd',
        'baseline_makespan_s',
        'cheapest_budget',
        'cheapest_cost_usd',
        'cheapest_makespan_s',
        'cost_reduction_vs_baseline_pct',
        'makespan_increase_vs_baseline_pct',
        'fastest_budget',
        'fastest_cost_usd',
        'fastest_makespan_s'
    ]

    grouped = {}
    for row in rows:
        key = (row['input_mb'], row['max_scalability'])
        grouped.setdefault(key, []).append(row)

    summary_rows = []
    for key, group in sorted(grouped.items()):
        baseline = next((row for row in group if math.isclose(float(row['budget']), 100.0)), None)
        cheapest = min(group, key=lambda row: (float(row['total_cost_usd']), float(row['makespan_s'])))
        fastest = min(group, key=lambda row: (float(row['makespan_s']), float(row['total_cost_usd'])))

        baseline_cost = float(baseline['total_cost_usd']) if baseline else None
        baseline_makespan = float(baseline['makespan_s']) if baseline else None
        cheapest_cost = float(cheapest['total_cost_usd'])
        cheapest_makespan = float(cheapest['makespan_s'])

        cost_reduction = ''
        makespan_increase = ''
        if baseline_cost is not None and baseline_cost != 0:
            cost_reduction = (baseline_cost - cheapest_cost) / baseline_cost * 100
        if baseline_makespan is not None and baseline_makespan != 0:
            makespan_increase = (cheapest_makespan - baseline_makespan) / baseline_makespan * 100

        summary_rows.append({
            'input_mb': key[0],
            'max_scalability': key[1],
            'baseline_budget': 100 if baseline else '',
            'baseline_cost_usd': baseline_cost if baseline_cost is not None else '',
            'baseline_makespan_s': baseline_makespan if baseline_makespan is not None else '',
            'cheapest_budget': cheapest['budget'],
            'cheapest_cost_usd': cheapest_cost,
            'cheapest_makespan_s': cheapest_makespan,
            'cost_reduction_vs_baseline_pct': cost_reduction,
            'makespan_increase_vs_baseline_pct': makespan_increase,
            'fastest_budget': fastest['budget'],
            'fastest_cost_usd': fastest['total_cost_usd'],
            'fastest_makespan_s': fastest['makespan_s']
        })

    with open(path, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)


def write_tradeoff_figure(rows, output_path: Path, representative_inputs: List[int]):
    figure_rows = [row for row in rows if int(row['input_mb']) in representative_inputs]
    if not figure_rows:
        return

    budgets = [float(row['budget']) for row in figure_rows]
    norm = LogNorm(vmin=min(budgets), vmax=max(budgets))
    markers = {1: 'o', 6: '^'}

    fig, axes = plt.subplots(
        1,
        len(representative_inputs),
        figsize=(5 * len(representative_inputs), 4),
        sharey=False,
        constrained_layout=True
    )
    if len(representative_inputs) == 1:
        axes = [axes]

    scatter_for_colorbar = None
    for ax, input_mb in zip(axes, representative_inputs):
        subset = [row for row in figure_rows if int(row['input_mb']) == input_mb]
        for max_scalability in sorted({int(row['max_scalability']) for row in subset}):
            series = [row for row in subset if int(row['max_scalability']) == max_scalability]
            scatter_for_colorbar = ax.scatter(
                [float(row['total_cost_usd']) for row in series],
                [float(row['makespan_s']) for row in series],
                c=[float(row['budget']) for row in series],
                cmap='viridis',
                norm=norm,
                marker=markers.get(max_scalability, 's'),
                label=f'max scalability {max_scalability}',
                edgecolors='black',
                linewidths=0.5
            )
        ax.set_title(f'{input_mb} MB')
        ax.set_xlabel('Modeled compute cost [USD]')
        ax.grid(True, linestyle='--', alpha=0.35)

    axes[0].set_ylabel('Predicted makespan [s]')
    axes[-1].legend(loc='best')
    fig.colorbar(scatter_for_colorbar, ax=axes, label='Budget [USD]')
    fig.suptitle('CATS budget sensitivity: cost-makespan trade-off')
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def parse_args():
    parser = argparse.ArgumentParser(description='Run a CATS budget-sensitivity cost sweep.')
    parser.add_argument('--output-dir', default='../scheduler-cost-sweep', help='Directory where timelines, summaries, and figures will be written.')
    parser.add_argument('--deadline', type=float, default=DEFAULT_DEADLINE, help='Deadline used to normalize makespan.')
    parser.add_argument('--input-volumes', type=float, nargs='+', default=DEFAULT_INPUT_VOLUMES, help='Input volumes in MB.')
    parser.add_argument('--budgets', type=float, nargs='+', default=DEFAULT_BUDGETS, help='Budget values in USD.')
    parser.add_argument('--max-scalability-values', type=int, nargs='+', default=DEFAULT_MAX_SCALABILITY_VALUES, help='Maximum scalability settings to sweep.')
    parser.add_argument('--representative-inputs', type=int, nargs='+', default=REPRESENTATIVE_INPUTS, help='Input volumes to include in the trade-off figure.')
    return parser.parse_args()


def main():
    args = parse_args()
    scheduler_dir = Path(__file__).resolve().parent
    output_dir = (scheduler_dir / args.output_dir).resolve()
    timelines_dir = output_dir / 'timelines'
    timelines_dir.mkdir(parents=True, exist_ok=True)

    pipeline, network_graph, all_dry_runs, forced_deployment = build_experiment_context(scheduler_dir)

    rows = []
    for input_volume in args.input_volumes:
        input_label = int(input_volume) if float(input_volume).is_integer() else input_volume
        for max_scalability in args.max_scalability_values:
            scheduler = TimelineScheduler(
                pipeline,
                network_graph,
                all_dry_runs,
                args.deadline,
                args.budgets[0],
                input_volume,
                [forced_deployment],
                max_scalability
            )
            for budget in args.budgets:
                scheduler.budget = budget
                scheduler.deadline = args.deadline
                scheduler.max_scalability = max_scalability
                resulting_timelines = scheduler.schedule()

                for timeline_index, timeline in enumerate(resulting_timelines, start=1):
                    current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    timeline_file = timelines_dir / (
                        f"timeline_costsweep_{current_time}_deadline{args.deadline:g}_"
                        f"budget{budget_label(budget)}_input{input_label}MB_"
                        f"maxscalability{max_scalability}_candidate{timeline_index}.csv"
                    )
                    timeline.serialize_to_csv(timeline_file)

                    makespan = timeline.calculate_timeline_total_time()
                    compute_cost_usd = compute_cost(timeline)
                    transfer_cost_usd = 0.0
                    total_cost_usd = compute_cost_usd
                    time_fraction = makespan / args.deadline
                    cost_fraction = total_cost_usd / budget
                    score = time_fraction + cost_fraction

                    rows.append({
                        'input_mb': input_label,
                        'max_scalability': max_scalability,
                        'deadline': args.deadline,
                        'budget': budget,
                        'makespan_s': makespan,
                        'compute_cost_usd': compute_cost_usd,
                        'transfer_cost_usd': transfer_cost_usd,
                        'total_cost_usd': total_cost_usd,
                        'transfer_cost_included': False,
                        'time_fraction': time_fraction,
                        'cost_fraction': cost_fraction,
                        'score': score,
                        'cloud_step_placements': cloud_step_placements(timeline),
                        'resource_signature': resource_signature(timeline),
                        'timeline_file': str(timeline_file.relative_to(output_dir))
                    })

    summary_path = output_dir / 'cost_sweep_summary.csv'
    sensitivity_path = output_dir / 'budget_sensitivity_summary.csv'
    figure_path = output_dir / 'cost_makespan_tradeoff.png'

    write_summary_csv(rows, summary_path)
    write_sensitivity_summary(rows, sensitivity_path)
    write_tradeoff_figure(rows, figure_path, args.representative_inputs)

    print(f'Wrote {len(rows)} schedule rows to {summary_path}')
    print(f'Wrote budget sensitivity summary to {sensitivity_path}')
    print(f'Wrote cost-makespan figure to {figure_path}')
    print('Transfer costs are excluded from reported totals because available schedule CSVs do not store edge data volumes.')


if __name__ == '__main__':
    main()
