ffrom __future__ import annotations

import streamlit as st
from dataclasses import dataclass
from math import ceil
from typing import List, Dict

# ----------------------------
# Data models
# ----------------------------
@dataclass(frozen=True)
class ProductOption:
    code: str
    name: str
    family: str
    capacity_lps_per_unit: float
    unit_cost_index: float


@dataclass(frozen=True)
class RainScenario:
    key: str
    name: str
    treatment_rain_mmph: float
    runoff_coeff: float


@dataclass(frozen=True)
class Selection:
    product: ProductOption
    units: int
    total_capacity_lps: float
    total_cost_index: float
    notes: List[str]


# ----------------------------
# Config
# ----------------------------
PRODUCTS: List[ProductOption] = [
    ProductOption("ATLAN_FULL", "Atlan Filter (Full)", "ATLAN", 12.0, 2.80),
    ProductOption("ATLAN_HALF", "Atlan Filter (Half)", "ATLAN", 6.0, 1.70),

    ProductOption("FLOW_400", "Flow Filter (400 Series)", "FLOW", 7.5, 1.60),
    ProductOption("FLOW_1500", "Flow Filter (1500 Series)", "FLOW", 15.0, 3.10),

    ProductOption("FLOWGUARD", "FlowGuard", "FLOWGUARD", 10.0, 2.40),
]

SCENARIOS: Dict[str, RainScenario] = {
    "AUCKLAND": RainScenario("AUCKLAND", "Auckland", treatment_rain_mmph=10.0, runoff_coeff=0.90),
    "CHRISTCHURCH": RainScenario("CHRISTCHURCH", "Christchurch", treatment_rain_mmph=12.0, runoff_coeff=0.90),
    "REST_NZ": RainScenario("REST_NZ", "Rest of NZ", treatment_rain_mmph=15.0, runoff_coeff=0.90),
}

REGION_LABEL_TO_KEY = {
    "Auckland": "AUCKLAND",
    "Christchurch": "CHRISTCHURCH",
    "Rest of NZ": "REST_NZ",
}


# ----------------------------
# Helpers
# ----------------------------
def normalize_region(region_label: str) -> str:
    if region_label not in REGION_LABEL_TO_KEY:
        raise ValueError(f"Unknown region: {region_label}")
    return REGION_LABEL_TO_KEY[region_label]


def eligible_products(region_key: str) -> List[ProductOption]:
    # Auckland => only ATLAN + FLOWGUARD families
    if region_key == "AUCKLAND":
        return [p for p in PRODUCTS if p.family in ("ATLAN", "FLOWGUARD")]
    return list(PRODUCTS)


def treatment_flow_lps(area_m2: float, treatment_rain_mmph: float, runoff_coeff: float) -> float:
    if area_m2 <= 0:
        raise ValueError("Impervious area must be > 0 m²")
    if treatment_rain_mmph <= 0:
        raise ValueError("Treatment rainfall must be > 0 mm/hr")
    if not (0.0 <= runoff_coeff <= 1.0):
        raise ValueError("Runoff coefficient must be between 0 and 1")
    # (area m² * mm/hr * runoff_coeff) / 3600 = L/s (since 1 mm over 1 m² = 1 L)
    return (area_m2 * treatment_rain_mmph * runoff_coeff) / 3600.0


def choose_cheapest(required_lps: float, region_key: str) -> Selection:
    candidates: List[Selection] = []

    for p in eligible_products(region_key):
        units = max(1, ceil(required_lps / p.capacity_lps_per_unit))
        total_cap = units * p.capacity_lps_per_unit
        total_cost = units * p.unit_cost_index

        notes: List[str] = []
        if p.code == "FLOW_1500" and required_lps <= 7.5:
            notes.append("Guardrail: 1500 Series usually unnecessary below 7.5 L/s (prefer 400 Series).")
        if p.code == "ATLAN_HALF":
            notes.append("Guardrail: Half-size should be used only where form-factor constraints apply.")

        candidates.append(Selection(p, units, total_cap, total_cost, notes))

    candidates.sort(key=lambda x: (x.total_cost_index, x.units, -x.product.capacity_lps_per_unit))
    return candidates[0]


def force_product(required_lps: float, region_key: str, product_code: str) -> Selection:
    allowed = {p.code: p for p in eligible_products(region_key)}
    code = product_code.strip().upper()

    if code not in allowed:
        allowed_list = ", ".join(sorted(allowed.keys()))
        raise ValueError(f"Product '{code}' not eligible in {SCENARIOS[region_key].name}. Allowed: {allowed_list}")

    p = allowed[code]
    units = max(1, ceil(required_lps / p.capacity_lps_per_unit))
    return Selection(
        product=p,
        units=units,
        total_capacity_lps=units * p.capacity_lps_per_unit,
        total_cost_index=units * p.unit_cost_index,
        notes=[]
    )


# ----------------------------
# UI (Professional + branded)
# ----------------------------
st.set_page_config(page_title="Atlan Stormwater Sizing", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; }
      div.stButton > button[kind="primary"] {
        background: #0B5CFF;
        border: 1px solid #0B5CFF;
        border-radius: 10px;
        padding: 0.6rem 1rem;
        font-weight: 600;
      }
      div.stButton > button[kind="primary"]:hover {
        background: #0749d1;
        border: 1px solid #0749d1;
      }
      .atlan-card {
        border: 1px solid rgba(11, 92, 255, 0.12);
        background: #FFFFFF;
        border-radius: 14px;
        padding: 16px 18px;
      }
      .atlan-muted { color: rgba(11, 18, 32, 0.65); }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Atlan Stormwater Treatment Sizing")
st.caption("Enter site inputs to calculate treatment flow and select an eligible system.")

# Sidebar inputs
with st.sidebar:
    st.header("Inputs")

    project = st.text_input("Project name", value="Demo Site")
    region_label = st.selectbox("Region", ["Auckland", "Christchurch", "Rest of NZ"], index=0)

    region_key = normalize_region(region_label)
    scenario = SCENARIOS[region_key]

    st.markdown("### Hydraulic Inputs")
    area_m2 = st.number_input("Impervious area (m²)", min_value=1.0, value=1500.0, step=50.0)

    treatment_rain_mmph = st.number_input(
        "Treatment rainfall (mm/hr)",
        min_value=0.1,
        value=float(scenario.treatment_rain_mmph),
        step=0.5,
        help="Default is loaded from region. You may override.",
    )

    runoff_coeff = st.number_input(
        "Runoff coefficient",
        min_value=0.0,
        max_value=1.0,
        value=float(scenario.runoff_coeff),
        step=0.05,
        help="Default is loaded from region. Typical range 0.7–1.0",
    )

    st.divider()
    st.header("Selection")

    mode = st.radio("Mode", ["Cheapest eligible", "Force product"], horizontal=False)

    eligible_codes = [p.code for p in eligible_products(region_key)]
    force_code = ""
    if mode == "Force product":
        force_code = st.selectbox("Force product code", eligible_codes)

    submitted = st.button("Calculate", type="primary", use_container_width=True)

    with st.expander("Eligibility rules", expanded=False):
        st.write("- **Auckland:** only **ATLAN** + **FLOWGUARD** families")
        st.write("- **Other regions:** all products allowed (as configured)")


# Main tabs
tab1, tab2, tab3 = st.tabs(["Summary", "Comparison", "Assumptions"])

with tab1:
    if not submitted:
        st.info("Enter inputs in the sidebar and click **Calculate**.")
    else:
        try:
            required_lps = treatment_flow_lps(area_m2, treatment_rain_mmph, runoff_coeff)

            if mode == "Force product":
                selection = force_product(required_lps, region_key, force_code)
            else:
                selection = choose_cheapest(required_lps, region_key)

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Treatment flow (L/s)", f"{required_lps:.2f}")
            k2.metric("Recommended product", selection.product.code)
            k3.metric("Units", f"{selection.units}")
            k4.metric("Total capacity (L/s)", f"{selection.total_capacity_lps:.2f}")

            st.write("")

            st.markdown('<div class="atlan-card">', unsafe_allow_html=True)
            st.subheader("Recommendation")
            st.write(f"**{selection.product.name}**  ·  `{selection.product.code}`")
            st.write(f"<span class='atlan-muted'>Project:</span> **{project}**", unsafe_allow_html=True)
            st.write(
                f"<span class='atlan-muted'>Inputs used:</span> "
                f"**{treatment_rain_mmph:g} mm/hr × runoff {runoff_coeff:g}**",
                unsafe_allow_html=True,
            )

            st.write("")
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Capacity per unit**  \n{selection.product.capacity_lps_per_unit:g} L/s")
            c2.write(f"**Units (rounded up)**  \n{selection.units}")
            c3.write(f"**Indicative cost index**  \n{selection.total_cost_index:.2f}")
            st.markdown("</div>", unsafe_allow_html=True)

            if selection.notes:
                st.warning("**Notes**\n\n" + "\n".join([f"- {n}" for n in selection.notes]))

            st.markdown("### Eligible products")
            elig = eligible_products(region_key)
            st.dataframe(
                [{
                    "Code": p.code,
                    "Name": p.name,
                    "Family": p.family,
                    "Capacity (L/s)": p.capacity_lps_per_unit,
                    "Cost index": p.unit_cost_index,
                } for p in elig],
                use_container_width=True,
                hide_index=True
            )

        except Exception as e:
            st.error(f"Couldn’t calculate: {e}")

with tab2:
    if not submitted:
        st.info("Run a calculation first to see the comparison table.")
    else:
        required_lps = treatment_flow_lps(area_m2, treatment_rain_mmph, runoff_coeff)
        elig = eligible_products(region_key)

        st.subheader("Comparison (eligible options)")
        comparisons = []
        for p in elig:
            units = max(1, ceil(required_lps / p.capacity_lps_per_unit))
            comparisons.append({
                "Code": p.code,
                "Family": p.family,
                "Units": units,
                "Total capacity (L/s)": round(units * p.capacity_lps_per_unit, 2),
                "Total cost index": round(units * p.unit_cost_index, 2),
            })
        comparisons.sort(key=lambda r: (r["Total cost index"], r["Units"], -r["Total capacity (L/s)"]))
        st.dataframe(comparisons, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Assumptions")
    st.write("**Treatment flow (L/s)** = (Impervious area × Treatment rainfall × Runoff coefficient) ÷ 3600")
    st.write("Any flow above the treatment flow may bypass (site-specific).")

    st.write("")
    st.subheader("Region defaults (used as starting values)")
    st.dataframe(
        [{
            "Region": s.name,
            "Treatment rainfall (mm/hr)": s.treatment_rain_mmph,
            "Runoff coefficient": s.runoff_coeff,
        } for s in SCENARIOS.values()],
        use_container_width=True,
        hide_index=True
    )

st.caption("Update PRODUCTS and SCENARIOS to match the latest Atlan spreadsheet assumptions.")
