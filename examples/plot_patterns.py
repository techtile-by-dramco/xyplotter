"""Visualize XY plotter patterns with matplotlib, mimicking motion order."""
from __future__ import annotations

import argparse
import math
from typing import Iterable, List, Sequence, Tuple

# Local import support when running the script directly from the repo
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
for path in (SRC_DIR, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import matplotlib.pyplot as plt

from xyplotter import (
    WorkArea,
    available_patterns,
    hilbert_curve,
    resolve_pattern,
)

Point = Tuple[float, float]


def sample_pattern(area: WorkArea, pattern_name: str, max_points: int) -> List[Point]:
    """Collect points from a named pattern with a safety cap."""
    generator = resolve_pattern(pattern_name)(area)
    points: List[Point] = []

    for idx, pt in enumerate(generator):
        if max_points and idx >= max_points:
            break
        points.append(pt)

    return points


def plot_path(ax, points: Sequence[Point], area: WorkArea, title: str) -> None:
    """Plot path segments in order, similar to how the plotter would move."""
    ax.set_title(title)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(area.xmin, area.xmax)
    ax.set_ylim(area.ymin, area.ymax)

    # Draw work envelope
    ax.plot(
        [area.xmin, area.xmax, area.xmax, area.xmin, area.xmin],
        [area.ymin, area.ymin, area.ymax, area.ymax, area.ymin],
        color="gray",
        linestyle="--",
        linewidth=1,
    )

    if len(points) < 2:
        return

    xs, ys = zip(*points)
    # Color path by progress to mimic time ordering
    colors = [i / (len(points) - 1) for i in range(len(points) - 1)]
    for i in range(len(points) - 1):
        ax.plot(
            [points[i][0], points[i + 1][0]],
            [points[i][1], points[i + 1][1]],
            color=plt.cm.viridis(colors[i]),
            linewidth=1.2,
        )

    # Mark start and end
    ax.scatter(xs[0], ys[0], c="red", s=20, label="start", zorder=3)
    ax.scatter(xs[-1], ys[-1], c="black", s=16, label="end", zorder=3)
    ax.legend(loc="upper right", fontsize="small", framealpha=0.8)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot XY plotter patterns.")
    parser.add_argument(
        "--pattern",
        choices=available_patterns(),
        default="center_out_refined_spiral",
        help="Pattern name to plot (ignored if --all is set).",
    )
    parser.add_argument("--all", action="store_true", help="Plot all available patterns.")
    parser.add_argument("--width", type=float, default=1250.0, help="Work area width.")
    parser.add_argument("--height", type=float, default=1250.0, help="Work area height.")
    parser.add_argument("--margin", type=float, default=10.0, help="Work area margin.")
    parser.add_argument(
        "--max-points",
        type=int,
        default=8000,
        help="Safety cap on number of points to draw per pattern.",
    )
    parser.add_argument(
        "--sweeps",
        type=int,
        default=1,
        help="When plotting a single pattern, draw multiple sweeps increasing density each time.",
    )
    parser.add_argument(
        "--density-factor",
        type=float,
        default=2.0,
        help="Controls how quickly sweeps get denser (used for non-Hilbert patterns).",
    )
    args = parser.parse_args()

    if args.sweeps < 1:
        parser.error("--sweeps must be >= 1")
    if args.density_factor <= 1.0 and not args.all and args.sweeps > 1:
        parser.error("--density-factor must be > 1 when using multiple sweeps")

    area = WorkArea(width=args.width, height=args.height, margin=args.margin)
    pattern_names = list(available_patterns()) if args.all else [args.pattern]

    if args.all:
        cols = math.ceil(math.sqrt(len(pattern_names)))
        rows = math.ceil(len(pattern_names) / cols)
        fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
        axes = axes.flatten() if isinstance(axes, Iterable) else [axes]
        for ax, name in zip(axes, pattern_names):
            pts = sample_pattern(area, name, args.max_points)
            plot_path(ax, pts, area, name)
        # Hide any unused axes
        for ax in axes[len(pattern_names) :]:
            ax.axis("off")
    else:
        pattern_name = pattern_names[0]
        cols = min(3, args.sweeps)
        rows = math.ceil(args.sweeps / cols)
        fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 5 * rows))
        axes = axes.flatten() if isinstance(axes, Iterable) else [axes]

        if pattern_name == "hilbert":
            # Increase Hilbert order each sweep. Total points per order: (2**order)^2 = 4**order
            max_order = max(1, int(math.log(max(args.max_points, 1), 4)))
            orders = [min(i + 1, max_order) for i in range(args.sweeps)]
            for ax, order in zip(axes, orders):
                pts = list(hilbert_curve(area, order=order))
                title = f"{pattern_name} (order {order})"
                plot_path(ax, pts, area, title)
            used_axes = len(orders)
        else:
            # Build multiple sweeps from coarse to dense by subsampling the full pattern
            full_pts = sample_pattern(area, pattern_name, args.max_points)
            sweeps = args.sweeps
            # stride decreases each sweep so density increases; last sweep is stride 1
            strides = [
                max(1, int(round(args.density_factor ** (sweeps - i - 1))))
                for i in range(sweeps)
            ]
            for sweep_idx, (ax, stride) in enumerate(zip(axes, strides), start=1):
                pts = full_pts[::stride] if stride > 1 else full_pts
                title = f"{pattern_name} (sweep {sweep_idx}, stride {stride})"
                plot_path(ax, pts, area, title)
            used_axes = len(strides)

        for ax in axes[used_axes:]:
            ax.axis("off")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
