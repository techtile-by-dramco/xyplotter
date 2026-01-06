"""XYPlotter control library for Techtile hardware."""

from .xyplotter import (
    DEFAULT_PATTERN,
    PATTERN_REGISTRY,
    XYPlotter,
    WorkArea,
    available_patterns,
    center_out_refined_spiral,
    concentric_square_rings,
    hilbert_curve,
    phyllotaxis_fill,
    progressive_raster,
    radial_spokes,
    resolve_pattern,
    serpentine_grid,
    wait_till_go_from_server,
)

__version__ = "0.1.0"

__all__ = [
    "XYPlotter",
    "WorkArea",
    "DEFAULT_PATTERN",
    "PATTERN_REGISTRY",
    "available_patterns",
    "concentric_square_rings",
    "center_out_refined_spiral",
    "hilbert_curve",
    "phyllotaxis_fill",
    "radial_spokes",
    "resolve_pattern",
    "progressive_raster",
    "serpentine_grid",
    "wait_till_go_from_server",
    "__version__",
]
