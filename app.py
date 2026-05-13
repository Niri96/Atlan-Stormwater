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


def job_size_category(quantity_m: float) -> str:
    if quantity_m >= 1000:
        return "Major project"
    if quantity_m >= 500:
        return "Large project"
    if quantity_m >= 250:
        return "Medium project"
    if quantity_m >= 100:
        return "Small project"
    return "Spot order"


def score_band(score: float) -> str:
    if score >= 8:
        return "Strong"
    if score >= 6:
        return "Moderate"
    return "Weak"


def win_probability(atlan_price: float, market_avg: float, atlan_score: float, competitor_avg_score: float) -> str:
    price_gap = (atlan_price - market_avg) / market_avg
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
    atlan_price: float,
    market_avg: float,
    gross_margin: float,
) -> str:
    gap = (atlan_price - market_avg) / market_avg

    if gross_margin < 0.25:
        return "Margin is thin. Avoid over-discounting unless this is a strategic project."
    if gap > 0.12:
        return "Atlan is materially above market. Sharpen price or clearly justify the premium."
    if gap > 0.04:
        return "Atlan is slightly above market. Lead with service, availability, and engineering support."
    if gap >= -0.03:
        return "Atlan is market-aligned. Maintain pricing discipline and focus on conversion."
    return "Atlan is pricing aggressively. Strong win potential, but check margin protection."


def build_competitor_pricing_sheet(
    pipe_size_mm: int,
    quantity_m: float,
    region_key: str,
) -> pd.DataFrame:
    region = REGIONS[region_key]
    base_price = PIPE_BASE_PRICE_PER_M[pipe_size_mm]
    discount = quantity_discount(quantity_m)

    rows = []

    for c in COMPETITORS:
        price_per_m = (
            base_price
            * c.price_factor
            * region.freight_multiplier
            * region.market_pressure
            * discount
        )

        total_price = price_per_m * quantity_m
        total_score = (c.service_score + c.delivery_score + c.technical_score) / 3

        rows.append({
            "Competitor": c.name,
            "Positioning": c.pricing_position,
            "Price / m": round(price_per_m, 2),
            "Total price": round(total_price, 0),
            "Service": c.service_score,
            "Delivery": c.delivery_score,
            "Technical": c.technical_score,
            "Capability score": round(total_score, 1),
            "Capability band": score_band(total_score),
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
            max-width: 850px;
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
            Enter the pipe size, quantity and region to generate an indicative competitor pricing sheet,
            market range, Atlan price position and suggested bid strategy.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Sidebar Inputs
# =========================================================

with st.sidebar:
    st.markdown("## Pricing Inputs")

    pipe_size_mm = st.selectbox(
        "Pipe size",
        sorted(PIPE_BASE_PRICE_PER_M.keys()),
        index=2,
        format_func=lambda x: f"{x}mm",
    )

    quantity_m = st.number_input(
        "Quantity / length to sell (m)",
        min_value=1.0,
        value=120.0,
        step=10.0,
    )

    region_key = st.selectbox(
        "Region",
        list(REGIONS.keys()),
        format_func=lambda x: REGIONS[x].name,
    )

    st.divider()

    st.markdown("## Atlan Inputs")

    atlan_price_per_m = st.number_input(
        "Atlan proposed price / m",
        min_value=1.0,
        value=float(PIPE_BASE_PRICE_PER_M[pipe_size_mm]),
        step=5.0,
    )

    atlan_cost_per_m = st.number_input(
        "Atlan estimated cost / m",
        min_value=1.0,
        value=float(PIPE_BASE_PRICE_PER_M[pipe_size_mm] * 0.65),
        step=5.0,
    )

    st.markdown("### Capability Scores")

    atlan_service_score = st.slider("Service", 1, 10, 8)
    atlan_delivery_score = st.slider("Delivery", 1, 10, 8)
    atlan_technical_score = st.slider("Technical", 1, 10, 8)

    st.divider()

    generate = st.button(
        "Generate Pricing Sheet",
        type="primary",
        use_container_width=True,
    )


# =========================================================
# Main App
# =========================================================

if generate:
    region = REGIONS[region_key]

    df = build_competitor_pricing_sheet(
        pipe_size_mm=pipe_size_mm,
        quantity_m=quantity_m,
        region_key=region_key,
    )

    market_low = df["Price / m"].min()
    market_avg = df["Price / m"].mean()
    market_high = df["Price / m"].max()
    market_median = df["Price / m"].median()

    atlan_total_revenue = atlan_price_per_m * quantity_m
    atlan_total_cost = atlan_cost_per_m * quantity_m
    atlan_gross_profit = atlan_total_revenue - atlan_total_cost
    atlan_gross_margin = atlan_gross_profit / atlan_total_revenue

    atlan_price_gap = atlan_price_per_m - market_avg
    atlan_price_gap_pct = atlan_price_gap / market_avg

    competitor_avg_score = df["Capability score"].mean()
    atlan_score = (atlan_service_score + atlan_delivery_score + atlan_technical_score) / 3

    win_prob = win_probability(
        atlan_price_per_m,
        market_avg,
        atlan_score,
        competitor_avg_score,
    )

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Market Snapshot")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Market low", f"${market_low:,.2f}/m")
    k2.metric("Market average", f"${market_avg:,.2f}/m")
    k3.metric("Market high", f"${market_high:,.2f}/m")
    k4.metric("Job size", job_size_category(quantity_m))

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Atlan price gap", f"{atlan_price_gap_pct:.1%}")
    k6.metric("Atlan gross margin", f"{atlan_gross_margin:.1%}")
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
    st.subheader("Competitor Pricing Sheet")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1.1, 0.9])

    with col_left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Atlan Positioning")

        positioning = pd.DataFrame([
            {"Metric": "Pipe size", "Value": f"{pipe_size_mm}mm"},
            {"Metric": "Quantity", "Value": f"{quantity_m:,.0f}m"},
            {"Metric": "Region", "Value": region.name},
            {"Metric": "Atlan price / m", "Value": f"${atlan_price_per_m:,.2f}"},
            {"Metric": "Market average / m", "Value": f"${market_avg:,.2f}"},
            {"Metric": "Gap vs market", "Value": f"${atlan_price_gap:,.2f}/m ({atlan_price_gap_pct:.1%})"},
            {"Metric": "Atlan total revenue", "Value": f"${atlan_total_revenue:,.0f}"},
            {"Metric": "Gross profit", "Value": f"${atlan_gross_profit:,.0f}"},
            {"Metric": "Gross margin", "Value": f"{atlan_gross_margin:.1%}"},
            {"Metric": "Atlan capability score", "Value": f"{atlan_score:.1f}/10"},
        ])

        st.dataframe(positioning, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Recommended Bid Strategy")

        recommendation = strategy_recommendation(
            atlan_price_per_m,
            market_avg,
            atlan_gross_margin,
        )

        st.success(recommendation)

        st.markdown("#### Readout")
        st.write(
            f"Atlan is currently priced at **{atlan_price_gap_pct:.1%}** versus the estimated market average."
        )
        st.write(
            f"The estimated win probability is **{win_prob}**, with a gross margin of **{atlan_gross_margin:.1%}**."
        )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Suggested Pricing Scenarios")

    scenarios = pd.DataFrame([
        {
            "Scenario": "Aggressive",
            "Price / m": round(market_low * 0.99, 2),
            "Total revenue": round(market_low * 0.99 * quantity_m, 0),
            "Gross margin": f"{((market_low * 0.99) - atlan_cost_per_m) / (market_low * 0.99):.1%}",
            "Best for": "Strategic win / defend share",
        },
        {
            "Scenario": "Market aligned",
            "Price / m": round(market_avg, 2),
            "Total revenue": round(market_avg * quantity_m, 0),
            "Gross margin": f"{(market_avg - atlan_cost_per_m) / market_avg:.1%}",
            "Best for": "Balanced win rate and margin",
        },
        {
            "Scenario": "Premium",
            "Price / m": round(market_high * 0.98, 2),
            "Total revenue": round(market_high * 0.98 * quantity_m, 0),
            "Gross margin": f"{((market_high * 0.98) - atlan_cost_per_m) / (market_high * 0.98):.1%}",
            "Best for": "Less price-sensitive customer",
        },
    ])

    st.dataframe(
        scenarios,
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    csv = df.to_csv(index=False)

    st.download_button(
        label="Download Competitor Pricing Sheet",
        data=csv,
        file_name="atlan_competitor_pipe_pricing_sheet.csv",
        mime="text/csv",
        use_container_width=True,
    )

else:
    st.markdown(
        """
        <div class="section-card">
            <h3>Start by entering your pricing inputs</h3>
            <p class="muted">
                Choose a pipe size, quantity, region and Atlan price from the sidebar.
                The tool will generate a competitor pricing sheet and recommended bid strategy.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
