import csv
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse, FancyArrowPatch, Patch, Rectangle


ANALYSIS_DIR = Path(__file__).resolve().parent
ROOT = ANALYSIS_DIR / "data"
OUT_DIR = ANALYSIS_DIR / "output"
PAPER_FIGURES_DIR = OUT_DIR / "Figures"
PLOTS_DIR = OUT_DIR / "Plots"
MAIN_SCALED_TIMELINE = "timeline_metrics3_20241121_221927_deadline1000_budget100_input24664MB_maxscalability6.csv"

STEP_LABELS = {
    "01-01-retrieve": "Retrieve (1.1)",
    "01-02-prepare-and-store": "Process and store (1.2)",
    "02-01-retrieve": "Retrieve (2.1)",
    "02-02-slice": "Slice (2.2)",
    "02-03-prepare": "Process (2.3)",
}

STEP_ORDER = [
    "01-01-retrieve",
    "01-02-prepare-and-store",
    "02-01-retrieve",
    "02-02-slice",
    "02-03-prepare",
]

STEP_STYLES = {
    "02-01-retrieve": {"color": "blue", "marker": "o"},
    "01-01-retrieve": {"color": "red", "marker": "s"},
    "01-02-prepare-and-store": {"color": "green", "marker": "^"},
    "02-02-slice": {"color": "purple", "marker": "D"},
    "02-03-prepare": {"color": "orange", "marker": "*"},
}


def read_dicts(path):
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def read_performance_metrics(path):
    metrics = {}
    for row in read_dicts(path):
        dry_run_id = row["DRY_RUN_ID"]
        step_name = row["STEP_NAME"]
        if not row["MAX_CPU"] or not row["AVG_CPU"] or not row["MAX_MEM"]:
            continue
        metrics.setdefault(dry_run_id, {})[step_name] = {
            "max_cpu": float(row["MAX_CPU"]),
            "avg_cpu": float(row["AVG_CPU"]),
            "max_mem": float(row["MAX_MEM"]),
        }
    return metrics


def read_measured_step_times(path):
    measured = {}
    for row in read_dicts(path):
        measured.setdefault(row["dry_run_id"], {})[row["job_name"]] = float(row["total_time"])
    return measured


def read_completed_aws_step_times():
    completed = read_completed_aws_makespan()
    if not completed:
        return None
    step_path = completed["path"].with_name(completed["path"].name.replace("deployment_times", "step_times"))
    if not step_path.exists():
        return None
    by_event = {}
    for row in read_dicts(step_path):
        if row.get("dry_run_id") != "9631":
            continue
        by_event[int(row["event_id"])] = {
            "job_name": row["job_name"],
            "total_time": float(row["total_time"]),
        }
    return by_event


def schedule_makespan(path):
    return max(float(row["End Position"]) for row in read_dicts(path) if row["Step Name"] != "source")


def read_completed_aws_makespan():
    """Read the completed replay selected for the revised manuscript."""
    path = ROOT / "replay" / "main_deployment_times.csv"
    for row in read_dicts(path):
        if row.get("dry_run_id") == "9631" and row.get("deployment_csv") == MAIN_SCALED_TIMELINE:
            return {
                "path": path,
                "total_time": float(row["total_time"]),
                "input_mbs": float(row.get("input_mbs") or 24664),
            }
    raise ValueError("The archived completed replay for dry_run_id 9631 is missing.")


def collect_makespan_by_input():
    completed_aws = read_completed_aws_makespan()
    records = []
    for deployment in read_dicts(ROOT / "deployment_times.csv"):
        schedule_csv = deployment["deployment_csv"]
        schedule_path = ROOT / schedule_csv
        if not schedule_path.exists():
            continue
        match = re.search(r"maxscalability(\d+)", schedule_csv)
        maxscalability = int(match.group(1)) if match else 1
        records.append(
            {
                "input_mbs": float(deployment["input_mbs"]),
                "maxscalability": maxscalability,
                "measured_makespan": (
                    completed_aws["total_time"]
                    if completed_aws and schedule_csv == MAIN_SCALED_TIMELINE
                    else float(deployment["total_time"])
                ),
                "predicted_makespan": schedule_makespan(schedule_path),
                "label": "Scaled" if maxscalability > 1 else "Non-scaled",
            }
        )
    return records


def collect_evaluation_data():
    deployments = read_dicts(ROOT / "deployment_times.csv")
    performance_metrics = read_performance_metrics(ROOT / "step_performance_metrics_exp2.csv")
    measured_step_times = read_measured_step_times(ROOT / "step_times.csv")
    completed_aws = read_completed_aws_makespan()
    completed_aws_steps = read_completed_aws_step_times()

    data = {
        "total_predicted_times": [],
        "total_measured_times": [],
        "input_volumes": [],
        "maxscalabilities": [],
        "percentage_differences": [],
        "step_data": {
            step: {
                "predicted_times": [],
                "measured_times": [],
                "predicted_cpus": [],
                "measured_reserved_cpus": [],
                "predicted_memory": [],
                "measured_memory": [],
                "percentage_differences": [],
                "input_volumes": [],
                "maxscalabilities": [],
            }
            for step in STEP_LABELS
        },
    }

    for deployment in deployments:
        dry_run_id = deployment["dry_run_id"]
        schedule_csv = deployment["deployment_csv"]
        schedule_path = ROOT / schedule_csv
        if not schedule_path.exists():
            continue

        match = re.search(r"maxscalability(\d+)", schedule_csv)
        maxscalability = int(match.group(1)) if match else 1
        observed_total_time = (
            completed_aws["total_time"]
            if completed_aws and schedule_csv == MAIN_SCALED_TIMELINE
            else float(deployment["total_time"])
        )
        input_mbs = float(deployment["input_mbs"])
        schedule_steps = read_dicts(schedule_path)
        scheduled_total_time = max(float(step["End Position"]) for step in schedule_steps)

        data["total_predicted_times"].append(scheduled_total_time)
        data["total_measured_times"].append(observed_total_time)
        data["input_volumes"].append(input_mbs)
        data["maxscalabilities"].append(maxscalability)
        data["percentage_differences"].append(
            ((observed_total_time - scheduled_total_time) / observed_total_time) * 100
        )

        event_id = 0
        for step in schedule_steps:
            step_name = step["Step Name"]
            if step_name.lower() == "source":
                continue
            event_id += 1
            if step_name not in STEP_LABELS:
                continue
            if dry_run_id not in performance_metrics or step_name not in performance_metrics[dry_run_id]:
                continue

            start = float(step["Start Position"])
            end = float(step["End Position"])
            predicted_time = end - start
            if completed_aws_steps and schedule_csv == MAIN_SCALED_TIMELINE:
                if event_id not in completed_aws_steps:
                    continue
                measured_time = completed_aws_steps[event_id]["total_time"]
            else:
                if dry_run_id not in measured_step_times or step_name not in measured_step_times[dry_run_id]:
                    continue
                measured_time = measured_step_times[dry_run_id][step_name]
            perf = performance_metrics[dry_run_id][step_name]
            step_bucket = data["step_data"][step_name]
            step_bucket["predicted_times"].append(predicted_time)
            step_bucket["measured_times"].append(measured_time)
            step_bucket["predicted_cpus"].append(float(step["Reserved CPU"]))
            step_bucket["measured_reserved_cpus"].append((perf["max_cpu"] + perf["avg_cpu"]) * 1.2)
            step_bucket["predicted_memory"].append(float(step["Reserved Memory"]))
            step_bucket["measured_memory"].append(perf["max_mem"])
            step_bucket["percentage_differences"].append(
                ((measured_time - predicted_time) / measured_time) * 100
            )
            step_bucket["input_volumes"].append(input_mbs)
            step_bucket["maxscalabilities"].append(maxscalability)

    return data


def save_figure(fig, stem, extra_pdf_paths=None):
    OUT_DIR.mkdir(exist_ok=True)
    for suffix in (".pdf", ".png"):
        fig.savefig(OUT_DIR / f"{stem}{suffix}", bbox_inches="tight", dpi=300)
    for path in extra_pdf_paths or []:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, bbox_inches="tight", dpi=300)
    plt.close(fig)


def label_for_diagram(step_id):
    diagram_labels = {
        "01-01-retrieve": "Retrieve\n(1.1)",
        "01-02-prepare-and-store": "Process and\nstore (1.2)",
        "02-01-retrieve": "Retrieve\n(2.1)",
        "02-02-slice": "Slice\n(2.2)",
        "02-03-prepare": "Process\n(2.3)",
    }
    return diagram_labels[step_id]


def setup_rc():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 8,
            "figure.dpi": 150,
        }
    )


def draw_arrow(ax, start, end, color="black", lw=2.0, style="-", mutation_scale=14):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=mutation_scale,
        linewidth=lw,
        linestyle=style,
        color=color,
        shrinkA=8,
        shrinkB=8,
        zorder=1,
    )
    ax.add_patch(arrow)


def draw_node(ax, xy, text, width=1.35, height=0.82, facecolor="white", edgecolor="black", color="black"):
    ellipse = Ellipse(xy, width, height, facecolor=facecolor, edgecolor=edgecolor, linewidth=1.4, zorder=3)
    ax.add_patch(ellipse)
    ax.text(xy[0], xy[1], text, ha="center", va="center", fontsize=8.0, fontweight="bold", color=color, zorder=4)


def draw_figure_4():
    fig, ax = plt.subplots(figsize=(7.8, 3.4))
    ax.set_aspect("equal")
    ax.axis("off")

    pos = {
        "source": (0, 0),
        "01-01-retrieve": (2.1, 1.05),
        "01-02-prepare-and-store": (4.55, 1.05),
        "02-01-retrieve": (2.1, -1.05),
        "02-02-slice": (4.55, -1.05),
        "02-03-prepare": (7.0, -1.05),
    }

    for start, end in [
        ((0.55, 0.23), (1.38, 0.78)),
        ((0.55, -0.23), (1.38, -0.78)),
        ((2.86, 1.05), (3.78, 1.05)),
        ((2.86, -1.05), (3.78, -1.05)),
        ((5.31, -1.05), (6.23, -1.05)),
    ]:
        draw_arrow(ax, start, end, lw=2.4)

    draw_arrow(ax, (3.78, 0.56), (2.86, 0.56), color="0.45", lw=1.0, style="--", mutation_scale=10)
    ax.plot([4.55, 4.55, 2.1], [1.46, 1.88, 1.88], "--", color="0.55", lw=1, zorder=0)
    ax.text(3.32, 1.95, "sync", ha="center", va="bottom", fontsize=9)

    draw_arrow(ax, (6.23, -0.56), (5.31, -0.56), color="0.45", lw=1.0, style="--", mutation_scale=10)
    ax.plot([7.0, 7.0, 4.55], [-1.46, -1.88, -1.88], "--", color="0.55", lw=1, zorder=0)
    ax.text(5.78, -1.82, "async", ha="center", va="bottom", fontsize=9)

    draw_node(ax, pos["source"], "Source", width=1.35, height=0.78, facecolor="black", color="white")
    for step_id in STEP_LABELS:
        width = 1.72 if step_id == "01-02-prepare-and-store" else 1.52
        draw_node(ax, pos[step_id], label_for_diagram(step_id), width=width, height=0.92)

    ax.set_xlim(-0.9, 7.9)
    ax.set_ylim(-2.18, 2.18)
    save_figure(
        fig,
        "figure_4_pipeline_case_study_relabelled",
        extra_pdf_paths=[PAPER_FIGURES_DIR / "bosch-pipeline.pdf"],
    )


def draw_figure_5():
    fig, ax = plt.subplots(figsize=(5.4, 5.8))
    ax.set_aspect("equal")
    ax.axis("off")

    pos = {
        "source": (0, 0),
        "01-01-retrieve": (-1.35, 1.25),
        "02-01-retrieve": (1.35, 1.25),
        "01-02-prepare-and-store": (-1.35, 2.65),
        "02-02-slice": (1.35, 4.0),
        "02-03-prepare": (-1.35, 4.0),
    }

    for y0, y1, label in [(-0.55, 0.75, "Level 0"), (0.75, 2.05, "Level 1"), (2.05, 4.65, "Level 2")]:
        ax.add_patch(Rectangle((-2.6, y0), 5.2, y1 - y0, fill=False, linestyle="-.", linewidth=1, zorder=0))
        ax.text(-2.75, (y0 + y1) / 2, label, rotation=90, va="center", ha="center", fontsize=10)

    draw_arrow(ax, (-0.35, 0.32), (-1.0, 0.88), color="red", lw=2.0)
    draw_arrow(ax, (0.35, 0.32), (1.0, 0.88), color="red", lw=2.0)
    draw_arrow(ax, (-1.35, 1.68), (-1.35, 2.2), lw=1.8)
    draw_arrow(ax, (1.35, 1.68), (1.35, 3.55), lw=1.8)
    draw_arrow(ax, (0.78, 4.0), (-0.78, 4.0), color="red", lw=2.0)
    draw_arrow(ax, (-1.35, 3.57), (-1.35, 3.1), lw=1.6)
    draw_arrow(ax, (-0.78, 3.78), (0.78, 3.78), lw=1.4, style=":", mutation_scale=12)

    draw_node(ax, pos["source"], "Source", width=1.25, height=0.72, facecolor="black", color="white")
    for step_id in STEP_LABELS:
        width = 1.72 if step_id == "01-02-prepare-and-store" else 1.58
        draw_node(ax, pos[step_id], label_for_diagram(step_id), width=width, height=0.88)

    ax.text(0.0, 3.58, "Asynch.\ndependency", ha="center", va="center", fontsize=9, fontweight="bold", zorder=5)
    ax.text(0.72, 2.6, "Synchronous\ndependency", rotation=90, ha="center", va="center", fontsize=9, fontweight="bold", zorder=5)
    ax.text(2.35, 2.65, "Data", rotation=90, color="red", ha="center", va="center", fontsize=10)

    ax.set_xlim(-2.95, 2.95)
    ax.set_ylim(-0.75, 4.9)
    save_figure(
        fig,
        "figure_5_dependency_levels_relabelled",
        extra_pdf_paths=[PAPER_FIGURES_DIR / "pipeline-levels.pdf"],
    )


def read_deployment_durations():
    durations = {}
    for row in read_dicts(ROOT / "deployment_metrics.csv"):
        step = row["step_name"]
        resource = row["node_name"].lower()
        durations[(step, resource)] = float(row["average_instance_start_time_seconds"])
    return durations


def draw_figure_6():
    schedule = read_dicts(ROOT / "timeline_metrics3_20241121_212353_deadline1000_budget100_input1229MB_maxscalability1.csv")
    deployment_durations = read_deployment_durations()
    fig, ax = plt.subplots(figsize=(7.2, 4.1))

    order = [
        "02-03-prepare",
        "02-02-slice",
        "01-02-prepare-and-store",
        "01-01-retrieve",
        "02-01-retrieve",
        "source",
    ]
    y_pos = {step: len(order) - i for i, step in enumerate(order)}
    colors = {
        "processing": "#55aa18",
        "transmission": "#e10",
        "deployment": "#1155ee",
    }

    row_by_step = {row["Step Name"]: row for row in schedule}
    for step in order:
        row = row_by_step[step]
        start = float(row["Start Position"])
        end = float(row["End Position"])
        resource = row["Resource Name"].lower()
        y = y_pos[step]
        height = 0.55

        deployment = 1.0 if step == "source" else deployment_durations.get((step, resource), 0.0)
        deployment_end = min(start + deployment, end)
        ax.barh(y, deployment_end - start, left=start, height=height, color=colors["deployment"])

        if step == "02-01-retrieve":
            transmission_end = float(row_by_step["02-02-slice"]["Start Position"])
            ax.barh(
                y,
                max(0, transmission_end - deployment_end),
                left=deployment_end,
                height=height,
                color=colors["transmission"],
            )
            processing_start = transmission_end
        else:
            processing_start = deployment_end

        ax.barh(
            y,
            max(0, end - processing_start),
            left=processing_start,
            height=height,
            color=colors["processing"],
        )

    ax.set_yticks([y_pos[step] for step in order])
    ax.set_yticklabels(
        [
            STEP_LABELS.get(step, "Source")
            for step in order
        ]
    )
    ax.set_xlim(0, 230)
    ax.set_xlabel("Time [s]", fontstyle="italic")
    ax.text(162, y_pos["02-02-slice"] + 0.15, "Makespan = 225s", fontstyle="italic", fontsize=10)
    ax.text(162, y_pos["01-02-prepare-and-store"] + 0.35, "Cost = 0.001USD", fontstyle="italic", fontsize=10)
    ax.legend(
        handles=[
            Patch(facecolor=colors["processing"], label="Step processing time"),
            Patch(facecolor=colors["transmission"], label="Data transmission time"),
            Patch(facecolor=colors["deployment"], label="Provisioning & deployment time"),
        ],
        loc="lower right",
        frameon=True,
        fancybox=False,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(False)
    fig.tight_layout()
    save_figure(
        fig,
        "figure_6_timeline_trace_relabelled",
        extra_pdf_paths=[PAPER_FIGURES_DIR / "1300M_no_scaling.drawio.pdf"],
    )


def scatter_by_step(ax, data, x_key, y_key, legend=True):
    for step_id in STEP_ORDER:
        style = STEP_STYLES[step_id]
        bucket = data["step_data"][step_id]
        for index, x in enumerate(bucket[x_key]):
            facecolor = "none" if bucket["maxscalabilities"][index] == 1 else style["color"]
            ax.scatter(
                x,
                bucket[y_key][index],
                edgecolor=style["color"],
                facecolors=facecolor,
                marker=style["marker"],
                label=STEP_LABELS[step_id] if index == 0 else "",
            )
    if legend:
        ax.legend(frameon=True, fontsize=8)


def scale_marker_facecolor(color, maxscalability):
    return "none" if maxscalability == 1 else color


def scale_label(maxscalability):
    return "Non-scaled" if maxscalability == 1 else "Scaled"


def step_legend_handles():
    return [
        Line2D(
            [0],
            [0],
            marker=style["marker"],
            color="none",
            markerfacecolor=style["color"],
            markeredgecolor=style["color"],
            label=STEP_LABELS[step_id],
            markersize=6,
        )
        for step_id in STEP_ORDER
        for style in [STEP_STYLES[step_id]]
    ]


def scaling_legend_handles(marker="o"):
    return [
        Line2D(
            [0],
            [0],
            marker=marker,
            color="black",
            markerfacecolor="none",
            markeredgecolor="black",
            linestyle="none",
            label="Non-scaled",
            markersize=6,
        ),
        Line2D(
            [0],
            [0],
            marker=marker,
            color="black",
            markerfacecolor="black",
            markeredgecolor="black",
            linestyle="none",
            label="Scaled",
            markersize=6,
        ),
    ]


def makespan_scaling_legend_handles(color="blue"):
    return [
        Line2D(
            [0],
            [0],
            marker="o",
            color=color,
            markerfacecolor="white",
            markeredgecolor=color,
            linestyle="none",
            label="Total pipeline makespan (non-scaled)",
            markersize=6,
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color=color,
            markerfacecolor=color,
            markeredgecolor=color,
            linestyle="none",
            label="Total pipeline makespan (scaled)",
            markersize=6,
        ),
    ]


def add_step_and_scaling_legends(ax, step_loc="upper left", scale_loc="lower right"):
    step_legend = ax.legend(handles=step_legend_handles(), loc=step_loc, fontsize=7, frameon=True)
    ax.add_artist(step_legend)
    ax.legend(handles=scaling_legend_handles(), loc=scale_loc, fontsize=7, frameon=True)


def aggregate_repeated_points(xs, ys, maxscalabilities):
    grouped = defaultdict(list)
    for x, y, maxscalability in zip(xs, ys, maxscalabilities):
        grouped[(x, maxscalability)].append(y)

    aggregated = []
    for (x, maxscalability), values in sorted(grouped.items()):
        error = stdev(values) if len(values) > 1 else 0.0
        aggregated.append(
            {
                "x": x,
                "x_plot": x * (0.985 if maxscalability == 1 else 1.015),
                "y": mean(values),
                "yerr": error,
                "n": len(values),
                "maxscalability": maxscalability,
            }
        )
    return aggregated


def plot_aggregated_errorbars(ax, points, color, marker, label=None, show_errorbars=True):
    for index, point in enumerate(points):
        facecolor = scale_marker_facecolor(color, point["maxscalability"])
        ax.errorbar(
            point["x_plot"],
            point["y"],
            yerr=point["yerr"] if show_errorbars and point["yerr"] > 0 else None,
            fmt=marker,
            color=color,
            markerfacecolor=facecolor,
            markeredgecolor=color,
            ecolor=color,
            elinewidth=0.8,
            capsize=2.5,
            markersize=5.5,
            linestyle="none",
            label=label if index == 0 else None,
        )


def plot_step_scatter_with_scaling(ax, data, x_key, y_key, alpha=0.82):
    for step_id in STEP_ORDER:
        style = STEP_STYLES[step_id]
        bucket = data["step_data"][step_id]
        for index, x in enumerate(bucket[x_key]):
            ax.scatter(
                x,
                bucket[y_key][index],
                edgecolor=style["color"],
                facecolors=scale_marker_facecolor(style["color"], bucket["maxscalabilities"][index]),
                marker=style["marker"],
                alpha=alpha,
                s=26,
                linewidths=0.9,
            )


def plot_identity_line(ax, values):
    positive = [value for value in values if value > 0]
    lower = min(positive)
    upper = max(positive)
    ax.plot([lower, upper], [lower, upper], color="red", linestyle="--", linewidth=1)


def draw_figure_7(data):
    fig, axes = plt.subplots(2, 1, figsize=(6.7, 8.4))
    draw_step_difference_axes(axes[0], data, add_title=False)
    axes[0].text(
        0.5,
        -0.28,
        "(a) Percentage difference in predicting the total step execution time",
        transform=axes[0].transAxes,
        ha="center",
    )
    draw_makespan_difference_axes(axes[1], data)
    axes[1].text(
        0.5,
        -0.28,
        "(b) Percentage difference in predicting total pipeline makespan",
        transform=axes[1].transAxes,
        ha="center",
    )
    fig.subplots_adjust(hspace=0.75)
    save_figure(fig, "figure_7_percentage_difference_relabelled")


def draw_figure_8(data):
    fig, axes = plt.subplots(2, 1, figsize=(6.7, 6.8))

    ax = axes[0]
    draw_step_time_axes(ax, data)
    ax.text(0.5, -0.28, "(a) Absolute step execution time", transform=ax.transAxes, ha="center")

    ax = axes[1]
    draw_makespan_axes(ax, data)
    ax.text(0.5, -0.28, "(b) Absolute total pipeline makespan", transform=ax.transAxes, ha="center")

    fig.subplots_adjust(hspace=0.55)
    save_figure(fig, "figure_8_execution_time_relabelled")


def draw_figure_9(data):
    fig, axes = plt.subplots(2, 1, figsize=(6.7, 6.8))

    ax = axes[0]
    draw_cpu_axes(ax, data)
    ax.text(0.5, -0.28, "(a) CPU usage", transform=ax.transAxes, ha="center")

    ax = axes[1]
    draw_memory_axes(ax, data)
    ax.text(0.5, -0.28, "(b) Memory usage", transform=ax.transAxes, ha="center")

    fig.subplots_adjust(hspace=0.55)
    save_figure(fig, "figure_9_resource_usage_relabelled")


def draw_step_difference_axes(ax, data, add_title=True):
    y_values = [
        value
        for bucket in data["step_data"].values()
        for value in bucket["percentage_differences"]
    ]
    margin = max(8, (max(y_values) - min(y_values)) * 0.08)
    for step_id in STEP_ORDER:
        style = STEP_STYLES[step_id]
        bucket = data["step_data"][step_id]
        points = aggregate_repeated_points(
            bucket["input_volumes"],
            bucket["percentage_differences"],
            bucket["maxscalabilities"],
        )
        plot_aggregated_errorbars(
            ax,
            points,
            style["color"],
            style["marker"],
            label=STEP_LABELS[step_id],
            show_errorbars=True,
        )
    ax.axhline(0, color="red", linestyle="--", linewidth=1)
    ax.axvspan(14, 155, color="green", alpha=0.25)
    ax.set_xscale("log")
    ax.set_xlabel("Input Data Volume (MB)")
    ax.set_ylabel("Difference (%)")
    ax.set_ylim(min(y_values) - margin, max(y_values) + margin)
    if add_title:
        ax.set_title("Step execution time")
    step_legend = ax.legend(handles=step_legend_handles(), loc="upper left", fontsize=7, frameon=True)
    ax.add_artist(step_legend)
    scale_handles = scaling_legend_handles()
    scale_handles.append(Patch(facecolor="green", alpha=0.25, label="DRY RUNS"))
    ax.legend(handles=scale_handles, loc="lower right", fontsize=7, frameon=True)


def draw_step_difference_facets(data):
    fig, axes = plt.subplots(3, 2, figsize=(7.0, 6.2), sharex=False, sharey=True)
    axes = axes.ravel()
    y_values = [
        value
        for bucket in data["step_data"].values()
        for value in bucket["percentage_differences"]
    ]
    margin = max(8, (max(y_values) - min(y_values)) * 0.08)

    for index, step_id in enumerate(STEP_ORDER):
        style = STEP_STYLES[step_id]
        ax = axes[index]
        bucket = data["step_data"][step_id]
        points = aggregate_repeated_points(
            bucket["input_volumes"],
            bucket["percentage_differences"],
            bucket["maxscalabilities"],
        )
        plot_aggregated_errorbars(ax, points, style["color"], style["marker"], show_errorbars=True)
        ax.axhline(0, color="red", linestyle="--", linewidth=0.8)
        ax.axvspan(14, 155, color="green", alpha=0.25)
        ax.set_xscale("log")
        ax.set_title(STEP_LABELS[step_id], fontsize=9)
        ax.set_ylim(min(y_values) - margin, max(y_values) + margin)
        ax.tick_params(labelsize=8)
        ax.set_xlabel("Input Data Volume (MB)", fontsize=8)

    axes[-1].axis("off")
    axes[2].set_ylabel("Difference (%)")
    axes[-1].legend(
        handles=[
            *scaling_legend_handles(),
            Patch(facecolor="green", alpha=0.25, label="DRY RUNS"),
        ],
        loc="center",
        fontsize=8,
        frameon=True,
    )
    fig.tight_layout()
    save_figure(fig, "sp_diff_relabelled", extra_pdf_paths=[PLOTS_DIR / "sp_diff.pdf"])


def draw_makespan_difference_axes(ax, data):
    points = aggregate_repeated_points(
        data["input_volumes"],
        data["percentage_differences"],
        data["maxscalabilities"],
    )
    plot_aggregated_errorbars(
        ax,
        points,
        "blue",
        "o",
        label="Total pipeline makespan",
        show_errorbars=True,
    )
    ax.axhline(0, color="red", linestyle="--", linewidth=1)
    ax.axvspan(14, 155, color="green", alpha=0.25)
    ax.set_xscale("log")
    ax.set_xlabel("Input Data Volume (MB)")
    ax.set_ylabel("Difference (%)")
    ax.legend(
        handles=[
            *makespan_scaling_legend_handles("blue"),
            Patch(facecolor="green", alpha=0.25, label="DRY RUNS"),
        ],
        loc="lower left",
        fontsize=7,
        frameon=True,
    )


def draw_step_difference_plot(data):
    draw_step_difference_facets(data)


def draw_makespan_difference_plot(data):
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    draw_makespan_difference_axes(ax, data)
    fig.tight_layout()
    save_figure(fig, "makespan_diff_relabelled", extra_pdf_paths=[PLOTS_DIR / "makespan_diff.pdf"])


def draw_step_time_axes(ax, data):
    plot_step_scatter_with_scaling(ax, data, "predicted_times", "measured_times")
    values = [
        value
        for bucket in data["step_data"].values()
        for value in [*bucket["predicted_times"], *bucket["measured_times"]]
    ]
    plot_identity_line(ax, values)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Predicted Step Time [s]")
    ax.set_ylabel("Real Deployment's Step Time [s]")
    add_step_and_scaling_legends(ax, step_loc="upper left", scale_loc="lower right")


def draw_step_time_plot(data):
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    draw_step_time_axes(ax, data)
    fig.tight_layout()
    save_figure(fig, "sp_relabelled", extra_pdf_paths=[PLOTS_DIR / "sp.pdf"])


def draw_makespan_axes(ax, data):
    for predicted, measured, maxscalability in zip(
        data["total_predicted_times"],
        data["total_measured_times"],
        data["maxscalabilities"],
    ):
        ax.scatter(
            predicted,
            measured,
            edgecolor="black",
            facecolors=scale_marker_facecolor("black", maxscalability),
            marker="o",
            s=26,
            linewidths=0.9,
        )
    plot_identity_line(ax, [*data["total_predicted_times"], *data["total_measured_times"]])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Predicted Makespan [s]")
    ax.set_ylabel("Real Deployment's Makespan [s]")
    ax.legend(handles=makespan_scaling_legend_handles("black"), loc="lower right", fontsize=7, frameon=True)


def draw_makespan_plot(data):
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    draw_makespan_axes(ax, data)
    fig.tight_layout()
    save_figure(fig, "makespan_relabelled", extra_pdf_paths=[PLOTS_DIR / "makespan.pdf"])


def draw_scaling_makespan_by_input_plot():
    records = collect_makespan_by_input()

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    styles = {
        1: {"color": "#2563eb", "marker": "o", "label": "Non-scaled"},
        6: {"color": "#dc2626", "marker": "s", "label": "Scaled"},
    }

    for maxscalability in (1, 6):
        subset = sorted(
            [record for record in records if record["maxscalability"] == maxscalability],
            key=lambda record: record["input_mbs"],
        )
        if not subset:
            continue
        style = styles[maxscalability]
        xs = [record["input_mbs"] for record in subset]
        measured = [record["measured_makespan"] for record in subset]
        predicted = [record["predicted_makespan"] for record in subset]
        ax.plot(
            xs,
            measured,
            color=style["color"],
            marker=style["marker"],
            linewidth=1.7,
            markersize=5,
            label=f"{style['label']} measured",
        )
        ax.plot(
            xs,
            predicted,
            color=style["color"],
            linestyle="--",
            linewidth=1.2,
            alpha=0.82,
            label=f"{style['label']} predicted",
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Input Data Volume (MB)")
    ax.set_ylabel("Makespan [s]")
    ax.grid(True, which="both", axis="y", linestyle=":", linewidth=0.5, alpha=0.55)
    ax.legend(loc="upper left", fontsize=7, frameon=True, ncol=2)
    fig.tight_layout()
    save_figure(
        fig,
        "scaling_makespan_by_input",
        extra_pdf_paths=[PLOTS_DIR / "scaling_makespan_by_input.pdf"],
    )


def draw_cpu_axes(ax, data):
    plot_step_scatter_with_scaling(ax, data, "predicted_cpus", "measured_reserved_cpus")
    values = [
        value
        for bucket in data["step_data"].values()
        for value in [*bucket["predicted_cpus"], *bucket["measured_reserved_cpus"]]
        if value > 0
    ]
    plot_identity_line(ax, values)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Predicted Step CPU [%]")
    ax.set_ylabel("Real Deployment's Step CPU [%]")
    ax.legend(
        handles=[*step_legend_handles(), *scaling_legend_handles()],
        loc="lower right",
        fontsize=7,
        frameon=True,
    )


def draw_cpu_plot(data):
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    draw_cpu_axes(ax, data)
    fig.tight_layout()
    save_figure(fig, "cpu_relabelled", extra_pdf_paths=[PLOTS_DIR / "cpu.pdf"])


def draw_memory_axes(ax, data):
    plot_step_scatter_with_scaling(ax, data, "predicted_memory", "measured_memory")
    values = [
        value
        for bucket in data["step_data"].values()
        for value in [*bucket["predicted_memory"], *bucket["measured_memory"]]
        if value > 0
    ]
    plot_identity_line(ax, values)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Predicted Step Memory [MB]")
    ax.set_ylabel("Real Deployment's Step Memory [MB]")
    add_step_and_scaling_legends(ax, step_loc="upper left", scale_loc="lower right")


def draw_memory_plot(data):
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    draw_memory_axes(ax, data)
    fig.tight_layout()
    save_figure(fig, "mem_relabelled", extra_pdf_paths=[PLOTS_DIR / "mem.pdf"])


def main():
    setup_rc()
    draw_figure_4()
    draw_figure_5()
    draw_figure_6()
    data = collect_evaluation_data()
    draw_figure_7(data)
    draw_figure_8(data)
    draw_figure_9(data)
    draw_step_difference_plot(data)
    draw_makespan_difference_plot(data)
    draw_step_time_plot(data)
    draw_makespan_plot(data)
    draw_scaling_makespan_by_input_plot()
    draw_cpu_plot(data)
    draw_memory_plot(data)
    print(f"Wrote relabelled figures to {OUT_DIR}")


if __name__ == "__main__":
    main()
