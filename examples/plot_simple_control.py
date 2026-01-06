"""Visualize the simple-control sweep pattern for multiple sweeps."""
from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

Point = Tuple[float, float]


def generate_sweep_points(
    sweeps: int = 10,
    width: float = 1250.0,
    height: float = 1250.0,
    margin: float = 10.0,
    start_spacing: float = 120.0,
    decay: float = 0.75,
    min_spacing: float = 20.0,
) -> List[List[Point]]:
    """Replicate the simple-control sweep generator, returning points per sweep."""
    all_sweeps: List[List[Point]] = []
    spacing = start_spacing
    for sweep in range(1, sweeps + 1):
        # Adjust spacing after every 2nd sweep (coarse -> dense)
        if sweep > 1 and sweep % 2 == 1:
            spacing = max(min_spacing, spacing * decay)

        x_offset = (spacing / 2) if sweep % 2 == 0 else 0
        y_offset = (spacing / 2) if sweep % 3 == 0 else 0

        x = np.arange(margin + x_offset, width - margin, spacing)
        y = np.arange(margin + y_offset, height - margin, spacing)

        if len(x) == 0 or len(y) == 0:
            x = np.arange(margin, width - margin, spacing)
            y = np.arange(margin, height - margin, spacing)

        xx, yy = np.meshgrid(x, y)
        # Serpentine; flip direction each sweep
        xx[1::2] = xx[1::2, ::-1]
        if sweep % 2 == 0:
            # Swap x and y to traverse columns instead of rows
            xx, yy = yy, xx

        pts = list(zip(xx.ravel().tolist(), yy.ravel().tolist()))
        all_sweeps.append(pts)
    return all_sweeps


def plot_sweeps(sweeps: List[List[Point]], width: float, height: float, margin: float) -> None:
    total_plots = len(sweeps) + 1  # extra plot for combined view
    cols = 5
    rows = math.ceil(total_plots / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
    axes = axes.flatten()

    for idx, (ax, pts) in enumerate(zip(axes, sweeps), start=1):
        ax.set_title(f"Sweep {idx}")
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(margin, width - margin)
        ax.set_ylim(margin, height - margin)
        ax.plot(
            [margin, width - margin, width - margin, margin, margin],
            [margin, margin, height - margin, height - margin, margin],
            color="gray",
            linestyle="--",
            linewidth=1,
        )
        if len(pts) > 1:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, linewidth=1.2, color="tab:blue", alpha=0.9)
            ax.scatter(xs[0], ys[0], c="red", s=16, zorder=3, label="start")
            ax.scatter(xs[-1], ys[-1], c="black", s=14, zorder=3, label="end")
        ax.legend(loc="upper right", fontsize="x-small", framealpha=0.7)

    # Combined view on the next available axis
    combined_ax_index = len(sweeps)
    if combined_ax_index < len(axes):
        ax = axes[combined_ax_index]
        ax.set_title("All sweeps")
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(margin, width - margin)
        ax.set_ylim(margin, height - margin)
        ax.plot(
            [margin, width - margin, width - margin, margin, margin],
            [margin, margin, height - margin, height - margin, margin],
            color="gray",
            linestyle="--",
            linewidth=1,
        )
        for idx, pts in enumerate(sweeps):
            if len(pts) < 2:
                continue
            xs, ys = zip(*pts)
            color = plt.cm.plasma(idx / max(len(sweeps) - 1, 1))
            ax.plot(xs, ys, linewidth=1.0, color=color, alpha=0.8, label=f"Sweep {idx+1}")
        if len(sweeps) > 0 and len(sweeps[0]) > 0:
            ax.scatter(
                sweeps[0][0][0],
                sweeps[0][0][1],
                c="red",
                s=18,
                zorder=3,
                label="start (sweep 1)",
            )
        ax.legend(loc="upper right", fontsize="x-small", framealpha=0.7)

    for ax in axes[total_plots:]:
        ax.axis("off")

    plt.tight_layout()
    plt.show()


def main() -> None:
    sweeps = generate_sweep_points()
    plot_sweeps(sweeps, width=1250.0, height=1250.0, margin=10.0)


if __name__ == "__main__":
    main()
