from __future__ import annotations

import streamlit as st
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List


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


REGIONS: Dict[str, RegionProfile] = {
    "QLD": RegionProfile("QLD", "Queensland", 1.05, 0.95, "High", "Competitive market with pricing pressure."),
    "NSW": RegionProfile("NSW", "New South Wales", 1.10, 0.97, "High", "High-volume market with strong peer activity."),
    "VIC": RegionProfile("VIC", "Victoria", 1.08, 1.00, "Medium", "Balanced market with room for value-led pricing."),
    "WA": RegionProfile("WA", "Western Australia", 1.18, 1.05, "Medium", "Higher freight and regional supply costs."),
    "SA": RegionProfile("SA", "South Australia", 1.12, 1.02, "Medium", "Moderate pricing pressure and freight sensitivity."),
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
    region: RegionProfile,
) -> str:
    gap = (atlan_price - market_avg) / market_avg

    if gross_margin < 0.25:
        return "Do not chase price too hard. Margin is already thin, so only discount if strategically important."

    if gap > 0.12:
        return "Atlan is materially above market. Either sharpen price or clearly justify the premium through engineering support, availability, and delivery certainty."

    if gap > 0.04:
        return "Atlan is slightly above market. Position as value-led, not cheapest. Emphasise service, design support, stock availability, and lower execution risk."

    if gap >= -0.03:
        return "Atlan is market-aligned. Maintain pricing discipline and focus on conversion."

    return "Atlan is pricing aggressively. Good win potential, but check that the discount is not eroding margin unnecessarily."


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
            "Pricing position": c.pricing_position,
            "Pipe size": f"{pipe_size_mm}mm",
            "Quantity": quantity_m,
            "Region": region.name,
            "Price / m": round(price_per_m, 2),
            "Total price": round(total_price, 0),
            "Service score": c.service_score,
            "Delivery score": c.delivery_score,
            "Technical score": c.technical_score,
            "Overall capability score": round(total_score, 1),
            "Capability band": score_band(total_score),
        })

    return pd.DataFrame(rows)


st.set_page_config(
    page_title="Competitor Pipe Pricing Tool",
    layout="wide",
)

st.title("Competitor Pipe Pricing Tool")
st.caption("Generate an indicative competitor pricing sheet by pipe size, quantity, and region.")

with st.sidebar:
    st.header("Inputs")

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
    st.header("Atlan price inputs")

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

    atlan_service_score = st.slider("Atlan service score", 1, 10, 8)
    atlan_delivery_score = st.slider("Atlan delivery score", 1, 10, 8)
    atlan_technical_score = st.slider("Atlan technical score", 1, 10, 8)

    generate = st.button("Generate competitor pricing sheet", type="primary", use_container_width=True)


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

    competitor_avg_score = df["Overall capability score"].mean()
    atlan_score = (atlan_service_score + atlan_delivery_score + atlan_technical_score) / 3

    win_prob = win_probability(
        atlan_price_per_m,
        market_avg,
        atlan_score,
        competitor_avg_score,
    )

    st.subheader("Market Summary")

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

    st.info(region.notes)

    st.markdown("### Competitor Pricing Sheet")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### Atlan Positioning")

    positioning_rows = pd.DataFrame([
        {
            "Metric": "Atlan price / m",
            "Value": f"${atlan_price_per_m:,.2f}",
        },
        {
            "Metric": "Atlan total revenue",
            "Value": f"${atlan_total_revenue:,.0f}",
        },
        {
            "Metric": "Atlan estimated cost",
            "Value": f"${atlan_total_cost:,.0f}",
        },
        {
            "Metric": "Atlan gross profit",
            "Value": f"${atlan_gross_profit:,.0f}",
        },
        {
            "Metric": "Atlan gross margin",
            "Value": f"{atlan_gross_margin:.1%}",
        },
        {
            "Metric": "Market average price / m",
            "Value": f"${market_avg:,.2f}",
        },
        {
            "Metric": "Gap vs market average",
            "Value": f"${atlan_price_gap:,.2f}/m ({atlan_price_gap_pct:.1%})",
        },
        {
            "Metric": "Atlan capability score",
            "Value": f"{atlan_score:.1f}/10",
        },
        {
            "Metric": "Competitor average capability score",
            "Value": f"{competitor_avg_score:.1f}/10",
        },
    ])

    st.dataframe(positioning_rows, use_container_width=True, hide_index=True)

    st.markdown("### Recommended Bid Strategy")
    st.success(
        strategy_recommendation(
            atlan_price_per_m,
            market_avg,
            atlan_gross_margin,
            region,
        )
    )

    st.markdown("### Suggested Pricing Scenarios")

    scenarios = pd.DataFrame([
        {
            "Scenario": "Aggressive",
            "Price / m": round(market_low * 0.99, 2),
            "Total revenue": round(market_low * 0.99 * quantity_m, 0),
            "Gross margin": round(((market_low * 0.99) - atlan_cost_per_m) / (market_low * 0.99), 3),
            "Use case": "Win priority / strategic job",
        },
        {
            "Scenario": "Market aligned",
            "Price / m": round(market_avg, 2),
            "Total revenue": round(market_avg * quantity_m, 0),
            "Gross margin": round((market_avg - atlan_cost_per_m) / market_avg, 3),
            "Use case": "Balanced win rate and margin",
        },
        {
            "Scenario": "Premium",
            "Price / m": round(market_high * 0.98, 2),
            "Total revenue": round(market_high * 0.98 * quantity_m, 0),
            "Gross margin": round(((market_high * 0.98) - atlan_cost_per_m) / (market_high * 0.98), 3),
            "Use case": "Premium positioning / less price-sensitive buyer",
        },
    ])

    st.dataframe(scenarios, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False)

    st.download_button(
        label="Download competitor pricing sheet",
        data=csv,
        file_name="competitor_pipe_pricing_sheet.csv",
        mime="text/csv",
    )

else:
    st.info("Enter pipe size, quantity, region, and Atlan pricing inputs, then click generate.")
