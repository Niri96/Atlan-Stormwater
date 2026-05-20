from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
import streamlit as st


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
    Competitor("Competitor A", "Aggressive / low-cost", 0.88),
    Competitor("Competitor B", "Market average", 1.00),
    Competitor("Competitor C", "Premium supplier", 1.16),
    Competitor("Competitor D", "Regional player", 0.96),
    Competitor("Competitor E", "Import / price-led", 0.82),
]

PIPE_BASE_RRP_PER_M: Dict[int, float] = {
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

PIPE_DEFAULT_COST_PER_M: Dict[int, float] = {
    size: round(rrp * 0.65, 2) for size, rrp in PIPE_BASE_RRP_PER_M.items()
}

PIPE_SIZE_OPTIONS = sorted(PIPE_BASE_RRP_PER_M.keys())


# =========================================================
# Helper Functions
# =========================================================

def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def money(value: float) -> str:
    return f"${value:,.0f}"


def percent(value: float) -> str:
    return f"{value:.1%}"


def build_default_product_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Pipe size mm": 375,
                "Quantity m": 120.0,
                "RRP / m": PIPE_BASE_RRP_PER_M[375],
                "Cost / m": PIPE_DEFAULT_COST_PER_M[375],
                "Freight cost": 0.0,
            },
            {
                "Pipe size mm": 450,
                "Quantity m": 80.0,
                "RRP / m": PIPE_BASE_RRP_PER_M[450],
                "Cost / m": PIPE_DEFAULT_COST_PER_M[450],
                "Freight cost": 0.0,
            },
        ]
    )


def clean_package_input(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    required_cols = [
        "Pipe size mm",
        "Quantity m",
        "RRP / m",
        "Cost / m",
        "Freight cost",
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = 0.0

    df["Pipe size mm"] = pd.to_numeric(df["Pipe size mm"], errors="coerce").fillna(0).astype(int)
    df["Quantity m"] = pd.to_numeric(df["Quantity m"], errors="coerce").fillna(0.0).clip(lower=0)
    df["RRP / m"] = pd.to_numeric(df["RRP / m"], errors="coerce").fillna(0.0).clip(lower=0)
    df["Cost / m"] = pd.to_numeric(df["Cost / m"], errors="coerce").fillna(0.0).clip(lower=0)
    df["Freight cost"] = pd.to_numeric(df["Freight cost"], errors="coerce").fillna(0.0).clip(lower=0)

    return df[df["Quantity m"] > 0].copy()


def calculate_product_lines(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "Discount %" not in df.columns:
        df["Discount %"] = 0.0

    df["Discount %"] = pd.to_numeric(df["Discount %"], errors="coerce").fillna(0.0).clip(lower=0, upper=100)

    df["Net sell price / m"] = df["RRP / m"] * (1 - df["Discount %"] / 100)
    df["RRP revenue"] = df["RRP / m"] * df["Quantity m"]
    df["Revenue"] = df["Net sell price / m"] * df["Quantity m"]

    df["Product cost"] = df["Cost / m"] * df["Quantity m"]
    df["Total cost incl. freight"] = df["Product cost"] + df["Freight cost"]

    df["Contribution $"] = df["Revenue"] - df["Total cost incl. freight"]
    df["Contribution margin %"] = df.apply(
        lambda row: safe_divide(row["Contribution $"], row["Revenue"]),
        axis=1,
    )

    df["RRP contribution $"] = df["RRP revenue"] - df["Total cost incl. freight"]
    df["RRP contribution margin %"] = df.apply(
        lambda row: safe_divide(row["RRP contribution $"], row["RRP revenue"]),
        axis=1,
    )

    df["Margin lost $"] = df["RRP contribution $"] - df["Contribution $"]
    df["Margin lost percentage points"] = (
        df["RRP contribution margin %"] - df["Contribution margin %"]
    ) * 100

    return df


def build_peer_comparison(product_lines: pd.DataFrame, region_key: str) -> pd.DataFrame:
    region = REGIONS[region_key]
    total_quantity = product_lines["Quantity m"].sum()
    total_freight = product_lines["Freight cost"].sum()

    rows = []

    for competitor in COMPETITORS:
        peer_revenue = 0.0

        for _, line in product_lines.iterrows():
            peer_price_per_m = (
                line["RRP / m"]
                * competitor.price_factor
                * region.freight_multiplier
                * region.market_pressure
            )

            peer_revenue += peer_price_per_m * line["Quantity m"]

        peer_total_package = peer_revenue

        rows.append(
            {
                "Peer": competitor.name,
                "Positioning": competitor.pricing_position,
                "Estimated package revenue": peer_total_package,
                "Freight assumed": total_freight,
                "Average package price / m": safe_divide(peer_total_package, total_quantity),
            }
        )

    return pd.DataFrame(rows)


def commercial_recommendation(package_margin: float, gap_vs_peer_avg: float, weighted_discount: float) -> str:
    if package_margin < 0.25:
        return "Margin risk is high. Review the discount, cost base or freight recovery before submitting."
    if weighted_discount >= 0.20:
        return "Discounting is material. Make sure the project value justifies the margin give-up."
    if gap_vs_peer_avg > 0.12:
        return "Package is materially above the peer average. Clearly justify the premium."
    if gap_vs_peer_avg < -0.05:
        return "Package is priced aggressively versus peers. Good conversion potential, but check margin discipline."
    return "Package is broadly market-aligned. Maintain price discipline and focus on conversion."


# =========================================================
# Page Setup
# =========================================================

st.set_page_config(
    page_title="Atlan Package Pricing Tool",
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
            max-width: 1320px;
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
            max-width: 920px;
        }}

        .section-card {{
            background: white;
            border: 1px solid rgba(11, 92, 255, 0.12);
            border-radius: 20px;
            padding: 22px;
            box-shadow: 0 10px 28px rgba(7, 27, 58, 0.06);
            margin-bottom: 18px;
        }}

        .muted {{
            color: rgba(7, 27, 58, 0.65);
            font-size: 14px;
        }}

        [data-testid="stMetricValue"] {{
            color: {ATLAN_DARK};
            font-weight: 800;
        }}

        section[data-testid="stSidebar"] {{
            background: #FFFFFF;
            border-right: 1px solid rgba(11, 92, 255, 0.10);
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
        <h1>Atlan Stormwater Package Pricing Tool</h1>
        <p>
            Enter the package, apply discount by product line, and see the live impact on
            contribution margin, margin at risk and peer pricing.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Sidebar
# =========================================================

with st.sidebar:
    st.markdown("## Market Inputs")

    region_key = st.selectbox(
        "Region",
        list(REGIONS.keys()),
        format_func=lambda x: REGIONS[x].name,
    )

    target_margin = st.slider(
        "Target contribution margin",
        min_value=0,
        max_value=70,
        value=35,
        step=1,
    ) / 100

    risk_margin = st.slider(
        "High-risk margin threshold",
        min_value=0,
        max_value=50,
        value=25,
        step=1,
    ) / 100


# =========================================================
# Step 1: Package Input
# =========================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Step 1: Enter Package")

package_input = st.data_editor(
    build_default_product_rows(),
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="package_input",
    column_config={
        "Pipe size mm": st.column_config.SelectboxColumn(
            "Pipe size mm",
            options=PIPE_SIZE_OPTIONS,
            required=True,
        ),
        "Quantity m": st.column_config.NumberColumn(
            "Quantity m",
            min_value=0.0,
            step=1.0,
            format="%.2f",
        ),
        "RRP / m": st.column_config.NumberColumn(
            "RRP / m",
            min_value=0.0,
            step=5.0,
            format="$%.2f",
        ),
        "Cost / m": st.column_config.NumberColumn(
            "Cost / m",
            min_value=0.0,
            step=5.0,
            format="$%.2f",
        ),
        "Freight cost": st.column_config.NumberColumn(
            "Freight cost",
            min_value=0.0,
            step=50.0,
            format="$%.2f",
        ),
    },
)

st.markdown("</div>", unsafe_allow_html=True)

clean_input = clean_package_input(package_input)

if clean_input.empty:
    st.info("Enter at least one product line with quantity greater than zero.")
    st.stop()


# =========================================================
# Step 2: Interactive Discount
# =========================================================

discount_df = clean_input.copy()
discount_df["Discount %"] = 0.0

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Step 2: Apply Discount")

discount_input = st.data_editor(
    discount_df,
    use_container_width=True,
    hide_index=True,
    key="discount_input",
    disabled=[
        "Pipe size mm",
        "Quantity m",
        "RRP / m",
        "Cost / m",
        "Freight cost",
    ],
    column_config={
        "Pipe size mm": st.column_config.NumberColumn("Pipe size mm", format="%d"),
        "Quantity m": st.column_config.NumberColumn("Quantity m", format="%.2f"),
        "RRP / m": st.column_config.NumberColumn("RRP / m", format="$%.2f"),
        "Cost / m": st.column_config.NumberColumn("Cost / m", format="$%.2f"),
        "Freight cost": st.column_config.NumberColumn("Freight cost", format="$%.2f"),
        "Discount %": st.column_config.NumberColumn(
            "Discount %",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            format="%.1f%%",
        ),
    },
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Calculations
# =========================================================

product_lines = calculate_product_lines(discount_input)

total_quantity = product_lines["Quantity m"].sum()
total_rrp_revenue = product_lines["RRP revenue"].sum()
total_revenue = product_lines["Revenue"].sum()
total_freight = product_lines["Freight cost"].sum()
total_product_cost = product_lines["Product cost"].sum()
total_cost_incl_freight = product_lines["Total cost incl. freight"].sum()
total_contribution = product_lines["Contribution $"].sum()

package_margin = safe_divide(total_contribution, total_revenue)

rrp_contribution = product_lines["RRP contribution $"].sum()
rrp_margin = safe_divide(rrp_contribution, total_rrp_revenue)

margin_lost_dollars = rrp_contribution - total_contribution
margin_lost_pp = (rrp_margin - package_margin) * 100

weighted_discount = safe_divide(total_rrp_revenue - total_revenue, total_rrp_revenue)


# =========================================================
# Package Summary
# =========================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Package Summary")

k1, k2, k3, k4 = st.columns(4)
k1.metric("RRP revenue", money(total_rrp_revenue))
k2.metric("Discounted revenue", money(total_revenue))
k3.metric("Total freight", money(total_freight))
k4.metric("Contribution margin", percent(package_margin))

k5, k6, k7, k8 = st.columns(4)
k5.metric("Weighted discount", percent(weighted_discount))
k6.metric("Contribution $", money(total_contribution))
k7.metric("Margin at risk", money(margin_lost_dollars))
k8.metric("Margin lost", f"{margin_lost_pp:.1f} pts")

if margin_lost_dollars > 0:
    st.warning(
        f"You are discounting the package by {weighted_discount:.1%}. "
        f"This reduces contribution margin from {rrp_margin:.1%} to {package_margin:.1%}, "
        f"putting {money(margin_lost_dollars)} of contribution margin at risk."
    )
else:
    st.success("No discount has been applied. There is no contribution margin leakage versus RRP.")

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Product Line Output
# =========================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Product Line Margin Detail")

output_cols = [
    "Pipe size mm",
    "Quantity m",
    "RRP / m",
    "Discount %",
    "Net sell price / m",
    "Cost / m",
    "Freight cost",
    "Revenue",
    "Product cost",
    "Total cost incl. freight",
    "Contribution $",
    "Contribution margin %",
    "Margin lost $",
    "Margin lost percentage points",
]

st.dataframe(
    product_lines[output_cols].style.format(
        {
            "Quantity m": "{:,.2f}",
            "RRP / m": "${:,.2f}",
            "Discount %": "{:.1f}%",
            "Net sell price / m": "${:,.2f}",
            "Cost / m": "${:,.2f}",
            "Freight cost": "${:,.0f}",
            "Revenue": "${:,.0f}",
            "Product cost": "${:,.0f}",
            "Total cost incl. freight": "${:,.0f}",
            "Contribution $": "${:,.0f}",
            "Contribution margin %": "{:.1%}",
            "Margin lost $": "${:,.0f}",
            "Margin lost percentage points": "{:.1f} pts",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Peer Comparison
# =========================================================

peer_df = build_peer_comparison(product_lines, region_key)

peer_avg = peer_df["Estimated package revenue"].mean()
gap_vs_peer_avg = safe_divide(total_revenue - peer_avg, peer_avg)

atlan_row = pd.DataFrame(
    [
        {
            "Peer": "Atlan proposed package",
            "Positioning": "Current quote",
            "Estimated package revenue": total_revenue,
            "Freight assumed": total_freight,
            "Average package price / m": safe_divide(total_revenue, total_quantity),
        }
    ]
)

peer_display = pd.concat([peer_df, atlan_row], ignore_index=True)
peer_display = peer_display.sort_values("Estimated package revenue").reset_index(drop=True)

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Peer Package Comparison")

st.dataframe(
    peer_display.style.format(
        {
            "Estimated package revenue": "${:,.0f}",
            "Freight assumed": "${:,.0f}",
            "Average package price / m": "${:,.2f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

recommendation = commercial_recommendation(
    package_margin=package_margin,
    gap_vs_peer_avg=gap_vs_peer_avg,
    weighted_discount=weighted_discount,
)

if package_margin < risk_margin:
    st.error(recommendation)
elif package_margin < target_margin:
    st.warning(recommendation)
else:
    st.success(recommendation)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Download
# =========================================================

download_df = product_lines.copy()

csv = download_df.to_csv(index=False)

st.download_button(
    label="Download Package Pricing Output",
    data=csv,
    file_name="atlan_package_pricing_output.csv",
    mime="text/csv",
    use_container_width=True,
)
