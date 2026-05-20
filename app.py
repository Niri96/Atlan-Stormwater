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


# =========================================================
# Assumptions
# =========================================================

ATLAN_BLUE = "#0B5CFF"
ATLAN_DARK = "#071B3A"
ATLAN_LIGHT = "#EEF5FF"
ATLAN_RED_LIGHT = "#FFF1F1"
ATLAN_AMBER_LIGHT = "#FFF8E6"
ATLAN_GREEN_LIGHT = "#EEFBEF"

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
# Helpers
# =========================================================

def money(value: float) -> str:
    return f"${value:,.0f}"


def money_2(value: float) -> str:
    return f"${value:,.2f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def margin_band(contribution_margin: float) -> tuple[str, str]:
    if contribution_margin < 0.25:
        return "High risk", ATLAN_RED_LIGHT
    if contribution_margin < 0.35:
        return "Watch margin", ATLAN_AMBER_LIGHT
    return "Healthy", ATLAN_GREEN_LIGHT


def build_default_product_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Pipe size mm": 375,
            "Quantity m": 120.0,
            "RRP / m": PIPE_BASE_RRP_PER_M[375],
            "Discount %": 0.0,
            "Cost / m": PIPE_DEFAULT_COST_PER_M[375],
            "Freight cost": 0.0,
        },
        {
            "Pipe size mm": 450,
            "Quantity m": 80.0,
            "RRP / m": PIPE_BASE_RRP_PER_M[450],
            "Discount %": 0.0,
            "Cost / m": PIPE_DEFAULT_COST_PER_M[450],
            "Freight cost": 0.0,
        },
    ])


def calculate_product_lines(product_df: pd.DataFrame) -> pd.DataFrame:
    df = product_df.copy()

    required_cols = ["Pipe size mm", "Quantity m", "RRP / m", "Discount %", "Cost / m", "Freight cost"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0.0

    df["Pipe size mm"] = pd.to_numeric(df["Pipe size mm"], errors="coerce").fillna(0).astype(int)
    df["Quantity m"] = pd.to_numeric(df["Quantity m"], errors="coerce").fillna(0.0).clip(lower=0)
    df["RRP / m"] = pd.to_numeric(df["RRP / m"], errors="coerce").fillna(0.0).clip(lower=0)
    df["Discount %"] = pd.to_numeric(df["Discount %"], errors="coerce").fillna(0.0).clip(lower=0, upper=100)
    df["Cost / m"] = pd.to_numeric(df["Cost / m"], errors="coerce").fillna(0.0).clip(lower=0)
    df["Freight cost"] = pd.to_numeric(df["Freight cost"], errors="coerce").fillna(0.0).clip(lower=0)

    df["Net sell price / m"] = df["RRP / m"] * (1 - df["Discount %"] / 100)
    df["Revenue before freight"] = df["Net sell price / m"] * df["Quantity m"]
    df["RRP revenue"] = df["RRP / m"] * df["Quantity m"]
    df["Product cost"] = df["Cost / m"] * df["Quantity m"]
    df["Total cost incl. freight"] = df["Product cost"] + df["Freight cost"]
    df["Contribution $"] = df["Revenue before freight"] - df["Total cost incl. freight"]
    df["Contribution margin %"] = df.apply(
        lambda row: safe_divide(row["Contribution $"], row["Revenue before freight"]), axis=1
    )

    df["RRP contribution $"] = df["RRP revenue"] - df["Total cost incl. freight"]
    df["RRP contribution margin %"] = df.apply(
        lambda row: safe_divide(row["RRP contribution $"], row["RRP revenue"]), axis=1
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
            base_rrp = line["RRP / m"]
            quantity = line["Quantity m"]
            peer_price_per_m = (
                base_rrp
                * competitor.price_factor
                * region.freight_multiplier
                * region.market_pressure
            )
            peer_revenue += peer_price_per_m * quantity

        peer_total_package = peer_revenue + total_freight
        rows.append({
            "Peer": competitor.name,
            "Positioning": competitor.pricing_position,
            "Estimated product revenue": peer_revenue,
            "Freight assumed": total_freight,
            "Estimated total package": peer_total_package,
            "Average package price / m": safe_divide(peer_total_package, total_quantity),
        })

    return pd.DataFrame(rows)


def commercial_recommendation(package_margin: float, package_gap_vs_market: float, avg_discount_pct: float) -> str:
    if package_margin < 0.25:
        return "Margin risk is high. Review the discount, cost base, or freight recovery before submitting."
    if avg_discount_pct >= 20:
        return "Discounting is material. Make sure the volume or strategic value justifies the margin give-up."
    if package_gap_vs_market > 0.12:
        return "Package is materially above the peer average. Lead with availability, service level, and product quality."
    if package_gap_vs_market < -0.05:
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
        .small-card {{
            background: {ATLAN_LIGHT};
            border: 1px solid rgba(11, 92, 255, 0.14);
            border-radius: 16px;
            padding: 16px;
        }}
        .warning-card {{
            border-radius: 16px;
            padding: 16px;
            border: 1px solid rgba(7, 27, 58, 0.10);
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
            Build a multi-product pipe package, apply line-level RRP discounts and freight,
            then compare the total landed package against peers and quantify contribution margin impact.
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

    st.markdown("### Margin Thresholds")
    target_margin = st.slider("Target contribution margin", 0, 70, 35, 1) / 100
    risk_margin = st.slider("High-risk margin threshold", 0, 50, 25, 1) / 100

    st.divider()

    st.markdown("## Product Setup")
    st.caption("Add each product line below. Freight and discount are entered per product line.")

# =========================================================
# Main Inputs
# =========================================================

region = REGIONS[region_key]

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Product Pricing Inputs")
st.caption("Edit the rows directly. Add more rows for additional pipe dimensions or product lines.")

product_input = st.data_editor(
    build_default_product_rows(),
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Pipe size mm": st.column_config.SelectboxColumn(
            "Pipe size mm",
            options=PIPE_SIZE_OPTIONS,
            required=True,
            help="Select the pipe dimension for this product line.",
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
        "Discount %": st.column_config.NumberColumn(
            "Discount %",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            format="%.1f%%",
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
            help="Freight cost allocated to this specific product line.",
        ),
    },
)

calculate = st.button("Calculate Package Pricing", type="primary", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# Main App
# =========================================================

if calculate:
    product_lines = calculate_product_lines(product_input)
    product_lines = product_lines[product_lines["Quantity m"] > 0].copy()

    if product_lines.empty:
        st.error("Please enter at least one product line with a quantity greater than zero.")
        st.stop()

    total_quantity = product_lines["Quantity m"].sum()
    total_rrp_revenue = product_lines["RRP revenue"].sum()
    total_revenue = product_lines["Revenue before freight"].sum()
    total_product_cost = product_lines["Product cost"].sum()
    total_freight = product_lines["Freight cost"].sum()
    total_cost_incl_freight = product_lines["Total cost incl. freight"].sum()
    total_contribution = product_lines["Contribution $"].sum()
    package_margin = safe_divide(total_contribution, total_revenue)

    rrp_contribution = product_lines["RRP contribution $"].sum()
    rrp_margin = safe_divide(rrp_contribution, total_rrp_revenue)
    margin_lost_dollars = rrp_contribution - total_contribution
    margin_lost_pp = (rrp_margin - package_margin) * 100
    weighted_discount_pct = safe_divide(total_rrp_revenue - total_revenue, total_rrp_revenue)

    peer_df = build_peer_comparison(product_lines, region_key)
    peer_low = peer_df["Estimated total package"].min()
    peer_avg = peer_df["Estimated total package"].mean()
    peer_high = peer_df["Estimated total package"].max()

    atlan_total_package = total_revenue
    package_gap_vs_market = safe_divide(atlan_total_package - peer_avg, peer_avg)
    margin_status, margin_colour = margin_band(package_margin)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Package Summary")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total package revenue", money(total_revenue))
    k2.metric("Total freight", money(total_freight))
    k3.metric("Contribution $", money(total_contribution))
    k4.metric("Contribution margin", pct(package_margin))

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Weighted discount", pct(weighted_discount_pct))
    k6.metric("Margin lost", money(margin_lost_dollars))
    k7.metric("Margin lost", f"{margin_lost_pp:.1f} pts")
    k8.metric("Vs peer average", pct(package_gap_vs_market))

    st.markdown(
        f"""
        <div class="warning-card" style="background:{margin_colour};">
            <b>Margin status: {margin_status}</b><br>
            <span class="muted">
                At RRP, the package contribution margin would be {rrp_margin:.1%}. After discounting,
                it is {package_margin:.1%}. The discount has reduced contribution margin by
                {margin_lost_pp:.1f} percentage points, or {money(margin_lost_dollars)} of contribution.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Product Line Output")

    display_lines = product_lines[[
        "Pipe size mm",
        "Quantity m",
        "RRP / m",
        "Discount %",
        "Net sell price / m",
        "Cost / m",
        "Freight cost",
        "Revenue before freight",
        "Product cost",
        "Total cost incl. freight",
        "Contribution $",
        "Contribution margin %",
        "Margin lost $",
        "Margin lost percentage points",
    ]].copy()

    st.dataframe(
        display_lines.style.format({
            "Quantity m": "{:,.2f}",
            "RRP / m": "${:,.2f}",
            "Discount %": "{:,.1f}%",
            "Net sell price / m": "${:,.2f}",
            "Cost / m": "${:,.2f}",
            "Freight cost": "${:,.0f}",
            "Revenue before freight": "${:,.0f}",
            "Product cost": "${:,.0f}",
            "Total cost incl. freight": "${:,.0f}",
            "Contribution $": "${:,.0f}",
            "Contribution margin %": "{:.1%}",
            "Margin lost $": "${:,.0f}",
            "Margin lost percentage points": "{:,.1f} pts",
        }),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([1.15, 0.85])

    with col_left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Peer Package Comparison")

        peer_display = peer_df.copy()
        peer_display.loc[len(peer_display)] = {
            "Peer": "Atlan proposed package",
            "Positioning": "Current quote",
            "Estimated product revenue": total_revenue,
            "Freight assumed": total_freight,
            "Estimated total package": atlan_total_package,
            "Average package price / m": safe_divide(atlan_total_package, total_quantity),
        }
        peer_display = peer_display.sort_values("Estimated total package").reset_index(drop=True)

        st.dataframe(
            peer_display.style.format({
                "Estimated product revenue": "${:,.0f}",
                "Freight assumed": "${:,.0f}",
                "Estimated total package": "${:,.0f}",
                "Average package price / m": "${:,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Commercial Readout")

        recommendation = commercial_recommendation(
            package_margin=package_margin,
            package_gap_vs_market=package_gap_vs_market,
            avg_discount_pct=weighted_discount_pct * 100,
        )

        if package_margin < risk_margin:
            st.error(recommendation)
        elif package_margin < target_margin:
            st.warning(recommendation)
        else:
            st.success(recommendation)

        st.write(
            f"The proposed package is **{pct(package_gap_vs_market)}** versus the estimated peer average."
        )
        st.write(
            f"The weighted discount off RRP is **{pct(weighted_discount_pct)}**."
        )
        st.write(
            f"Contribution margin has moved from **{pct(rrp_margin)}** at RRP to **{pct(package_margin)}** after discounting and freight."
        )

        st.markdown("#### Market Range")
        st.write(f"Peer low: **{money(peer_low)}**")
        st.write(f"Peer average: **{money(peer_avg)}**")
        st.write(f"Peer high: **{money(peer_high)}**")

        st.markdown("#### Region Note")
        st.caption(region.notes)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Download Outputs")

    output_df = product_lines.copy()
    output_df["Region"] = region.name
    output_df["Package total revenue"] = total_revenue
    output_df["Package contribution margin %"] = package_margin
    output_df["Weighted discount %"] = weighted_discount_pct
    output_df["Peer average package"] = peer_avg
    output_df["Package gap vs peer average %"] = package_gap_vs_market

    csv = output_df.to_csv(index=False)
    st.download_button(
        label="Download Package Pricing Output",
        data=csv,
        file_name="atlan_package_pricing_output.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.markdown(
        """
        <div class="section-card">
            <h3>Start by adding product lines</h3>
            <p class="muted">
                Add each pipe size as a separate line, enter the quantity, RRP, discount, cost and freight.
                Then calculate the package to see contribution margin impact and peer positioning.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
