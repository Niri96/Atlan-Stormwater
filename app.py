from __future__ import annotations

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
# Config (EDIT THESE to match Atlan / your spreadsheet)
# ----------------------------
PRODUCTS: List[ProductOption] = [
    # ATLAN family examples (placeholder — set your real values)
    ProductOption("ATLAN_FULL", "Atlan Filter (Full)", "ATLAN", 12.0, 2.80),
    ProductOption("ATLAN_HALF", "Atlan Filter (Half)", "ATLAN", 6.0, 1.70),

    # Your snippet (kept)
    ProductOption("FLOW_400", "Flow Filter (400 Series)", "FLOW", 7.5, 1.60),
    ProductOption("FLOW_1500", "Flow Filter (1500 Series)", "FLOW", 15.0, 3.10),

    ProductOption("FLOWGUARD", "FlowGuard", "FLOWGUARD", 10.0, 2.40),
]

SCENARIOS: Dict[str, RainScenario] = {
    # Replace these rainfall & coeffs with your actual internal spreadsheet assumptions
    "AUCKLAND": RainScenario("AUCKLAND", "Auckland", treatment_rain_mmph=10.0, runoff_coeff=0.90),
    "CHRISTCHURCH": RainScenario("CHRISTCHURCH", "Christchurch", treatment_rain_mmph=12.0, runoff_coeff=0.90),
    "REST_NZ": RainScenario("REST_NZ", "Rest of NZ", treatment_rain_mmph=15.0, runoff_coeff=0.90),
}

REGION_LABEL_TO_KEY = {
    "Auckland": "AUCKLAND",
    "Christchurch": "CHRISTCHURCH",
    "Rest of NZ": "REST_NZ",
}


def normalize_region(region_label: str) -> str:
    if region_label not in REGION_LABEL_TO_KEY:
        raise ValueError(f"Unknown region: {region_label}")
    return REGION_LABEL_TO_KEY[region_label]


# ----------------------------
# Core logic (your functions)
# ----------------------------
def eligible_products(region_key: str) -> List[ProductOption]:
    # Your rule: Auckland => only ATLAN + FLOWGUARD families
    if region_key == "AUCKLAND":
        return [p for p in PRODUCTS if p.family in ("ATLAN", "FLOWGUARD")]
    return list(PRODUCTS)


def treatment_flow_lps(area_m2: float, scenario: RainScenario) -> float:
    if area_m2 <= 0:
        raise ValueError("Impervious area must be > 0 m²")
    # (area m² * mm/hr * runoff_coeff) / 3600 = L/s (since 1 mm over 1 m² = 1 L)
    return (area_m2 * scenario.treatment_rain_mmph * scenario.runoff_coeff) / 3600.0


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
# UI
# ----------------------------
st.set_page_config(page_title="Atlan Stormwater Sizing Demo", layout="wide")

st.title("Atlan Stormwater Treatment Sizing – Demo")
st.caption("Enter site inputs → calculate treatment flow → select cheapest eligible system (or force a product).")

left, right = st.columns([1, 1.2], gap="large")

with left:
    st.subheader("Inputs")

    with st.form("inputs_form"):
        project = st.text_input("Project name", value="Demo Site")
        region_label = st.selectbox("Region", ["Auckland", "Christchurch", "Rest of NZ"], index=0)
        area_m2 = st.number_input("Impervious area (m²)", min_value=1.0, value=1500.0, step=50.0)

        mode = st.radio("Selection mode", ["Cheapest eligible", "Force product"], horizontal=True)

        force_code = ""
        if mode == "Force product":
            # show only eligible codes for the chosen region
            try:
                rk = normalize_region(region_label)
                eligible_codes = [p.code for p in eligible_products(rk)]
            except Exception:
                eligible_codes = [p.code for p in PRODUCTS]

            force_code = st.selectbox("Force product code", eligible_codes)

        submitted = st.form_submit_button("Calculate")

    st.divider()
    st.subheader("Eligibility rules")
    st.write("- **Auckland:** only **ATLAN** + **FLOWGUARD** families")
    st.write("- **Other regions:** all products allowed (as currently configured)")

with right:
    st.subheader("Results")

    if not submitted:
        st.info("Fill the inputs and click **Calculate**.")
    else:
        try:
            region_key = normalize_region(region_label)
            scenario = SCENARIOS[region_key]
            required_lps = treatment_flow_lps(area_m2, scenario)

            if mode == "Force product":
                selection = force_product(required_lps, region_key, force_code)
            else:
                selection = choose_cheapest(required_lps, region_key)

            # Top KPIs
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Treatment flow (L/s)", f"{required_lps:.2f}")
            k2.metric("Selected product", f"{selection.product.code}")
            k3.metric("Units", f"{selection.units}")
            k4.metric("Total capacity (L/s)", f"{selection.total_capacity_lps:.2f}")

            st.write("")
            st.write(f"**Project:** {project}")
            st.write(f"**Region scenario:** {scenario.name}  |  {scenario.treatment_rain_mmph:g} mm/hr × runoff {scenario.runoff_coeff:g}")

            # Detail card
            st.markdown("### Selected Treatment System")
            st.write(f"**{selection.product.name}** (`{selection.product.code}`)")
            st.write(f"- Capacity per unit: **{selection.product.capacity_lps_per_unit:g} L/s**")
            st.write(f"- Units (rounded up): **{selection.units}**")
            st.write(f"- Cost index (demo): **{selection.total_cost_index:.2f}**")

            # Notes / guardrails
            if selection.notes:
                st.warning("**Guardrails / notes**\n\n" + "\n".join([f"- {n}" for n in selection.notes]))

            # Eligible product table
            st.markdown("### Eligible products (this region)")
            elig = eligible_products(region_key)
            st.dataframe(
                [{
                    "Code": p.code,
                    "Name": p.name,
                    "Family": p.family,
                    "Capacity (L/s per unit)": p.capacity_lps_per_unit,
                    "Cost index (per unit)": p.unit_cost_index,
                } for p in elig],
                use_container_width=True,
                hide_index=True
            )

            # Show all candidates comparison (helpful for stakeholders)
            st.markdown("### Comparison (all eligible options)")
            comparisons = []
            for p in elig:
                units = max(1, ceil(required_lps / p.capacity_lps_per_unit))
                comparisons.append({
                    "Code": p.code,
                    "Family": p.family,
                    "Units": units,
                    "Total capacity (L/s)": units * p.capacity_lps_per_unit,
                    "Total cost index": units * p.unit_cost_index,
                })
            comparisons.sort(key=lambda r: (r["Total cost index"], r["Units"], -r["Total capacity (L/s)"]))
            st.dataframe(comparisons, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Couldn’t calculate: {e}")
            st.stop()

st.caption("Tip: swap the placeholder rainfall/coeff assumptions in SCENARIOS + product capacities/costs to match the Atlan spreadsheet.")
