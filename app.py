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
    market_pressure: float
    notes: str


@dataclass(frozen=True)
class Competitor:
    name: str
    pricing_position: str
    price_factor: float


@dataclass(frozen=True)
class FleetOption:
    name: str
    deck_length_m: float
    deck_width_m: float
    max_length_m: float
    payload_t: float
    litres_per_100km: float
    maintenance_per_km: float
    pallets: int


# =========================================================
# Assumptions
# =========================================================

ATLAN_BLUE = "#0B5CFF"
ATLAN_DARK = "#071B3A"
ATLAN_LIGHT = "#EEF5FF"
ATLAN_GREEN = "#EAF8EE"
ATLAN_AMBER = "#FFF7E6"
ATLAN_RED = "#FFF0F0"

REGIONS: Dict[str, RegionProfile] = {
    "QLD": RegionProfile("QLD", "Queensland", 0.95, "Competitive pipe market with strong pricing pressure."),
    "NSW": RegionProfile("NSW", "New South Wales", 0.97, "High-volume market with active peer competition."),
    "VIC": RegionProfile("VIC", "Victoria", 1.00, "Balanced market with room for value-led pricing."),
    "WA": RegionProfile("WA", "Western Australia", 1.05, "Higher freight exposure and regional supply cost."),
    "SA": RegionProfile("SA", "South Australia", 1.02, "Moderate pricing pressure with freight sensitivity."),
    "TAS": RegionProfile("TAS", "Tasmania", 1.08, "Freight-sensitive market with ferry / line-haul exposure."),
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

ZONE_KM = {
    "Metro": 30,
    "Outer Metro": 60,
    "Regional": 150,
    "Remote": 350,
    "TAS": 600,
}

FLEET_OPTIONS: Dict[str, FleetOption] = {
    "Ute": FleetOption("Ute", 1.7, 1.7, 1.7, 0.5, 12, 0.10, 2),
    "Ute + trailer": FleetOption("Ute + trailer", 6.7, 2.4, 6.7, 3.2, 16, 0.14, 6),
    "6.5m truck": FleetOption("6.5m truck", 6.7, 2.4, 6.7, 4.0, 20, 0.18, 8),
    "6.5m truck + trailer": FleetOption("6.5m truck + trailer", 13.4, 2.4, 13.4, 7.2, 25, 0.22, 14),
    "8m truck": FleetOption("8m truck", 7.9, 2.4, 7.9, 8.0, 30, 0.22, 12),
    "8m truck + trailer": FleetOption("8m truck + trailer", 14.6, 2.4, 14.6, 11.2, 35, 0.28, 18),
}

LINE_HAUL_OPTIONS = {
    "None": 0.0,
    "Albury → Hallam flat rate": 1700.0,
    "Bairnsdale Semi-trailer per km": 9.00,
    "Bairnsdale B-Double per km": 10.50,
}


# =========================================================
# Helpers
# =========================================================

def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def money(value: float) -> str:
    return f"${value:,.0f}"


def percent(value: float) -> str:
    return f"{value:.1%}"


def margin_status(package_margin: float) -> tuple[str, str]:
    if package_margin < 0.25:
        return "Margin at risk", ATLAN_RED
    if package_margin < 0.35:
        return "Watch margin", ATLAN_AMBER
    return "Healthy margin", ATLAN_GREEN


def calculate_fleet_cost_per_km(fleet: FleetOption, diesel_price: float) -> float:
    fuel_per_km = fleet.litres_per_100km / 100 * diesel_price
    return fuel_per_km + fleet.maintenance_per_km


def calculate_internal_freight(
    km_one_way: float,
    trip_type: str,
    fleet_name: str,
    driver_rate_per_hr: float,
    diesel_price: float,
    avg_kmh: float,
    wide_load_kmh: float,
    site_hours: float,
    is_wide_load: bool,
    fuel_levy_pct: float,
    permit_cost: float,
) -> float:
    fleet = FLEET_OPTIONS[fleet_name]
    speed = wide_load_kmh if is_wide_load else avg_kmh
    speed = max(speed, 1)

    distance_km = km_one_way * 2 if trip_type == "Return" else km_one_way
    drive_hours = distance_km / speed
    total_hours = drive_hours + site_hours

    labour_cost = total_hours * driver_rate_per_hr
    vehicle_cost = distance_km * calculate_fleet_cost_per_km(fleet, diesel_price)
    fuel_levy = vehicle_cost * fuel_levy_pct
    permit = permit_cost if is_wide_load else 0

    return labour_cost + vehicle_cost + fuel_levy + permit


def calculate_linehaul_freight(option: str, total_km: float) -> float:
    if option == "None":
        return 0.0
    if option == "Albury → Hallam flat rate":
        return LINE_HAUL_OPTIONS[option]
    return LINE_HAUL_OPTIONS[option] * total_km


def build_default_product_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Pipe size mm": 375,
                "Quantity m": 120.0,
                "RRP / m": PIPE_BASE_RRP_PER_M[375],
                "Cost / m": PIPE_DEFAULT_COST_PER_M[375],
                "Freight method": "Internal fleet",
                "Zone": "Outer Metro",
                "km one-way": ZONE_KM["Outer Metro"],
                "Trip": "Return",
                "Fleet": "6.5m truck",
                "Site hrs": 1.0,
                "Wide load": False,
                "Line haul": "None",
                "Line haul km": 0.0,
                "Manual freight override": 0.0,
            },
            {
                "Pipe size mm": 450,
                "Quantity m": 80.0,
                "RRP / m": PIPE_BASE_RRP_PER_M[450],
                "Cost / m": PIPE_DEFAULT_COST_PER_M[450],
                "Freight method": "Internal fleet",
                "Zone": "Metro",
                "km one-way": ZONE_KM["Metro"],
                "Trip": "Return",
                "Fleet": "6.5m truck",
                "Site hrs": 1.0,
                "Wide load": False,
                "Line haul": "None",
                "Line haul km": 0.0,
                "Manual freight override": 0.0,
            },
        ]
    )


def clean_package_input(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    required_defaults = {
        "Pipe size mm": 375,
        "Quantity m": 0.0,
        "RRP / m": 0.0,
        "Cost / m": 0.0,
        "Freight method": "Internal fleet",
        "Zone": "Metro",
        "km one-way": 30.0,
        "Trip": "Return",
        "Fleet": "6.5m truck",
        "Site hrs": 1.0,
        "Wide load": False,
        "Line haul": "None",
        "Line haul km": 0.0,
        "Manual freight override": 0.0,
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    df["Pipe size mm"] = pd.to_numeric(df["Pipe size mm"], errors="coerce").fillna(375).astype(int)
    df["Quantity m"] = pd.to_numeric(df["Quantity m"], errors="coerce").fillna(0.0).clip(lower=0)
    df["RRP / m"] = pd.to_numeric(df["RRP / m"], errors="coerce").fillna(0.0).clip(lower=0)
    df["Cost / m"] = pd.to_numeric(df["Cost / m"], errors="coerce").fillna(0.0).clip(lower=0)
    df["km one-way"] = pd.to_numeric(df["km one-way"], errors="coerce").fillna(0.0).clip(lower=0)
    df["Site hrs"] = pd.to_numeric(df["Site hrs"], errors="coerce").fillna(1.0).clip(lower=0)
    df["Line haul km"] = pd.to_numeric(df["Line haul km"], errors="coerce").fillna(0.0).clip(lower=0)
    df["Manual freight override"] = pd.to_numeric(df["Manual freight override"], errors="coerce").fillna(0.0).clip(lower=0)

    df["RRP / m"] = df.apply(
        lambda row: PIPE_BASE_RRP_PER_M.get(row["Pipe size mm"], row["RRP / m"]) if row["RRP / m"] == 0 else row["RRP / m"],
        axis=1,
    )
    df["Cost / m"] = df.apply(
        lambda row: PIPE_DEFAULT_COST_PER_M.get(row["Pipe size mm"], row["Cost / m"]) if row["Cost / m"] == 0 else row["Cost / m"],
        axis=1,
    )

    return df[df["Quantity m"] > 0].copy()


def add_calculated_freight(
    df: pd.DataFrame,
    driver_rate_per_hr: float,
    diesel_price: float,
    avg_kmh: float,
    wide_load_kmh: float,
    fuel_levy_pct: float,
    permit_cost: float,
) -> pd.DataFrame:
    df = df.copy()
    freight_costs = []

    for _, row in df.iterrows():
        manual_override = float(row.get("Manual freight override", 0.0))
        if manual_override > 0:
            freight_costs.append(manual_override)
            continue

        method = row.get("Freight method", "Internal fleet")

        if method == "Line haul":
            freight_cost = calculate_linehaul_freight(
                option=row.get("Line haul", "None"),
                total_km=float(row.get("Line haul km", 0.0)),
            )
        else:
            freight_cost = calculate_internal_freight(
                km_one_way=float(row.get("km one-way", 0.0)),
                trip_type=row.get("Trip", "Return"),
                fleet_name=row.get("Fleet", "6.5m truck"),
                driver_rate_per_hr=driver_rate_per_hr,
                diesel_price=diesel_price,
                avg_kmh=avg_kmh,
                wide_load_kmh=wide_load_kmh,
                site_hours=float(row.get("Site hrs", 1.0)),
                is_wide_load=bool(row.get("Wide load", False)),
                fuel_levy_pct=fuel_levy_pct,
                permit_cost=permit_cost,
            )

        freight_costs.append(freight_cost)

    df["Calculated freight"] = freight_costs
    return df


def calculate_product_lines(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "Discount %" not in df.columns:
        df["Discount %"] = 0.0

    df["Discount %"] = pd.to_numeric(df["Discount %"], errors="coerce").fillna(0.0).clip(lower=0, upper=100)
    df["Freight cost"] = df["Calculated freight"]

    df["Net sell price / m"] = df["RRP / m"] * (1 - df["Discount %"] / 100)
    df["RRP revenue"] = df["RRP / m"] * df["Quantity m"]
    df["Revenue"] = df["Net sell price / m"] * df["Quantity m"]
    df["Product cost"] = df["Cost / m"] * df["Quantity m"]
    df["Total cost incl. freight"] = df["Product cost"] + df["Freight cost"]
    df["Contribution $"] = df["Revenue"] - df["Total cost incl. freight"]
    df["Contribution margin %"] = df.apply(lambda row: safe_divide(row["Contribution $"], row["Revenue"]), axis=1)
    df["RRP contribution $"] = df["RRP revenue"] - df["Total cost incl. freight"]
    df["RRP contribution margin %"] = df.apply(lambda row: safe_divide(row["RRP contribution $"], row["RRP revenue"]), axis=1)
    df["Margin lost $"] = df["RRP contribution $"] - df["Contribution $"]
    df["Margin lost percentage points"] = (df["RRP contribution margin %"] - df["Contribution margin %"]) * 100

    return df


def build_competitor_freight_defaults(total_atlan_freight: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Peer": c.name, "Pricing position": c.pricing_position, "Price factor": c.price_factor, "Competitor freight": round(total_atlan_freight * 1.00, 0)}
            for c in COMPETITORS
        ]
    )


def build_peer_comparison(product_lines: pd.DataFrame, competitor_assumptions: pd.DataFrame, region_key: str) -> pd.DataFrame:
    region = REGIONS[region_key]
    total_quantity = product_lines["Quantity m"].sum()
    rows = []

    for _, peer in competitor_assumptions.iterrows():
        product_revenue = 0.0
        for _, line in product_lines.iterrows():
            peer_price_per_m = line["RRP / m"] * float(peer["Price factor"]) * region.market_pressure
            product_revenue += peer_price_per_m * line["Quantity m"]

        freight = float(peer.get("Competitor freight", 0.0))
        total_package = product_revenue + freight

        rows.append(
            {
                "Peer": peer["Peer"],
                "Pricing position": peer["Pricing position"],
                "Product revenue": product_revenue,
                "Freight": freight,
                "Total package": total_package,
                "Avg package price / m": safe_divide(total_package, total_quantity),
            }
        )

    return pd.DataFrame(rows)


def recommendation(package_margin: float, gap_vs_peer_avg: float, weighted_discount: float) -> str:
    if package_margin < 0.25:
        return "Margin risk is high. Review discounting, cost base or freight recovery before submitting."
    if weighted_discount >= 0.20:
        return "Discounting is material. Confirm the strategic value or volume upside before approving."
    if gap_vs_peer_avg > 0.12:
        return "Package is above peer average. Lead with service, reliability and availability."
    if gap_vs_peer_avg < -0.05:
        return "Package is priced aggressively. Strong conversion potential, but protect margin discipline."
    return "Package is broadly market-aligned. Maintain price discipline and focus on conversion."


# =========================================================
# Page Setup
# =========================================================

st.set_page_config(page_title="Atlan Executive Pricing Tool", page_icon="💧", layout="wide")

st.markdown(
    f"""
    <style>
        .stApp {{ background: linear-gradient(180deg, #F4F8FF 0%, #FFFFFF 48%); }}
        .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1480px; }}
        .hero {{ background: radial-gradient(circle at top left, #2F7DFF 0%, {ATLAN_BLUE} 35%, #06265F 100%); padding: 34px 38px; border-radius: 28px; color: white; box-shadow: 0 22px 48px rgba(7, 27, 58, 0.22); margin-bottom: 22px; }}
        .hero h1 {{ font-size: 40px; line-height: 1.05; margin: 0 0 10px 0; font-weight: 850; letter-spacing: -0.02em; }}
        .hero p {{ font-size: 17px; opacity: 0.93; max-width: 980px; margin: 0; }}
        .section-card {{ background: rgba(255,255,255,0.96); border: 1px solid rgba(11,92,255,0.12); border-radius: 22px; padding: 22px; box-shadow: 0 12px 30px rgba(7,27,58,0.065); margin-bottom: 18px; }}
        .mini-card {{ border-radius: 18px; padding: 18px; border: 1px solid rgba(7,27,58,0.10); box-shadow: inset 0 1px 0 rgba(255,255,255,0.7); }}
        .muted {{ color: rgba(7,27,58,0.65); font-size: 14px; }}
        [data-testid="stMetricValue"] {{ color: {ATLAN_DARK}; font-weight: 850; letter-spacing: -0.02em; }}
        [data-testid="stMetricLabel"] {{ color: rgba(7,27,58,0.70); font-weight: 650; }}
        section[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid rgba(11,92,255,0.10); }}
        div[data-testid="stDataFrame"] {{ border-radius: 16px; overflow: hidden; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>Atlan Stormwater Executive Pricing Tool</h1>
        <p>
            Build a multi-product package, calculate freight using the VIC/TAS freight logic,
            apply live discounts, and compare the landed package against peer pricing.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Sidebar Controls
# =========================================================

with st.sidebar:
    st.markdown("## Market")
    region_key = st.selectbox("Region", list(REGIONS.keys()), index=2, format_func=lambda x: REGIONS[x].name)
    target_margin = st.slider("Target contribution margin", 0, 70, 35, 1) / 100
    risk_margin = st.slider("High-risk margin threshold", 0, 50, 25, 1) / 100

    st.divider()
    st.markdown("## Freight Assumptions")
    driver_rate = st.number_input("Driver $/hr", min_value=0.0, value=100.0, step=10.0)
    diesel_price = st.number_input("Diesel $/L", min_value=0.0, value=3.00, step=0.10)
    avg_kmh = st.number_input("Avg km/h", min_value=1.0, value=60.0, step=5.0)
    wide_load_kmh = st.number_input("Wide-load km/h", min_value=1.0, value=50.0, step=5.0)
    fuel_levy_pct = st.number_input("Fuel levy %", min_value=0.0, value=15.0, step=1.0) / 100
    permit_cost = st.number_input("Default permit $", min_value=0.0, value=350.0, step=50.0)


# =========================================================
# Step 1: Package Input
# =========================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Step 1 — Enter Package + Freight Method")
st.caption("RRP and cost are pre-filled using hypothetical pipe assumptions. You can manually adjust them. Freight can be calculated or manually overridden per product line.")

package_input = st.data_editor(
    build_default_product_rows(),
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="package_input",
    column_config={
        "Pipe size mm": st.column_config.SelectboxColumn("Pipe size mm", options=PIPE_SIZE_OPTIONS, required=True),
        "Quantity m": st.column_config.NumberColumn("Quantity m", min_value=0.0, step=1.0, format="%.2f"),
        "RRP / m": st.column_config.NumberColumn("Hypothetical RRP / m", min_value=0.0, step=5.0, format="$%.2f"),
        "Cost / m": st.column_config.NumberColumn("Hypothetical Cost / m", min_value=0.0, step=5.0, format="$%.2f"),
        "Freight method": st.column_config.SelectboxColumn("Freight method", options=["Internal fleet", "Line haul"]),
        "Zone": st.column_config.SelectboxColumn("Zone", options=list(ZONE_KM.keys())),
        "km one-way": st.column_config.NumberColumn("km one-way", min_value=0.0, step=5.0),
        "Trip": st.column_config.SelectboxColumn("Trip", options=["One-way", "Return"]),
        "Fleet": st.column_config.SelectboxColumn("Fleet", options=list(FLEET_OPTIONS.keys())),
        "Site hrs": st.column_config.NumberColumn("Site hrs", min_value=0.0, step=0.5, format="%.2f"),
        "Wide load": st.column_config.CheckboxColumn("Wide load"),
        "Line haul": st.column_config.SelectboxColumn("Line haul", options=list(LINE_HAUL_OPTIONS.keys())),
        "Line haul km": st.column_config.NumberColumn("Line haul km", min_value=0.0, step=10.0),
        "Manual freight override": st.column_config.NumberColumn("Manual freight override", min_value=0.0, step=50.0, format="$%.2f", help="Leave as 0 to use calculated freight."),
    },
)

st.markdown("</div>", unsafe_allow_html=True)

clean_input = clean_package_input(package_input)
if clean_input.empty:
    st.info("Enter at least one product line with quantity greater than zero.")
    st.stop()

freight_input = add_calculated_freight(
    clean_input,
    driver_rate_per_hr=driver_rate,
    diesel_price=diesel_price,
    avg_kmh=avg_kmh,
    wide_load_kmh=wide_load_kmh,
    fuel_levy_pct=fuel_levy_pct,
    permit_cost=permit_cost,
)


# =========================================================
# Freight Preview
# =========================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Freight Preview")
st.caption("Calculated using the VIC/TAS freight logic. Manual override replaces the calculated freight where entered.")

freight_preview_cols = [
    "Pipe size mm", "Quantity m", "Freight method", "Zone", "km one-way", "Trip", "Fleet", "Line haul", "Line haul km", "Manual freight override", "Calculated freight"
]

st.dataframe(
    freight_input[freight_preview_cols].style.format({
        "Quantity m": "{:,.2f}",
        "km one-way": "{:,.0f}",
        "Line haul km": "{:,.0f}",
        "Manual freight override": "${:,.0f}",
        "Calculated freight": "${:,.0f}",
    }),
    use_container_width=True,
    hide_index=True,
)
st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Step 2: Discount
# =========================================================

discount_df = freight_input.copy()
discount_df["Discount %"] = 0.0

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Step 2 — Apply Product-Level Discount")
st.caption("Only the discount column is editable here. The package margin updates instantly below.")

discount_input = st.data_editor(
    discount_df[["Pipe size mm", "Quantity m", "RRP / m", "Cost / m", "Calculated freight", "Discount %"]],
    use_container_width=True,
    hide_index=True,
    key="discount_input",
    disabled=["Pipe size mm", "Quantity m", "RRP / m", "Cost / m", "Calculated freight"],
    column_config={
        "Pipe size mm": st.column_config.NumberColumn("Pipe size mm", format="%d"),
        "Quantity m": st.column_config.NumberColumn("Quantity m", format="%.2f"),
        "RRP / m": st.column_config.NumberColumn("RRP / m", format="$%.2f"),
        "Cost / m": st.column_config.NumberColumn("Cost / m", format="$%.2f"),
        "Calculated freight": st.column_config.NumberColumn("Freight", format="$%.2f"),
        "Discount %": st.column_config.NumberColumn("Discount %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f%%"),
    },
)

# Bring back fields removed from discount editor.
discount_input = discount_input.merge(
    freight_input.drop(columns=["Pipe size mm", "Quantity m", "RRP / m", "Cost / m", "Calculated freight"], errors="ignore"),
    left_index=True,
    right_index=True,
    how="left",
)
discount_input["Calculated freight"] = freight_input["Calculated freight"].values

st.markdown("</div>", unsafe_allow_html=True)

product_lines = calculate_product_lines(discount_input)


# =========================================================
# Package Summary
# =========================================================

total_quantity = product_lines["Quantity m"].sum()
total_rrp_revenue = product_lines["RRP revenue"].sum()
total_revenue = product_lines["Revenue"].sum()
total_freight = product_lines["Freight cost"].sum()
total_cost = product_lines["Total cost incl. freight"].sum()
total_contribution = product_lines["Contribution $"].sum()
package_margin = safe_divide(total_contribution, total_revenue)
rrp_contribution = product_lines["RRP contribution $"].sum()
rrp_margin = safe_divide(rrp_contribution, total_rrp_revenue)
margin_lost_dollars = rrp_contribution - total_contribution
margin_lost_pp = (rrp_margin - package_margin) * 100
weighted_discount = safe_divide(total_rrp_revenue - total_revenue, total_rrp_revenue)
status_label, status_colour = margin_status(package_margin)

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Executive Package Summary")

k1, k2, k3, k4 = st.columns(4)
k1.metric("RRP revenue", money(total_rrp_revenue))
k2.metric("Discounted revenue", money(total_revenue))
k3.metric("Freight cost", money(total_freight))
k4.metric("Contribution margin", percent(package_margin))

k5, k6, k7, k8 = st.columns(4)
k5.metric("Weighted discount", percent(weighted_discount))
k6.metric("Contribution $", money(total_contribution))
k7.metric("Margin at risk", money(margin_lost_dollars))
k8.metric("Margin lost", f"{margin_lost_pp:.1f} pts")

st.markdown(
    f"""
    <div class="mini-card" style="background:{status_colour}; margin-top:10px;">
        <b>{status_label}</b><br>
        <span class="muted">
            At RRP, package contribution margin is {rrp_margin:.1%}. After discounts and freight, contribution margin is {package_margin:.1%}.
            Current discounting places {money(margin_lost_dollars)} of contribution at risk.
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Product Line Output
# =========================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Product Line Margin Detail")

line_cols = [
    "Pipe size mm", "Quantity m", "RRP / m", "Discount %", "Net sell price / m", "Cost / m", "Freight cost", "Revenue", "Product cost", "Total cost incl. freight", "Contribution $", "Contribution margin %", "Margin lost $", "Margin lost percentage points"
]

st.dataframe(
    product_lines[line_cols].style.format({
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
    }),
    use_container_width=True,
    hide_index=True,
)
st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Competitor Freight Assumptions and Peer Comparison
# =========================================================

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Step 3 — Competitor Freight Assumptions")
st.caption("Hypothetical competitor freight is pre-filled using Atlan freight. You can manually adjust by competitor.")

competitor_assumptions = st.data_editor(
    build_competitor_freight_defaults(total_freight),
    use_container_width=True,
    hide_index=True,
    key="competitor_freight",
    disabled=["Peer", "Pricing position"],
    column_config={
        "Price factor": st.column_config.NumberColumn("Price factor", min_value=0.0, step=0.01, format="%.2f"),
        "Competitor freight": st.column_config.NumberColumn("Competitor freight", min_value=0.0, step=50.0, format="$%.2f"),
    },
)

peer_df = build_peer_comparison(product_lines, competitor_assumptions, region_key)
peer_avg = peer_df["Total package"].mean()
gap_vs_peer_avg = safe_divide(total_revenue - peer_avg, peer_avg)

atlan_row = pd.DataFrame([
    {
        "Peer": "Atlan proposed package",
        "Pricing position": "Current quote",
        "Product revenue": total_revenue - total_freight,
        "Freight": total_freight,
        "Total package": total_revenue,
        "Avg package price / m": safe_divide(total_revenue, total_quantity),
    }
])

peer_display = pd.concat([peer_df, atlan_row], ignore_index=True).sort_values("Total package").reset_index(drop=True)

st.markdown("### Peer Landed Package Comparison")
st.dataframe(
    peer_display.style.format({
        "Product revenue": "${:,.0f}",
        "Freight": "${:,.0f}",
        "Total package": "${:,.0f}",
        "Avg package price / m": "${:,.2f}",
    }),
    use_container_width=True,
    hide_index=True,
)

readout = recommendation(package_margin, gap_vs_peer_avg, weighted_discount)
if package_margin < risk_margin:
    st.error(readout)
elif package_margin < target_margin:
    st.warning(readout)
else:
    st.success(readout)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Reference Tables
# =========================================================

with st.expander("Freight reference tables"):
    fleet_ref = pd.DataFrame([
        {
            "Fleet": f.name,
            "Deck": f"{f.deck_width_m} × {f.deck_length_m}",
            "Max length": f.max_length_m,
            "Payload t": f.payload_t,
            "L/100km": f.litres_per_100km,
            "Maint $/km": f.maintenance_per_km,
            "Fuel $/km": f.litres_per_100km / 100 * diesel_price,
            "Total $/km": calculate_fleet_cost_per_km(f, diesel_price),
            "Pallets": f.pallets,
        }
        for f in FLEET_OPTIONS.values()
    ])
    st.dataframe(fleet_ref.style.format({"Maint $/km": "${:.2f}", "Fuel $/km": "${:.2f}", "Total $/km": "${:.2f}"}), use_container_width=True, hide_index=True)

    zone_ref = pd.DataFrame([{"Zone": k, "Preset km one-way": v} for k, v in ZONE_KM.items()])
    st.dataframe(zone_ref, use_container_width=True, hide_index=True)


# =========================================================
# Download
# =========================================================

csv = product_lines.to_csv(index=False)
st.download_button(
    label="Download Pricing Output CSV",
    data=csv,
    file_name="atlan_package_pricing_output.csv",
    mime="text/csv",
    use_container_width=True,
)
