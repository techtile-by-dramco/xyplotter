# xyplotter

Lib to control the XYPlotter of Techtile.

## Installation

Install from a local checkout:

```bash
pip install .
```

Install directly from GitHub (replace the URL if your remote differs):

```bash
pip install git+https://github.com/Calle/xyplotter.git
```

Build a wheel locally (outputs to `dist/`):

```bash
python -m pip install --upgrade pip build
python -m build
```

## Usage

The library exposes a small controller class plus pattern generators. The default pattern starts in the center, spirals outward, and reduces its spacing after each full turn to sweep quickly before refining.

```python
from xyplotter import XYPlotter, WorkArea

area = WorkArea(width=1250, height=1250, margin=10)

with XYPlotter(port="COM3") as plotter:
    plotter.home()
    plotter.run_pattern(area)  # uses the center-out refined spiral by default
```

To run a different pattern, provide a callable that accepts a `WorkArea` and yields `(x, y)` points:

```python
from xyplotter import serpentine_grid, progressive_raster

with XYPlotter(port="COM3") as plotter:
    plotter.home()

    # Simple zig-zag raster at fixed spacing
    plotter.run_pattern(area, pattern=lambda a: serpentine_grid(a, spacing=100))

    # Multiple passes, getting denser each time
    plotter.run_pattern(
        area,
        pattern=lambda a: progressive_raster(a, initial_spacing=300, passes=3, spacing_decay=0.6),
    )
```

### Built-in pattern names

You can also choose by name using `run_pattern(area, pattern="pattern_name")`. Available names:

- `center_out_refined_spiral` (default): center start, spiral outward, tighter spacing each turn.
- `serpentine_100`: zig-zag raster at 100 mm spacing.
- `progressive_raster`: multiple rasters, densifying each pass.
- `concentric_squares`: expanding square perimeters from the center.
- `radial_spokes`: repeated starburst rays expanding outward.
- `phyllotaxis`: golden-angle spiral with even coverage.
- `hilbert`: space-filling Hilbert curve over the largest inscribed square.

## Visualize patterns

An example script plots the path order using matplotlib (no hardware needed):

```bash
python examples/plot_patterns.py --all
# or a single pattern
python examples/plot_patterns.py --pattern center_out_refined_spiral
```

All motion commands are sent as standard GRBL-compatible G-code.
