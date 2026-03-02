from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import ceil
from typing import Iterable, List, Optional, Tuple, Dict


# -----------------------------
# Core domain models
# -----------------------------
class GradeDirection(str, Enum):
    """
    Direction of "UP" slope across the plan.
    Define which axis is the slope axis.
    You can align this with your Figma UI labels.
    """
    UP = "UP"         # +Y
    DOWN = "DOWN"     # -Y
    LEFT = "LEFT"     # -X
    RIGHT = "RIGHT"   # +X


@dataclass(frozen=True)
class MegaVaultModuleSpec:
    """
    Confirm these with engineering / Excel:
    - module length/width define grid cell footprint
    - module_void_volume_m3 should be the storage per module at full internal height
      (you mentioned 21.02 m³)
    - internal_height_m is the internal height of one module stack (if fixed).
    """
    module_length_m: float
    module_width_m: float
    module_void_volume_m3: float  # e.g., 21.02 m³
    internal_height_m: float      # internal storage height per module stack


@dataclass(frozen=True)
class MegaVaultInputs:
    target_effective_volume_kl: float            # kL == m³
    internal_height_m: float                     # can be pulled from spec, but allow input
    max_storage_height_m: float
    tank_grade: float                            # 0.01 for 1%
    grade_direction: GradeDirection
    hed_volume_to_subtract_m3: float
    filter_bay_volume_to_subtract_m3: float
    # stage table settings
    tank_invert_level_m: float = 0.0
    stage_step_m: float = 0.05                   # 50 mm steps default
    stage_max_height_m: Optional[float] = None   # if None, use computed effective height cap


@dataclass(frozen=True)
class MegaVaultSelection:
    """
    The grid selection as a set of (row, col) indices selected by user.
    Row/col are 0-indexed.
    """
    selected_cells: Tuple[Tuple[int, int], ...]
    grid_rows: int
    grid_cols: int


@dataclass(frozen=True)
class MegaVaultResult:
    modules_selected: int
    modules_to_meet_target: Optional[int]  # if you compute auto-sizing
    tank_length_m: float
    tank_width_m: float

    # Heights
    min_storage_height_m: float
    effective_storage_height_m: float  # representative/average depth at full stage

    # Volumes
    proposed_total_volume_kl: float
    proposed_effective_volume_kl: float

    # Metadata
    deductions_m3: float
    notes: List[str]


@dataclass(frozen=True)
class StageRow:
    stage_level_m: float           # absolute water level (invert + depth)
    depth_m: float                 # depth above invert
    wetted_area_m2: float
    incremental_volume_m3: float
    cumulative_volume_m3: float
    cumulative_effective_m3: float # after deductions (deductions applied once at end, see notes)


# -----------------------------
# Validation
# -----------------------------
def validate_inputs(inputs: MegaVaultInputs) -> None:
    if inputs.target_effective_volume_kl <= 0:
        raise ValueError("Target Effective Volume must be > 0 kL")

    if inputs.internal_height_m <= 0:
        raise ValueError("Internal Megavault Height must be > 0 m")

    if inputs.max_storage_height_m <= 0:
        raise ValueError("Max Storage Height must be > 0 m")

    # Your stated rule: Max Storage Height ≤ Internal Height
    # (If your current Excel allows the opposite, flip this rule.)
    if inputs.max_storage_height_m > inputs.internal_height_m:
        raise ValueError("Rule: Max Storage Height must be ≤ Internal Height")

    if inputs.tank_grade < 0:
        raise ValueError("Tank Grade must be ≥ 0")

    if inputs.hed_volume_to_subtract_m3 < 0 or inputs.filter_bay_volume_to_subtract_m3 < 0:
        raise ValueError("HED/Filter volumes cannot be negative")


def validate_selection(sel: MegaVaultSelection) -> None:
    if sel.grid_rows <= 0 or sel.grid_cols <= 0:
        raise ValueError("Grid rows/columns must be > 0")

    if len(sel.selected_cells) < 1:
        raise ValueError("At least 1 module must be selected")

    for r, c in sel.selected_cells:
        if not (0 <= r < sel.grid_rows and 0 <= c < sel.grid_cols):
            raise ValueError(f"Selected cell ({r},{c}) is outside the grid bounds")


# -----------------------------
# Geometry helpers
# -----------------------------
def bounding_box_cells(cells: Iterable[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    """
    Returns (min_row, max_row, min_col, max_col) inclusive.
    """
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return min(rows), max(rows), min(cols), max(cols)


def footprint_dimensions_from_cells(
    cells: Iterable[Tuple[int, int]],
    spec: MegaVaultModuleSpec
) -> Tuple[float, float]:
    """
    Calculates overall tank length/width based on bounding rectangle of selection.
    This matches most grid-based tools: length/width is the outer extents,
    not the perimeter length of an irregular polygon.

    If your Excel calculates length/width differently, adjust here.
    """
    min_r, max_r, min_c, max_c = bounding_box_cells(cells)
    n_rows = (max_r - min_r + 1)
    n_cols = (max_c - min_c + 1)

    # Convention: rows map to "length" axis (Y), cols map to "width" axis (X)
    length_m = n_rows * spec.module_length_m
    width_m = n_cols * spec.module_width_m
    return length_m, width_m


def cell_center_xy(r: int, c: int, spec: MegaVaultModuleSpec) -> Tuple[float, float]:
    """
    Defines an (x,y) plane where:
    - x increases with column
    - y increases with row
    (0,0) at top-left is fine as long as consistent.
    """
    x = (c + 0.5) * spec.module_width_m
    y = (r + 0.5) * spec.module_length_m
    return x, y


def floor_offset_due_to_grade(x: float, y: float, inputs: MegaVaultInputs) -> float:
    """
    Returns the floor elevation offset (m) due to tank grade at point (x,y),
    relative to a reference at (0,0).
    """
    g = inputs.tank_grade
    if g == 0:
        return 0.0

    if inputs.grade_direction == GradeDirection.UP:
        return g * y
    if inputs.grade_direction == GradeDirection.DOWN:
        return -g * y
    if inputs.grade_direction == GradeDirection.RIGHT:
        return g * x
    if inputs.grade_direction == GradeDirection.LEFT:
        return -g * x

    # Should never happen due to Enum
    raise ValueError("Invalid grade direction")


# -----------------------------
# Volume engine (graded tank)
# -----------------------------
def compute_depth_at_cell(
    water_depth_m: float,
    r: int,
    c: int,
    inputs: MegaVaultInputs,
    spec: MegaVaultModuleSpec,
    reference_origin_xy: Tuple[float, float]
) -> float:
    """
    Computes effective water depth at a given cell, accounting for floor slope.

    water_depth_m is depth at reference origin (or invert).
    We adjust cell depth by subtracting local floor rise relative to origin.
    """
    x, y = cell_center_xy(r, c, spec)
    x0, y0 = reference_origin_xy

    z0 = floor_offset_due_to_grade(x0, y0, inputs)
    z = floor_offset_due_to_grade(x, y, inputs)

    # If floor is higher at (x,y), local depth is lower
    local_depth = water_depth_m - (z - z0)

    # Clamp between 0 and max storage height (and internal height)
    cap = min(inputs.internal_height_m, inputs.max_storage_height_m)
    return max(0.0, min(cap, local_depth))


def compute_storage_for_depth(
    sel: MegaVaultSelection,
    inputs: MegaVaultInputs,
    spec: MegaVaultModuleSpec,
    water_depth_m: float
) -> Tuple[float, float, float]:
    """
    Returns (total_volume_m3, wetted_area_m2, avg_depth_m) at a given reference depth.

    We approximate tank volume by summing depth * cell_area across selected cells.
    This is a robust approach and matches the idea of Excel stage integration
    (and it supports irregular shapes naturally).

    If your Excel uses exact geometry beyond cell-based integration,
    you can increase precision by using smaller sub-cells per module.
    """
    cell_area = spec.module_length_m * spec.module_width_m
    cells = sel.selected_cells
    if not cells:
        return 0.0, 0.0, 0.0

    # Use the lowest (or first) selected cell center as reference origin
    # You can align this to Excel convention (e.g., bottom-left corner).
    ref_r, ref_c = cells[0]
    ref_xy = cell_center_xy(ref_r, ref_c, spec)

    total_vol = 0.0
    wetted_area = 0.0
    depth_sum = 0.0

    for r, c in cells:
        d = compute_depth_at_cell(water_depth_m, r, c, inputs, spec, ref_xy)
        if d > 0:
            wetted_area += cell_area
        total_vol += d * cell_area
        depth_sum += d

    avg_depth = depth_sum / len(cells)
    return total_vol, wetted_area, avg_depth


def apply_deductions(effective_m3: float, inputs: MegaVaultInputs) -> float:
    deductions = inputs.hed_volume_to_subtract_m3 + inputs.filter_bay_volume_to_subtract_m3
    out = effective_m3 - deductions
    return max(0.0, out)


# -----------------------------
# Main sizing function
# -----------------------------
def calculate_megavault(
    sel: MegaVaultSelection,
    inputs: MegaVaultInputs,
    spec: MegaVaultModuleSpec,
    *,
    auto_size: bool = True
) -> MegaVaultResult:
    """
    Calculates tank footprint + volumes at full storage (capped) and (optionally)
    finds modules needed to meet target effective volume using incremental sizing.

    NOTE: "100% Excel replication" requires matching Excel’s exact conventions:
    - reference point for grade
    - whether total volume uses module void volume (21.02) vs geometric integration
    - whether there are porosity/efficiency factors
    This engine is built so you can lock those in once Excel is confirmed.
    """
    validate_inputs(inputs)
    validate_selection(sel)

    notes: List[str] = []

    # Basic counts + footprint
    modules_selected = len(sel.selected_cells)
    length_m, width_m = footprint_dimensions_from_cells(sel.selected_cells, spec)

    # Compute full-stage storage at cap depth (reference depth = cap)
    cap_depth = min(inputs.internal_height_m, inputs.max_storage_height_m)

    total_m3, wetted_area_m2, avg_depth_m = compute_storage_for_depth(sel, inputs, spec, water_depth_m=cap_depth)

    # Decide what "Total volume" means:
    # Option A (common): total geometric water volume under slope at cap depth => total_m3
    # Option B (some Excel): module void volume * modules (at full internal height), independent of grade.
    # If Excel uses module volume (21.02) for "Total" then do:
    # total_m3 = modules_selected * spec.module_void_volume_m3
    #
    # For now we expose both via a note; choose one as your standard.
    total_volume_m3 = total_m3

    effective_volume_m3 = apply_deductions(total_m3, inputs)
    deductions = inputs.hed_volume_to_subtract_m3 + inputs.filter_bay_volume_to_subtract_m3

    if deductions > 0:
        notes.append(f"Deductions applied: HED + Filter = {deductions:.2f} m³.")

    # Compute min storage height metric:
    # This is often "minimum depth anywhere in footprint" at cap stage.
    # We'll compute the minimum local depth across cells at the cap stage.
    # (This matches the concept of shallow end depth.)
    ref_r, ref_c = sel.selected_cells[0]
    ref_xy = cell_center_xy(ref_r, ref_c, spec)
    min_depth = 10**9
    for r, c in sel.selected_cells:
        d = compute_depth_at_cell(cap_depth, r, c, inputs, spec, ref_xy)
        min_depth = min(min_depth, d)
    if min_depth == 10**9:
        min_depth = 0.0

    # "Effective storage height" in your Excel appears to be a reported value like 3.95m:
    # a representative height (often average depth, or cap depth minus grade effect).
    effective_height_report = avg_depth_m

    # Auto-size: find modules required to meet target effective volume by adding cells.
    # Since CPQ grid selection is manual, "modules_to_meet_target" is mostly a guidance output.
    modules_to_meet_target: Optional[int] = None
    if auto_size:
        target_m3 = inputs.target_effective_volume_kl  # kL==m³
        if effective_volume_m3 >= target_m3:
            modules_to_meet_target = modules_selected
        else:
            # We can estimate required module count using a scaling approach on average depth:
            # required_cells ≈ target / (avg_depth * cell_area) + deductions adjustment.
            cell_area = spec.module_length_m * spec.module_width_m
            if avg_depth_m > 0:
                req_cells = ceil((target_m3 + deductions) / (avg_depth_m * cell_area))
                modules_to_meet_target = max(1, req_cells)
                notes.append("Modules-to-target is an estimate unless a packing/shape rule is applied.")
            else:
                modules_to_meet_target = None
                notes.append("Could not estimate modules-to-target (avg depth computed as 0).")

    return MegaVaultResult(
        modules_selected=modules_selected,
        modules_to_meet_target=modules_to_meet_target,
        tank_length_m=round(length_m, 2),
        tank_width_m=round(width_m, 2),
        min_storage_height_m=round(min_depth, 2),
        effective_storage_height_m=round(effective_height_report, 2),
        proposed_total_volume_kl=round(total_volume_m3, 2),
        proposed_effective_volume_kl=round(effective_volume_m3, 2),
        deductions_m3=round(deductions, 2),
        notes=notes,
    )


# -----------------------------
# Stage storage table generator
# -----------------------------
def generate_stage_storage_table(
    sel: MegaVaultSelection,
    inputs: MegaVaultInputs,
    spec: MegaVaultModuleSpec
) -> List[StageRow]:
    """
    Generates stage-storage from invert level up to max stage.
    We compute incremental volume for each step and accumulate.

    Deductions: Excel conventions vary.
    Most often, deductions apply to final "effective" storage; stage table typically shows gross storage.
    Here we compute:
      - cumulative_volume_m3 (gross)
      - cumulative_effective_m3 (gross minus deductions, floored at 0)
    """
    validate_inputs(inputs)
    validate_selection(sel)

    cap_depth = min(inputs.internal_height_m, inputs.max_storage_height_m)
    stage_max = inputs.stage_max_height_m if inputs.stage_max_height_m is not None else cap_depth
    step = inputs.stage_step_m

    if step <= 0:
        raise ValueError("Stage step must be > 0 m")
    if stage_max <= 0:
        raise ValueError("Stage max height must be > 0 m")

    rows: List[StageRow] = []
    cumulative = 0.0
    prev_total = 0.0

    depth = 0.0
    while depth <= stage_max + 1e-9:
        total_m3, wetted_area_m2, _avg_depth = compute_storage_for_depth(sel, inputs, spec, water_depth_m=depth)
        incremental = max(0.0, total_m3 - prev_total)
        cumulative += incremental
        prev_total = total_m3

        effective_cum = apply_deductions(cumulative, inputs)
        stage_level = inputs.tank_invert_level_m + depth

        rows.append(StageRow(
            stage_level_m=round(stage_level, 3),
            depth_m=round(depth, 3),
            wetted_area_m2=round(wetted_area_m2, 3),
            incremental_volume_m3=round(incremental, 3),
            cumulative_volume_m3=round(cumulative, 3),
            cumulative_effective_m3=round(effective_cum, 3),
        ))

        depth += step

    return rows
