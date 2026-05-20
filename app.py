from __future__ import annotations

import streamlit as st
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List


# =========================================================
# Data Models
# =========================================================

@dataclass(frozen=True)
class RegionProfile:
    key: str
    name: str
    freight_multiplier: float
    market_pressure: float
    competitiveness: str
    notes: str


@dataclass(frozen=True)
class Competitor:
    name: str
    pricing_position: str
    price_factor: float
    service_score: int
    delivery_score: int
    technical_score: int


# =========================================================
# Assumptions
# =========================================================

ATLAN_BLUE = "#0B5CFF"
ATLAN_DARK = "#071B3A"
ATLAN_LIGHT = "#EEF5FF"

REGIONS: Dict[str, RegionProfile] = {
    "QLD": RegionProfile("QLD", "Queensland", 1.05, 0.95, "High", "Competitive pipe market with strong pricing pressure."),
    "NSW": RegionProfile("NSW", "New South Wales", 1.10, 0.97, "High", "High-volume market with active peer competition."),
    "VIC": RegionProfile("VIC", "Victoria", 1.08, 1.00, "Medium", "Balanced market with room for value-led pricing."),
    "WA": RegionProfile("WA", "Western Australia", 1.18, 1.05, "Medium", "Higher freight exposure and regional supply cost."),
    "SA": RegionProfile("SA", "South Australia", 1.12, 1.02, "Medium", "Moderate pricing pressure with freight sensitivity."),
}

COMPETITORS: List[Competitor] = [
    Competitor("Competitor A", "Aggressive / low-cost", 0.88, 6, 7, 5),
    Competitor("Competitor B", "Market average", 1.00, 7, 7, 7),
    Competitor("Competitor C", "Premium supplier", 1.16, 8, 8, 9),
    Competitor("Competitor D", "Regional player", 0.96, 7, 9, 6),
    Competitor("Competitor E", "Import / price-led", 0.82, 5, 5, 4),
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


# =========================================================
# Logic
# =========================================================

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


def job_size_category(total_quantity_m: float) -> str:
    if total_quantity_m >= 1000:
        return "Major project"
    if total_quantity_m >= 500:
        return "Large project"
    if total_quantity_m >= 250:
        return "Medium project"
    if total_quantity_m >= 100:
        return "Small project"
    return "Spot order"


def score_band(score: float) -> str:
    if score >= 8:
        return "Strong"
    if score >= 6:
        return "Moderate"
    return "Weak"


def safe_pct(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def win_probability(atlan_package_price: float, market_avg_package: float, atlan_score: float, competitor_avg_score: float) -> str:
    if market_avg_package <= 0:
        return "N/A"

    price_gap = (atlan_package_price - market_avg_package) / market_avg_package
    score_advantage = (atlan_score - competitor_avg_score) / 10
    adjusted_gap = price_gap - score_advantage

    if adjusted_gap <= -0.05:
        return "High"
    if adjusted_gap <= 0.04:
        return "Medium"
    if adjusted_gap <= 0.12:
        return "Low"
    return "Very Low"


def strategy_recommendation(
    atlan_package_price: float,
    market_avg_package: float,
    contribution_margin_pct: float,
) -> str:
    gap = safe_pct(atlan_package_price - market_avg_package, market_avg_package)

    if contribution_margin_pct < 0.25:
        return "Contribution margin is thin. Avoid further discounting unless this is a strategic project."
    if gap > 0.12:
        return "Atlan is materially above market. Sharpen price or clearly justify the premium."
    if gap > 0.04:
        return "Atlan is slightly above market. Lead with service, availability, and engineering support."
    if gap >= -0.03:
        return "Atlan is market-aligned. Maintain pricing discipline and focus on conversion."
    return "Atlan is pricing aggressively. Strong win potential, but check margin protection."


def default_pipe_lines() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Pipe size mm": 375,
                "Quantity / length m": 120.0,
                "RRP / m": PIPE_BASE_PRICE_PER_M[375],
                "Cost / m": round(PIPE_BASE_PRICE_PER_M[375] * 0.65, 2),
            },
            {
                "Pipe size mm": 450,
                "Quantity / length m": 60.0,
                "RRP / m": PIPE_BASE_PRICE_PER_M[450],
                "Cost / m": round(PIPE_BASE_PRICE_PER_M[450] * 0.65, 2),
            },
        ]
    )


def clean_pipe_lines(pipe_lines: pd.DataFrame) -> pd.DataFrame:
    df = pipe_lines.copy()

    required_cols = ["Pipe size mm", "Quantity / length m", "RRP / m", "Cost / m"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0.0

    df = df[required_cols]
    df["Pipe size mm"] = pd.to_numeric(df["Pipe size mm"], errors="coerce").fillna(0).astype(int)
    df["Quantity / length m"] = pd.to_numeric(df["Quantity / length m"], errors="coerce").fillna(0.0)
    df["RRP / m"] = pd.to_numeric(df["RRP / m"], errors="coerce").fillna(0.0)
    df["Cost / m"] = pd.to_numeric(df["Cost / m"], errors="coerce").fillna(0.0)

    df = df[
        (df["Pipe size mm"] > 0)
        & (df["Quantity / length m"] > 0)
        & (df["RRP / m"] > 0)
        & (df["Cost / m"] >= 0)
    ].copy()

    return df


def build_atlan_package(
    pipe_lines: pd.DataFrame,
    discount_pct: float,
    freight_cost: float,
) -> tuple[pd.DataFrame, dict]:
    df = clean_pipe_lines(pipe_lines)

    discount_factor = 1 - (discount_pct / 100)

    df["Gross RRP"] = df["RRP / m"] * df["Quantity / length m"]
    df["Discounted price / m"] = df["RRP / m"] * discount_factor
    df["Net revenue"] = df["Discounted price / m"] * df["Quantity / length m"]
    df["Total cost"] = df["Cost / m"] * df["Quantity / length m"]
    df["Contribution margin $"] = df["Net revenue"] - df["Total cost"]
    df["Contribution margin %"] = df.apply(
        lambda x: safe_pct(x["Contribution margin $"], x["Net revenue"]),
        axis=1,
    )

    gross_rrp = df["Gross RRP"].sum()
    net_revenue = df["Net revenue"].sum()
    total_cost = df["Total cost"].sum()
    cm_dollars = net_revenue - total_cost
    cm_pct = safe_pct(cm_dollars, net_revenue)

    undiscounted_cm_dollars = gross_rrp - total_cost
    undiscounted_cm_pct = safe_pct(undiscounted_cm_dollars, gross_rrp)

    cm_loss_dollars = undiscounted_cm_dollars - cm_dollars
    cm_loss_pct = safe_pct(cm_loss_dollars, undiscounted_cm_dollars)

    total_package_price = net_revenue + freight_cost

    summary = {
        "gross_rrp": gross_rrp,
        "net_revenue": net_revenue,
        "total_cost": total_cost,
        "freight_cost": freight_cost,
        "total_package_price": total_package_price,
        "cm_dollars": cm_dollars,
        "cm_pct": cm_pct,
        "undiscounted_cm_dollars": undiscounted_cm_dollars,
        "undiscounted_cm_pct": undiscounted_cm_pct,
        "cm_loss_dollars": cm_loss_dollars,
        "cm_loss_pct": cm_loss_pct,
        "total_quantity_m": df["Quantity / length m"].sum(),
    }

    return df, summary


def build_competitor_package_sheet(
    pipe_lines: pd.DataFrame,
    region_key: str,
    freight_cost: float,
) -> pd.DataFrame:
    region = REGIONS[region_key]
    lines = clean_pipe_lines(pipe_lines)

    rows = []

    for c in COMPETITORS:
        product_total = 0.0

        for _, line in lines.iterrows():
            pipe_size = int(line["Pipe size mm"])
            quantity_m = float(line["Quantity / length m"])
            base_price = PIPE_BASE_PRICE_PER_M.get(pipe_size, float(line["RRP / m"]))

            price_per_m = (
                base_price
                * c.price_factor
                * region.market_pressure
                * quantity_discount(quantity_m)
            )

            product_total += price_per_m * quantity_m

        competitor_freight = freight_cost * region.freight_multiplier
        package_total = product_total + competitor_freight
        total_score = (c.service_score + c.delivery_score + c.technical_score) / 3

        rows.append({
            "Competitor": c.name,
            "Positioning": c.pricing_position,
            "Product total": round(product_total, 0),
            "Freight": round(competitor_freight, 0),
            "Total package": round(package_total, 0),
            "Service": c.service_score,
            "Delivery": c.delivery_score,
            "Technical": c.technical_score,
            "Capability score": round(total_score, 1),
            "Capability band": score_band(total_score),
        })

    return pd.DataFrame(rows)


def build_pipe_level_peer_comparison(
    pipe_lines: pd.DataFrame,
    region_key: str,
) -> pd.DataFrame:
    region = REGIONS[region_key]
    lines = clean_pipe_lines(pipe_lines)
    rows = []

    for _, line in lines.iterrows():
        pipe_size = int(line["Pipe size mm"])
        quantity_m = float(line["Quantity / length m"])
        base_price = PIPE_BASE_PRICE_PER_M.get(pipe_size, float(line["RRP / m"]))

        peer_prices = [
            base_price
            * c.price_factor
            * region.market_pressure
            * quantity_discount(quantity_m)
            for c in COMPETITORS
        ]

        rows.append({
            "Pipe size": f"{pipe_size}mm",
            "Quantity / length m": round(quantity_m, 0),
            "Peer low / m": round(min(peer_prices), 2),
            "Peer average / m": round(sum(peer_prices) / len(peer_prices), 2),
            "Peer high / m": round(max(peer_prices), 2),
        })

    return pd.DataFrame(rows)


# =========================================================
# Page Setup
# =========================================================

st.set_page_config(
    page_title="Atlan Competitor Pricing Tool",
    page_icon="💧",
    layout="wide",
)

st.markdown(
    f"""
    <style>
        .stApp {{
            background: linear-gradient(180deg, #F5F9FF 0%, #FFFFFF 45%);
        }}

        .block-container {{
            padding-top: 1.8rem;
            padding-bottom: 3rem;
            max-width: 1250px;
        }}

        .hero {{
            background: linear-gradient(135deg, {ATLAN_BLUE} 0%, #003A9B 100%);
            padding: 32px 36px;
            border-radius: 24px;
            color: white;
            box-shadow: 0 18px 40px rgba(11, 92, 255, 0.22);
            margin-bottom: 24px;
        }}

        .hero h1 {{
            font-size: 38px;
            margin-bottom: 8px;
            font-weight: 800;
        }}

        .hero p {{
            font-size: 17px;
            opacity: 0.92;
            max-width: 900px;
        }}

        .section-card {{
            background: white;
            border: 1px solid rgba(11, 92, 255, 0.12);
            border-radius: 20px;
            padding: 22px;
            box-shadow: 0 10px 28px rgba(7, 27, 58, 0.06);
            margin-bottom: 18px;
        }}

        .small-card {{
            background: {ATLAN_LIGHT};
            border: 1px solid rgba(11, 92, 255, 0.14);
            border-radius: 16px;
            padding: 16px;
        }}

        .danger-card {{
            background: #FFF3F0;
            border: 1px solid rgba(214, 69, 38, 0.18);
            border-radius: 16px;
            padding: 16px;
        }}

        .muted {{
            color: rgba(7, 27, 58, 0.65);
            font-size: 14px;
        }}

        div.stButton > button[kind="primary"] {{
            background: {ATLAN_BLUE};
            border: 1px solid {ATLAN_BLUE};
            border-radius: 14px;
            padding: 0.75rem 1rem;
            font-weight: 700;
            width: 100%;
        }}

        div.stButton > button[kind="primary"]:hover {{
            background: #0848C8;
            border: 1px solid #0848C8;
        }}

        [data-testid="stMetricValue"] {{
            color: {ATLAN_DARK};
            font-weight: 800;
        }}

        [data-testid="stMetricLabel"] {{
            color: rgba(7, 27, 58, 0.72);
        }}

        section[data-testid="stSidebar"] {{
            background: #FFFFFF;
            border-right: 1px solid rgba(11, 92, 255, 0.10);
        }}

        .stDataFrame {{
            border-radius: 16px;
            overflow: hidden;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Header
# =========================================================

st.markdown(
    """
    <div class="hero">
        <h1>Atlan Stormwater Competitor Pricing Tool</h1>
        <p>
            Build a multi-pipe package quote, add freight, compare the total landed price against peers,
            and test how RRP discounts impact contribution margin.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Sidebar Inputs
# =========================================================

with st.sidebar:
    st.markdown("## Market Inputs")

    region_key = st.selectbox(
        "Region",
        list(REGIONS.keys()),
        format_func=lambda x: REGIONS[x].name,
    )

    freight_cost = st.number_input(
        "Freight cost for total package",
        min_value=0.0,
        value=2500.0,
        step=250.0,
        help="Enter the freight cost to be added to the total Atlan package price.",
    )

    st.divider()

    st.markdown("## Discount Inputs")

    discount_pct = st.slider(
        "Discount off RRP",
        min_value=0.0,
        max_value=50.0,
        value=0.0,
        step=0.5,
        help="Discount applied to all RRP lines.",
    )

    st.divider()

    st.markdown("## Atlan Capability Scores")

    atlan_service_score = st.slider("Service", 1, 10, 8)
    atlan_delivery_score = st.slider("Delivery", 1, 10, 8)
    atlan_technical_score = st.slider("Technical", 1, 10, 8)

    st.divider()

    generate = st.button(
        "Generate Package Pricing",
        type="primary",
        use_container_width=True,
    )


# =========================================================
# Main App Inputs
# =========================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Pipe Package Inputs")

st.write(
    "Add each pipe dimension and quantity/length. Enter RRP per metre and estimated cost per metre for each line."
)

pipe_lines_input = st.data_editor(
    default_pipe_lines(),
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Pipe size mm": st.column_config.SelectboxColumn(
            "Pipe size mm",
            options=sorted(PIPE_BASE_PRICE_PER_M.keys()),
            required=True,
        ),
        "Quantity / length m": st.column_config.NumberColumn(
            "Quantity / length m",
            min_value=0.0,
            step=10.0,
            required=True,
        ),
        "RRP / m": st.column_config.NumberColumn(
            "RRP / m",
            min_value=0.0,
            step=5.0,
            format="$%.2f",
            required=True,
        ),
        "Cost / m": st.column_config.NumberColumn(
            "Cost / m",
            min_value=0.0,
            step=5.0,
            format="$%.2f",
            required=True,
        ),
    },
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Main App
# =========================================================

if generate:
    region = REGIONS[region_key]

    atlan_lines, atlan_summary = build_atlan_package(
        pipe_lines=pipe_lines_input,
        discount_pct=discount_pct,
        freight_cost=freight_cost,
    )

    if atlan_lines.empty:
        st.error("Please enter at least one valid pipe line with pipe size, quantity, RRP and cost.")
        st.stop()

    competitor_df = build_competitor_package_sheet(
        pipe_lines=atlan_lines,
        region_key=region_key,
        freight_cost=freight_cost,
    )

    pipe_peer_df = build_pipe_level_peer_comparison(
        pipe_lines=atlan_lines,
        region_key=region_key,
    )

    market_low_package = competitor_df["Total package"].min()
    market_avg_package = competitor_df["Total package"].mean()
    market_high_package = competitor_df["Total package"].max()
    market_median_package = competitor_df["Total package"].median()

    atlan_package_price = atlan_summary["total_package_price"]
    atlan_gap_dollars = atlan_package_price - market_avg_package
    atlan_gap_pct = safe_pct(atlan_gap_dollars, market_avg_package)

    competitor_avg_score = competitor_df["Capability score"].mean()
    atlan_score = (atlan_service_score + atlan_delivery_score + atlan_technical_score) / 3

    win_prob = win_probability(
        atlan_package_price,
        market_avg_package,
        atlan_score,
        competitor_avg_score,
    )

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Package Market Snapshot")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Peer low package", f"${market_low_package:,.0f}")
    k2.metric("Peer average package", f"${market_avg_package:,.0f}")
    k3.metric("Peer high package", f"${market_high_package:,.0f}")
    k4.metric("Job size", job_size_category(atlan_summary["total_quantity_m"]))

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Atlan gap vs peer average", f"{atlan_gap_pct:.1%}", f"${atlan_gap_dollars:,.0f}")
    k6.metric("Contribution margin", f"{atlan_summary['cm_pct']:.1%}", f"${atlan_summary['cm_dollars']:,.0f}")
    k7.metric("Win probability", win_prob)
    k8.metric("Region competitiveness", region.competitiveness)

    st.markdown(
        f"""
        <div class="small-card">
            <b>{region.name} market note:</b><br>
            <span class="muted">{region.notes}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Atlan Package Build-up")

    display_atlan_lines = atlan_lines.copy()
    display_atlan_lines["Contribution margin %"] = display_atlan_lines["Contribution margin %"].map(lambda x: f"{x:.1%}")

    st.dataframe(
        display_atlan_lines,
        use_container_width=True,
        hide_index=True,
    )

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Gross RRP", f"${atlan_summary['gross_rrp']:,.0f}")
    a2.metric("Discounted revenue", f"${atlan_summary['net_revenue']:,.0f}")
    a3.metric("Freight added", f"${atlan_summary['freight_cost']:,.0f}")
    a4.metric("Total package", f"${atlan_summary['total_package_price']:,.0f}")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Discount Impact on Contribution Margin")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Discount applied", f"{discount_pct:.1f}%")
    d2.metric("CM before discount", f"{atlan_summary['undiscounted_cm_pct']:.1%}", f"${atlan_summary['undiscounted_cm_dollars']:,.0f}")
    d3.metric("CM after discount", f"{atlan_summary['cm_pct']:.1%}", f"${atlan_summary['cm_dollars']:,.0f}")
    d4.metric("Contribution margin lost", f"{atlan_summary['cm_loss_pct']:.1%}", f"${atlan_summary['cm_loss_dollars']:,.0f}")

    if discount_pct > 0:
        st.markdown(
            f"""
            <div class="danger-card">
                <b>Discount warning:</b><br>
                A <b>{discount_pct:.1f}%</b> discount off RRP reduces contribution margin dollars by
                <b>{atlan_summary['cm_loss_pct']:.1%}</b>, or approximately
                <b>${atlan_summary['cm_loss_dollars']:,.0f}</b>.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info("No discount has been applied. Contribution margin is shown at full RRP.")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Peer Package Comparison")

    competitor_df["Gap vs Atlan"] = competitor_df["Total package"] - round(atlan_package_price, 0)
    competitor_df["Gap vs Atlan %"] = competitor_df["Gap vs Atlan"].apply(
        lambda x: safe_pct(x, atlan_package_price)
    ).map(lambda x: f"{x:.1%}")

    st.dataframe(
        competitor_df,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1.05, 0.95])

    with col_left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Pipe-level Peer Range")

        st.dataframe(
            pipe_peer_df,
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Recommended Bid Strategy")

        recommendation = strategy_recommendation(
            atlan_package_price,
            market_avg_package,
            atlan_summary["cm_pct"],
        )

        st.success(recommendation)

        st.markdown("#### Readout")
        st.write(
            f"Atlan's total package is priced at **{atlan_gap_pct:.1%}** versus the estimated peer average."
        )
        st.write(
            f"The estimated win probability is **{win_prob}**, with a contribution margin of **{atlan_summary['cm_pct']:.1%}**."
        )
        st.write(
            f"The package includes **{len(atlan_lines)} pipe line(s)** and **${freight_cost:,.0f}** of freight."
        )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Suggested Pricing Scenarios")

    total_cost = atlan_summary["total_cost"]
    freight = atlan_summary["freight_cost"]

    scenarios = pd.DataFrame([
        {
            "Scenario": "Aggressive",
            "Product revenue": round(max(market_low_package - freight, 0) * 0.99, 0),
            "Freight": round(freight, 0),
            "Total package": round(max(market_low_package - freight, 0) * 0.99 + freight, 0),
            "Contribution margin": f"{safe_pct((max(market_low_package - freight, 0) * 0.99) - total_cost, max(market_low_package - freight, 0) * 0.99):.1%}",
            "Best for": "Strategic win / defend share",
        },
        {
            "Scenario": "Market aligned",
            "Product revenue": round(max(market_avg_package - freight, 0), 0),
            "Freight": round(freight, 0),
            "Total package": round(max(market_avg_package - freight, 0) + freight, 0),
            "Contribution margin": f"{safe_pct(max(market_avg_package - freight, 0) - total_cost, max(market_avg_package - freight, 0)):.1%}",
            "Best for": "Balanced win rate and margin",
        },
        {
            "Scenario": "Premium",
            "Product revenue": round(max(market_high_package - freight, 0) * 0.98, 0),
            "Freight": round(freight, 0),
            "Total package": round(max(market_high_package - freight, 0) * 0.98 + freight, 0),
            "Contribution margin": f"{safe_pct((max(market_high_package - freight, 0) * 0.98) - total_cost, max(market_high_package - freight, 0) * 0.98):.1%}",
            "Best for": "Less price-sensitive customer",
        },
    ])

    st.dataframe(
        scenarios,
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    download_tabs = {
        "atlan_package": atlan_lines,
        "peer_comparison": competitor_df,
        "pipe_peer_range": pipe_peer_df,
        "scenarios": scenarios,
    }

    csv = competitor_df.to_csv(index=False)

    st.download_button(
        label="Download Peer Package Comparison",
        data=csv,
        file_name="atlan_peer_package_pricing_comparison.csv",
        mime="text/csv",
        use_container_width=True,
    )

else:
    st.markdown(
        """
        <div class="section-card">
            <h3>Start by entering your package inputs</h3>
            <p class="muted">
                Add multiple pipe dimensions and quantities, enter freight, apply any RRP discount,
                then generate the package comparison against peers.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
