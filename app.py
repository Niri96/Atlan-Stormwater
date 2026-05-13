from __future__ import annotations

import streamlit as st
from dataclasses import dataclass
from math import ceil
from typing import List, Dict


# -----------------------------
# Dataclasses
# -----------------------------

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


@dataclass(frozen=True)
class RegionPricingProfile:
    key: str
    name: str
    freight_multiplier: float
    competitiveness: str
    price_pressure: float


@dataclass(frozen=True)
class Competitor:
    name: str
    positioning: str
    price_factor: float


# -----------------------------
# Core sizing assumptions
# -----------------------------

PRODUCTS: List[ProductOption] = [
    ProductOption("ATLAN_FULL", "Atlan Filter (Full)", "ATLAN", 12.0, 2.80),
    ProductOption("ATLAN_HALF", "Atlan Filter (Half)", "ATLAN", 6.0, 1.70),
    ProductOption("FLOW_400", "Flow Filter (400 Series)", "FLOW", 7.5, 1.60),
    ProductOption("FLOW_1500", "Flow Filter (1500 Series)", "FLOW", 15.0, 3.10),
    ProductOption("FLOWGUARD", "FlowGuard", "FLOWGUARD", 10.0, 2.40),
]

SCENARIOS: Dict[str, RainScenario] = {
    "AUCKLAND": RainScenario("AUCKLAND", "Auckland", 10.0, 0.90),
    "CHRISTCHURCH": RainScenario("CHRISTCHURCH", "Christchurch", 12.0, 0.90),
    "REST_NZ": RainScenario("REST_NZ", "Rest of NZ", 15.0, 0.90),
}

REGION_LABEL_TO_KEY = {
    "Auckland": "AUCKLAND",
    "Christchurch": "CHRISTCHURCH",
    "Rest of NZ": "REST_NZ",
}


# -----------------------------
# Peer pricing assumptions
# -----------------------------

PRICING_REGIONS: Dict[str, RegionPricingProfile] = {
    "QLD": RegionPricingProfile("QLD", "Queensland", 1.05, "High", 0.95),
    "NSW": RegionPricingProfile("NSW", "New South Wales", 1.10, "High", 0.97),
    "VIC": RegionPricingProfile("VIC", "Victoria", 1.08, "Medium", 1.00),
    "WA": RegionPricingProfile("WA", "Western Australia", 1.18, "Medium", 1.05),
    "SA": RegionPricingProfile("SA", "South Australia", 1.12, "Medium", 1.02),
}

COMPETITORS: List[Competitor] = [
    Competitor("Competitor A", "Low-cost / aggressive", 0.90),
    Competitor("Competitor B", "Market average", 1.00),
    Competitor("Competitor C", "Premium / engineered solution", 1.15),
]

PIPE_BASE_PRICE_PER_M: Dict[int, float] = {
    225: 85,
    300: 120,
    375: 165,
    450: 220,
    525: 285,
    600: 360,
    750: 520,
    900: 720,
    1050: 950,
    1200: 1250,
}


# -----------------------------
# Sizing functions
# -----------------------------

def normalize_region(region_label: str) -> str:
    if region_label not in REGION_LABEL_TO_KEY:
        raise ValueError(f"Unknown region: {region_label}")
    return REGION_LABEL_TO_KEY[region_label]


def eligible_products(region_key: str) -> List[ProductOption]:
    if region_key == "AUCKLAND":
        return [p for p in PRODUCTS if p.family in ("ATLAN", "FLOWGUARD")]
    return list(PRODUCTS)


def treatment_flow_lps(
    area_m2: float,
    treatment_rain_mmph: float,
    runoff_coeff: float,
) -> float:
    if area_m2 <= 0:
        raise ValueError("Impervious area must be > 0 m²")
    if treatment_rain_mmph <= 0:
        raise ValueError("Treatment rainfall must be > 0 mm/hr")
    if not (0.0 <= runoff_coeff <= 1.0):
        raise ValueError("Runoff coefficient must be between 0 and 1")

    return (area_m2 * treatment_rain_mmph * runoff_coeff) / 3600.0


def choose_cheapest(required_lps: float, region_key: str) -> Selection:
    candidates: List[Selection] = []

    for p in eligible_products(region_key):
        units = max(1, ceil(required_lps / p.capacity_lps_per_unit))
        total_cap = units * p.capacity_lps_per_unit
        total_cost = units * p.unit_cost_index

        notes: List[str] = []

        if p.code == "FLOW_1500" and required_lps <= 7.5:
            notes.append("Guardrail: 1500 Series usually unnecessary below 7.5 L/s.")
        if p.code == "ATLAN_HALF":
            notes.append("Guardrail: Half-size should be used only where form-factor constraints apply.")

        candidates.append(
            Selection(
                product=p,
                units=units,
                total_capacity_lps=total_cap,
                total_cost_index=total_cost,
                notes=notes,
            )
        )

    candidates.sort(key=lambda x: (x.total_cost_index, x.units, -x.product.capacity_lps_per_unit))
    return candidates[0]


def force_product(required_lps: float, region_key: str, product_code: str) -> Selection:
    allowed = {p.code: p for p in eligible_products(region_key)}
    code = product_code.strip().upper()

    if code not in allowed:
        allowed_list = ", ".join(sorted(allowed.keys()))
        raise ValueError(
            f"Product '{code}' not eligible in {SCENARIOS[region_key].name}. "
            f"Allowed: {allowed_list}"
        )

    p = allowed[code]
    units = max(1, ceil(required_lps / p.capacity_lps_per_unit))

    return Selection(
        product=p,
        units=units,
        total_capacity_lps=units * p.capacity_lps_per_unit,
        total_cost_index=units * p.unit_cost_index,
        notes=[],
    )


# -----------------------------
# Peer pricing functions
# -----------------------------

def quantity_discount(quantity_m: float) -> float:
    if quantity_m >= 1000:
        return 0.88
    if quantity_m >= 500:
        return 0.92
    if quantity_m >= 250:
        return 0.95
    if quantity_m >= 100:
        return 0.98
    return 1.00


def win_probability(atlan_price: float, market_price: float) -> str:
    gap = (atlan_price - market_price) / market_price

    if gap <= -0.05:
        return "High"
    if gap <= 0.05:
        return "Medium"
    if gap <= 0.12:
        return "Low"
    return "Very Low"


def pricing_recommendation(atlan_price: float, market_price: float) -> str:
    gap = (atlan_price - market_price) / market_price

    if gap > 0.10:
        return "Sharpen price or justify premium through technical/service value."
    if gap > 0.03:
        return "Slightly above market. Position around availability, freight, and engineering support."
    if gap >= -0.03:
        return "Market-aligned. Maintain pricing discipline."

    return "Aggressive pricing. Good chance to win, but check margin protection."


def build_peer_pricing_table(
    pipe_size_mm: int,
    quantity_m: float,
    region_key: str,
) -> List[dict]:
    region = PRICING_REGIONS[region_key]
    base_price = PIPE_BASE_PRICE_PER_M[pipe_size_mm]
    discount = quantity_discount(quantity_m)

    rows = []

    for competitor in COMPETITORS:
        price_per_m = (
            base_price
            * competitor.price_factor
            * region.freight_multiplier
            * region.price_pressure
            * discount
        )

        rows.append({
            "Competitor": competitor.name,
            "Positioning": competitor.positioning,
            "Estimated price / m": round(price_per_m, 2),
            "Estimated total": round(price_per_m * quantity_m, 0),
        })

    return rows


# -----------------------------
# Streamlit setup
# -----------------------------

st.set_page_config(
    page_title="Atlan Stormwater Sizing",
    layout="wide",
)

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

      .atlan-muted {
        color: rgba(11, 18, 32, 0.65);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Atlan Stormwater Treatment Sizing")
st.caption("Treatment sizing, product comparison, and indicative peer pricing analysis.")


# -----------------------------
# Sidebar inputs
# -----------------------------

with st.sidebar:
    st.header("Sizing Inputs")

    project = st.text_input("Project name", value="Demo Site")

    region_label = st.selectbox(
        "Sizing region",
        ["Auckland", "Christchurch", "Rest of NZ"],
        index=0,
    )

    region_key = normalize_region(region_label)
    scenario = SCENARIOS[region_key]

    st.markdown("### Hydraulic Inputs")

    area_m2 = st.number_input(
        "Impervious area (m²)",
        min_value=1.0,
        value=1500.0,
        step=50.0,
    )

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
    )

    st.divider()
    st.header("Selection")

    mode = st.radio(
        "Mode",
        ["Cheapest eligible", "Force product"],
        horizontal=False,
    )

    eligible_codes = [p.code for p in eligible_products(region_key)]
    force_code = ""

    if mode == "Force product":
        force_code = st.selectbox("Force product code", eligible_codes)

    submitted = st.button(
        "Calculate",
        type="primary",
        use_container_width=True,
    )

    with st.expander("Eligibility rules", expanded=False):
        st.write("- **Auckland:** only **ATLAN** + **FLOWGUARD** families")
        st.write("- **Other regions:** all products allowed as configured")


# -----------------------------
# Tabs
# -----------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "Summary",
    "Comparison",
    "Peer Pricing",
    "Assumptions",
])


# -----------------------------
# Tab 1: Summary
# -----------------------------

with tab1:
    if not submitted:
        st.info("Enter inputs in the sidebar and click **Calculate**.")
    else:
        try:
            required_lps = treatment_flow_lps(
                area_m2,
                treatment_rain_mmph,
                runoff_coeff,
            )

            if mode == "Force product":
                selection = force_product(required_lps, region_key, force_code)
            else:
                selection = choose_cheapest(required_lps, region_key)

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Treatment flow", f"{required_lps:.2f} L/s")
            k2.metric("Recommended product", selection.product.code)
            k3.metric("Units", f"{selection.units}")
            k4.metric("Total capacity", f"{selection.total_capacity_lps:.2f} L/s")

            st.write("")

            st.markdown('<div class="atlan-card">', unsafe_allow_html=True)
            st.subheader("Recommendation")
            st.write(f"**{selection.product.name}** · `{selection.product.code}`")
            st.write(f"<span class='atlan-muted'>Project:</span> **{project}**", unsafe_allow_html=True)
            st.write(
                f"<span class='atlan-muted'>Inputs used:</span> "
                f"**{treatment_rain_mmph:g} mm/hr × runoff {runoff_coeff:g}**",
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns(3)
            c1.write(f"**Capacity per unit**  \n{selection.product.capacity_lps_per_unit:g} L/s")
            c2.write(f"**Units rounded up**  \n{selection.units}")
            c3.write(f"**Indicative cost index**  \n{selection.total_cost_index:.2f}")
            st.markdown("</div>", unsafe_allow_html=True)

            if selection.notes:
                st.warning("**Notes**\n\n" + "\n".join([f"- {n}" for n in selection.notes]))

            st.markdown("### Eligible products")
            st.dataframe(
                [{
                    "Code": p.code,
                    "Name": p.name,
                    "Family": p.family,
                    "Capacity L/s": p.capacity_lps_per_unit,
                    "Cost index": p.unit_cost_index,
                } for p in eligible_products(region_key)],
                use_container_width=True,
                hide_index=True,
            )

        except Exception as e:
            st.error(f"Couldn’t calculate: {e}")


# -----------------------------
# Tab 2: Comparison
# -----------------------------

with tab2:
    if not submitted:
        st.info("Run a calculation first to see the comparison table.")
    else:
        required_lps = treatment_flow_lps(
            area_m2,
            treatment_rain_mmph,
            runoff_coeff,
        )

        comparisons = []

        for p in eligible_products(region_key):
            units = max(1, ceil(required_lps / p.capacity_lps_per_unit))
            comparisons.append({
                "Code": p.code,
                "Family": p.family,
                "Units": units,
                "Total capacity L/s": round(units * p.capacity_lps_per_unit, 2),
                "Total cost index": round(units * p.unit_cost_index, 2),
            })

        comparisons.sort(
            key=lambda r: (
                r["Total cost index"],
                r["Units"],
                -r["Total capacity L/s"],
            )
        )

        st.subheader("Comparison of eligible options")
        st.dataframe(
            comparisons,
            use_container_width=True,
            hide_index=True,
        )


# -----------------------------
# Tab 3: Peer Pricing
# -----------------------------

with tab3:
    st.subheader("Peer Pricing / Competitor Benchmarking")
    st.caption("Indicative only. This uses hypothetical competitor pricing logic, not live market data.")

    c1, c2, c3, c4 = st.columns(4)

    pipe_size_mm = c1.selectbox(
        "Pipe size",
        sorted(PIPE_BASE_PRICE_PER_M.keys()),
        index=2,
        format_func=lambda x: f"{x}mm",
    )

    quantity_m = c2.number_input(
        "Quantity / length (m)",
        min_value=1.0,
        value=120.0,
        step=10.0,
    )

    pricing_region = c3.selectbox(
        "Pricing region",
        list(PRICING_REGIONS.keys()),
        format_func=lambda x: PRICING_REGIONS[x].name,
    )

    atlan_price_per_m = c4.number_input(
        "Atlan price / m",
        min_value=1.0,
        value=float(PIPE_BASE_PRICE_PER_M[pipe_size_mm]),
        step=5.0,
    )

    rows = build_peer_pricing_table(
        pipe_size_mm=pipe_size_mm,
        quantity_m=quantity_m,
        region_key=pricing_region,
    )

    prices = [r["Estimated price / m"] for r in rows]

    market_low = min(prices)
    market_avg = sum(prices) / len(prices)
    market_high = max(prices)

    atlan_total = atlan_price_per_m * quantity_m
    gap = atlan_price_per_m - market_avg
    gap_pct = gap / market_avg

    st.write("")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Market low", f"${market_low:,.2f}/m")
    k2.metric("Market average", f"${market_avg:,.2f}/m")
    k3.metric("Market premium", f"${market_high:,.2f}/m")
    k4.metric("Gap vs market", f"{gap_pct:.1%}")

    st.markdown("### Competitor pricing estimate")
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Atlan positioning")

    p1, p2, p3 = st.columns(3)
    p1.metric("Atlan total price", f"${atlan_total:,.0f}")
    p2.metric("Estimated win probability", win_probability(atlan_price_per_m, market_avg))
    p3.metric("Market competitiveness", PRICING_REGIONS[pricing_region].competitiveness)

    st.info(pricing_recommendation(atlan_price_per_m, market_avg))

    st.markdown("### Pricing assumptions used")
    st.dataframe(
        [{
            "Region": r.name,
            "Freight multiplier": r.freight_multiplier,
            "Competitiveness": r.competitiveness,
            "Price pressure": r.price_pressure,
        } for r in PRICING_REGIONS.values()],
        use_container_width=True,
        hide_index=True,
    )


# -----------------------------
# Tab 4: Assumptions
# -----------------------------

with tab4:
    st.subheader("Sizing assumptions")

    st.write(
        "**Treatment flow L/s** = "
        "(Impervious area × Treatment rainfall × Runoff coefficient) ÷ 3600"
    )

    st.write("Any flow above the treatment flow may bypass, subject to site-specific design.")

    st.markdown("### Region defaults")
    st.dataframe(
        [{
            "Region": s.name,
            "Treatment rainfall mm/hr": s.treatment_rain_mmph,
            "Runoff coefficient": s.runoff_coeff,
        } for s in SCENARIOS.values()],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Product assumptions")
    st.dataframe(
        [{
            "Code": p.code,
            "Name": p.name,
            "Family": p.family,
            "Capacity L/s": p.capacity_lps_per_unit,
            "Cost index": p.unit_cost_index,
        } for p in PRODUCTS],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Pipe base price assumptions")
    st.dataframe(
        [{
            "Pipe size mm": size,
            "Base price / m": price,
        } for size, price in PIPE_BASE_PRICE_PER_M.items()],
        use_container_width=True,
        hide_index=True,
    )

st.caption("Update PRODUCTS, SCENARIOS, PRICING_REGIONS, COMPETITORS, and PIPE_BASE_PRICE_PER_M to match the latest internal assumptions.")
