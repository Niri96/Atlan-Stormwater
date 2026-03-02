import streamlit as st

from megavault_engine import (
    MegaVaultModuleSpec,
    MegaVaultInputs,
    MegaVaultSelection,
    GradeDirection,
    calculate_megavault
)

st.set_page_config(page_title="MegaVault Tank Sizing", layout="wide")

st.title("MegaVault Tank Sizing Tool")
st.caption("Engineering Engine Demo – CPQ Stage 1")

# ----------------
# Inputs
# ----------------
with st.sidebar:
    st.header("Inputs")

    target = st.number_input("Target Effective Volume (kL)", value=1000.0)
    internal_h = st.number_input("Internal Height (m)", value=3.0)
    max_h = st.number_input("Max Storage Height (m)", value=3.0)
    grade = st.number_input("Tank Grade (0.01 = 1%)", value=0.01)
    direction = st.selectbox("Grade Direction", ["UP", "DOWN", "LEFT", "RIGHT"])

    hed = st.number_input("HED Volume (m³)", value=0.0)
    filter_v = st.number_input("Filter Bay Volume (m³)", value=0.0)

    modules = st.number_input("Selected Modules", min_value=1, value=30)

    run = st.button("Calculate", type="primary")

# ----------------
# Run calc
# ----------------
if run:

    # Fake simple grid selection (for now)
    cells = tuple((r, 0) for r in range(modules))

    spec = MegaVaultModuleSpec(
        module_length_m=2.4,
        module_width_m=1.2,
        module_void_volume_m3=21.02,
        internal_height_m=internal_h,
    )

    inputs = MegaVaultInputs(
        target_effective_volume_kl=target,
        internal_height_m=internal_h,
        max_storage_height_m=max_h,
        tank_grade=grade,
        grade_direction=GradeDirection(direction),
        hed_volume_to_subtract_m3=hed,
        filter_bay_volume_to_subtract_m3=filter_v,
    )

    sel = MegaVaultSelection(
        selected_cells=cells,
        grid_rows=40,
        grid_cols=40,
    )

    result = calculate_megavault(sel, inputs, spec)

    st.subheader("Results")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Modules", result.modules_selected)
    c2.metric("Effective Volume (kL)", result.proposed_effective_volume_kl)
    c3.metric("Length (m)", result.tank_length_m)
    c4.metric("Width (m)", result.tank_width_m)

    st.write(result)
