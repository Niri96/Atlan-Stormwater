from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
import streamlit as st


# =========================================================
# DATA MODELS
# =========================================================

@dataclass(frozen=True)
class RegionProfile:
    key: str
    name: str
    market_pressure: float
    notes: str


@dataclass(frozen=True)
class FleetProfile:
    name: str
    max_length_m: float
    payload_t: float
    litres_per_100km: float
    maintenance_per_km: float


@dataclass(frozen=True)
class Competitor:
    name: str
    positioning: str
    price_factor: float


# =========================================================
# ASSUMPTIONS
# =========================================================

ATLAN_BLUE = "#0B5CFF"
ATLAN_DARK = "#071B3A"

REGIONS: Dict[str, RegionProfile] = {
    "VIC": RegionProfile("VIC", "Victoria", 1.00, "Balanced market with room for value-led pricing."),
    "QLD": RegionProfile("QLD", "Queensland", 0.95, "Competitive pipe market with strong pricing pressure."),
    "NSW": RegionProfile("NSW", "New South Wales", 0.97, "High-volume market with active peer competition."),
    "WA": RegionProfile("WA", "Western Australia", 1.05, "Higher freight exposure and regional supply cost."),
    "SA": RegionProfile("SA", "South Australia", 1.02, "Moderate pricing pressure with freight sensitivity."),
}

COMPETITORS: List[Competitor] = [
    Competitor("Competitor A", "Aggressive / low-cost", 0.88),
    Competitor("Competitor B", "Market average", 1.00),
    Competitor("Competitor C", "Premium supplier", 1.16),
    Competitor("Competitor D", "Regional player", 0.96),
    Competitor("Competitor E", "Import / price-led", 0.82),
]

PIPE_RRP: Dict[int, float] = {
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

PIPE_COST: Dict[int, float] = {
    size: round(rrp * 0.65, 2) for size, rrp in PIPE_RRP.items()
}

PIPE_LENGTH: Dict[int, float] = {
    225: 2.4,
    300: 2.4,
    375: 2.4,
    450: 2.4,
    525: 2.4,
    600: 2.4,
    750: 2.4,
    900: 2.4,
    1050: 2.4,
    1200: 2.4,
}

FLEET: Dict[str, FleetProfile] = {
    "Ute": FleetProfile("Ute", 1.7, 0.5, 12, 0.10),
    "Ute + trailer": FleetProfile("Ute + trailer", 6.7, 3.2, 16, 0.14),
    "6.5m truck": FleetProfile("6.5m truck", 6.7, 4.0, 20, 0.18),
    "6.5m truck + trailer": FleetProfile("6.5m truck + trailer", 13.4, 7.2, 25, 0.22),
    "8m truck": FleetProfile("8m truck", 7.9, 8.0, 30, 0.22),
    "8m truck + trailer": FleetProfile("8m truck + trailer", 14.6, 11.2, 35, 0.28),
}

ZONES = {
    "Metro": 30,
    "Outer Metro": 60,
    "Regional": 150,
    "Remote": 350,
    "TAS": 600,
}

DISCOUNT_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]


# =========================================================
# HELPERS
# =========================================================

def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def safe_divide(a: float, b: float) -> float:
    return a / b if b else 0.0


def calculate_internal_freight(
    fleet_name: str,
    km_one_way: float,
    driver_rate: float,
    diesel_price: float,
    avg_speed: float,
    site_hours: float,
    trip_type: str,
) -> float:
    fleet = FLEET[fleet_name]

    km_total = km_one_way * 2 if trip_type == "Return" else km_one_way

    fuel_per_km = fleet.litres_per_100km / 100 * diesel_price
    vehicle_cost_per_km = fuel_per_km + fleet.maintenance_per_km

    drive_hours = safe_divide(km_total, avg_speed)
    labour_cost = (drive_hours + site_hours) * driver_rate
    vehicle_cost = km_total * vehicle_cost_per_km

    return labour_cost + vehicle_cost


def add_product_line() -> None:
    line_id = len(st.session_state.product_lines) + 1

    st.session_state.product_lines.append(
        {
            "id": line_id,
            "pipe_size": 375,
            "quantity_m": 100.0,
            "discount_pct": 0,
            "freight_method": "Auto calculate",
            "zone": "Metro",
            "km_one_way": 30.0,
            "trip_type": "Return",
            "fleet": "6.5m truck",
            "site_hours": 1.0,
            "manual_freight": 0.0,
        }
    )


def remove_product_line(line_id: int) -> None:
    st.session_state.product_lines = [
        line for line in st.session_state.product_lines if line["id"] != line_id
    ]


def calculate_line(line: dict, global_inputs: dict) -> dict:
    pipe_size = line["pipe_size"]
    quantity_m = line["quantity_m"]
    rrp_per_m = PIPE_RRP[pipe_size]
    cost_per_m = PIPE_COST[pipe_size]
    discount_pct = line["discount_pct"]

    net_price_per_m = rrp_per_m * (1 - discount_pct / 100)
    rrp_revenue = rrp_per_m * quantity_m
    revenue = net_price_per_m * quantity_m
    product_cost = cost_per_m * quantity_m

    if line["freight_method"] == "Manual override":
        freight_cost = line["manual_freight"]
    else:
        freight_cost = calculate_internal_freight(
            fleet_name=line["fleet"],
            km_one_way=line["km_one_way"],
            driver_rate=global_inputs["driver_rate"],
            diesel_price=global_inputs["diesel_price"],
            avg_speed=global_inputs["avg_speed"],
            site_hours=line["site_hours"],
            trip_type=line["trip_type"],
        )

    total_cost = product_cost + freight_cost
    contribution = revenue - total_cost
    contribution_margin = safe_divide(contribution, revenue)

    rrp_contribution = rrp_revenue - total_cost
    rrp_margin = safe_divide(rrp_contribution, rrp_revenue)

    margin_lost = rrp_contribution - contribution
    margin_lost_pp = (rrp_margin - contribution_margin) * 100

    return {
        "Pipe size": f"{pipe_size}mm",
        "Quantity m": quantity_m,
        "RRP / m": rrp_per_m,
        "Discount %": discount_pct,
        "Net price / m": net_price_per_m,
        "Cost / m": cost_per_m,
        "Product revenue": revenue,
        "Product cost": product_cost,
        "Freight cost": freight_cost,
        "Total cost": total_cost,
        "Contribution $": contribution,
        "Contribution margin %": contribution_margin,
        "RRP contribution $": rrp_contribution,
        "RRP margin %": rrp_margin,
        "Margin lost $": margin_lost,
        "Margin lost pp": margin_lost_pp,
    }


def build_peer_comparison(total_revenue: float, total_quantity: float, total_freight: float, region_key: str) -> pd.DataFrame:
    region = REGIONS[region_key]

    rows = []

    avg_price_per_m = safe_divide(total_revenue, total_quantity)

    for competitor in COMPETITORS:
        peer_revenue = total_quantity * avg_price_per_m * competitor.price_factor * region.market_pressure

        rows.append(
            {
                "Supplier": competitor.name,
                "Positioning": competitor.positioning,
                "Estimated Package": peer_revenue,
                "Freight Assumption": total_freight,
                "Average $ / m": safe_divide(peer_revenue, total_quantity),
            }
        )

    rows.append(
        {
            "Supplier": "Atlan Proposed Package",
            "Positioning": "Current quote",
            "Estimated Package": total_revenue,
            "Freight Assumption": total_freight,
            "Average $ / m": safe_divide(total_revenue, total_quantity),
        }
    )

    return pd.DataFrame(rows).sort_values("Estimated Package")


# =========================================================
# PAGE SETUP
# =========================================================

st.set_page_config(
    page_title="Atlan Pricing Engine",
    page_icon="💧",
    layout="wide",
)

st.markdown(
    f"""
    <style>
        .stApp {{
            background: #F4F7FB;
        }}

        .block-container {{
            max-width: 1380px;
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }}

        .hero {{
            background: linear-gradient(135deg, #071B3A 0%, #0B5CFF 100%);
            padding: 34px 38px;
            border-radius: 28px;
            color: white;
            box-shadow: 0 22px 50px rgba(7,27,58,0.22);
            margin-bottom: 26px;
        }}

        .hero h1 {{
            font-size: 40px;
            line-height: 1.1;
            margin-bottom: 10px;
            font-weight: 850;
        }}

        .hero p {{
            font-size: 17px;
            opacity: 0.92;
            max-width: 900px;
        }}

        .card {{
            background: white;
            border: 1px solid rgba(7,27,58,0.08);
            border-radius: 24px;
            padding: 24px;
            box-shadow: 0 10px 30px rgba(7,27,58,0.06);
            margin-bottom: 20px;
        }}

        .mini-card {{
            background: white;
            border: 1px solid rgba(7,27,58,0.08);
            border-radius: 20px;
            padding: 18px;
            box-shadow: 0 8px 24px rgba(7,27,58,0.05);
        }}

        .line-title {{
            font-size: 19px;
            font-weight: 800;
            color: #071B3A;
            margin-bottom: 6px;
        }}

        .subtle {{
            color: rgba(7,27,58,0.62);
            font-size: 14px;
        }}

        .risk-card {{
            border-radius: 22px;
            padding: 22px;
            margin-top: 16px;
            border: 1px solid rgba(7,27,58,0.08);
        }}

        .risk-good {{
            background: #ECFDF3;
        }}

        .risk-watch {{
            background: #FFF7E6;
        }}

        .risk-bad {{
            background: #FFF1F1;
        }}

        section[data-testid="stSidebar"] {{
            background: #FFFFFF;
            border-right: 1px solid rgba(7,27,58,0.08);
        }}

        [data-testid="stMetricValue"] {{
            color: #071B3A;
            font-weight: 850;
        }}

        [data-testid="stMetricLabel"] {{
            color: rgba(7,27,58,0.68);
        }}

        div.stButton > button {{
            border-radius: 14px;
            font-weight: 750;
        }}

        div.stButton > button[kind="primary"] {{
            background: #0B5CFF;
            border-color: #0B5CFF;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SESSION STATE
# =========================================================

if "product_lines" not in st.session_state:
    st.session_state.product_lines = []
    add_product_line()


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="hero">
        <h1>Atlan Stormwater Pricing Engine</h1>
        <p>
            Build a package quote, apply controlled discounting, calculate freight at line level,
            and see live contribution margin risk against peer pricing.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown("## Global Freight Assumptions")

    driver_rate = st.number_input("Driver $/hr", min_value=0.0, value=100.0, step=5.0)
    diesel_price = st.number_input("Diesel $/L", min_value=0.0, value=3.00, step=0.10)
    avg_speed = st.number_input("Average km/h", min_value=1.0, value=60.0, step=5.0)

    st.divider()

    st.markdown("## Commercial Guardrails")

    target_margin = st.slider("Target contribution margin", 0, 70, 35, 1) / 100
    risk_margin = st.slider("High-risk margin threshold", 0, 50, 25, 1) / 100

    st.divider()

    region_key = st.selectbox(
        "Peer comparison region",
        list(REGIONS.keys()),
        format_func=lambda x: REGIONS[x].name,
    )


global_inputs = {
    "driver_rate": driver_rate,
    "diesel_price": diesel_price,
    "avg_speed": avg_speed,
}


# =========================================================
# PRODUCT CARDS
# =========================================================

top_col_1, top_col_2 = st.columns([0.78, 0.22])

with top_col_1:
    st.markdown("## Package Builder")
    st.caption("Add each product as a quote card. Discount and freight are calculated line by line.")

with top_col_2:
    if st.button("+ Add product line", type="primary", use_container_width=True):
        add_product_line()
        st.rerun()


calculated_rows = []

for line in list(st.session_state.product_lines):
    st.markdown('<div class="card">', unsafe_allow_html=True)

    header_col, remove_col = st.columns([0.86, 0.14])

    with header_col:
        st.markdown(
            f"""
            <div class="line-title">Product Line {line["id"]}</div>
            <div class="subtle">Select product, apply discount, and choose freight method.</div>
            """,
            unsafe_allow_html=True,
        )

    with remove_col:
        if len(st.session_state.product_lines) > 1:
            if st.button("Remove", key=f"remove_{line['id']}", use_container_width=True):
                remove_product_line(line["id"])
                st.rerun()

    st.divider()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        line["pipe_size"] = st.selectbox(
            "Pipe size",
            list(PIPE_RRP.keys()),
            index=list(PIPE_RRP.keys()).index(line["pipe_size"]),
            key=f"pipe_size_{line['id']}",
            format_func=lambda x: f"{x}mm",
        )

    with c2:
        line["quantity_m"] = st.number_input(
            "Quantity / length (m)",
            min_value=0.0,
            value=float(line["quantity_m"]),
            step=10.0,
            key=f"qty_{line['id']}",
        )

    with c3:
        st.metric("Hypothetical RRP / m", f"${PIPE_RRP[line['pipe_size']]:,.2f}")

    with c4:
        st.metric("Hypothetical Cost / m", f"${PIPE_COST[line['pipe_size']]:,.2f}")

    d1, d2, d3 = st.columns([0.28, 0.36, 0.36])

    with d1:
        line["discount_pct"] = st.selectbox(
            "Discount off RRP",
            DISCOUNT_OPTIONS,
            index=DISCOUNT_OPTIONS.index(line["discount_pct"]),
            key=f"discount_{line['id']}",
            format_func=lambda x: f"{x}%",
        )

    with d2:
        line["freight_method"] = st.radio(
            "Freight method",
            ["Auto calculate", "Manual override"],
            horizontal=True,
            key=f"freight_method_{line['id']}",
        )

    with d3:
        line["trip_type"] = st.radio(
            "Trip",
            ["Return", "One-way"],
            horizontal=True,
            key=f"trip_type_{line['id']}",
        )

    if line["freight_method"] == "Auto calculate":
        f1, f2, f3, f4 = st.columns(4)

        with f1:
            line["zone"] = st.selectbox(
                "Delivery zone",
                list(ZONES.keys()),
                index=list(ZONES.keys()).index(line["zone"]),
                key=f"zone_{line['id']}",
            )

            if st.button("Use zone km", key=f"use_zone_{line['id']}", use_container_width=True):
                line["km_one_way"] = float(ZONES[line["zone"]])
                st.rerun()

        with f2:
            line["km_one_way"] = st.number_input(
                "km one-way",
                min_value=0.0,
                value=float(line["km_one_way"]),
                step=10.0,
                key=f"km_{line['id']}",
            )

        with f3:
            line["fleet"] = st.selectbox(
                "Fleet",
                list(FLEET.keys()),
                index=list(FLEET.keys()).index(line["fleet"]),
                key=f"fleet_{line['id']}",
            )

        with f4:
            line["site_hours"] = st.number_input(
                "Site hours",
                min_value=0.0,
                value=float(line["site_hours"]),
                step=0.5,
                key=f"site_hrs_{line['id']}",
            )

    else:
        line["manual_freight"] = st.number_input(
            "Manual freight cost",
            min_value=0.0,
            value=float(line["manual_freight"]),
            step=50.0,
            key=f"manual_freight_{line['id']}",
        )

    result = calculate_line(line, global_inputs)
    calculated_rows.append(result)

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("Net sell price / m", f"${result['Net price / m']:,.2f}")
    with m2:
        st.metric("Revenue", money(result["Product revenue"]))
    with m3:
        st.metric("Freight", money(result["Freight cost"]))
    with m4:
        st.metric("Contribution margin", pct(result["Contribution margin %"]))

    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# CALCULATIONS
# =========================================================

df = pd.DataFrame(calculated_rows)

total_quantity = df["Quantity m"].sum()
total_rrp_revenue = (df["RRP / m"] * df["Quantity m"]).sum()
total_revenue = df["Product revenue"].sum()
total_product_cost = df["Product cost"].sum()
total_freight = df["Freight cost"].sum()
total_cost = df["Total cost"].sum()
total_contribution = df["Contribution $"].sum()

package_margin = safe_divide(total_contribution, total_revenue)

rrp_contribution = df["RRP contribution $"].sum()
rrp_margin = safe_divide(rrp_contribution, total_rrp_revenue)

weighted_discount = safe_divide(total_rrp_revenue - total_revenue, total_rrp_revenue)

margin_lost = rrp_contribution - total_contribution
margin_lost_pp = (rrp_margin - package_margin) * 100


# =========================================================
# EXECUTIVE SUMMARY
# =========================================================

st.markdown("## Executive Package Summary")

st.markdown('<div class="card">', unsafe_allow_html=True)

s1, s2, s3, s4 = st.columns(4)
s1.metric("Discounted revenue", money(total_revenue), delta=f"{pct(weighted_discount)} discount")
s2.metric("Contribution $", money(total_contribution))
s3.metric("Contribution margin", pct(package_margin))
s4.metric("Margin at risk", money(margin_lost), delta=f"{margin_lost_pp:.1f} pts lost")

s5, s6, s7, s8 = st.columns(4)
s5.metric("RRP revenue", money(total_rrp_revenue))
s6.metric("Product cost", money(total_product_cost))
s7.metric("Freight cost", money(total_freight))
s8.metric("Total quantity", f"{total_quantity:,.0f}m")

if package_margin < risk_margin:
    risk_class = "risk-bad"
    risk_title = "High margin risk"
    risk_message = "The package is below the high-risk threshold. Review discounting, cost recovery, or freight recovery before submitting."
elif package_margin < target_margin:
    risk_class = "risk-watch"
    risk_title = "Margin below target"
    risk_message = "The package is above the risk floor, but below the target margin. Consider whether the discount is commercially justified."
else:
    risk_class = "risk-good"
    risk_title = "Healthy package margin"
    risk_message = "The package is above the target contribution margin. Pricing discipline appears intact."

st.markdown(
    f"""
    <div class="risk-card {risk_class}">
        <h3 style="margin:0 0 8px 0; color:#071B3A;">{risk_title}</h3>
        <div style="color:rgba(7,27,58,0.75); font-size:15px;">
            {risk_message}<br><br>
            At RRP, the package margin would be <b>{rrp_margin:.1%}</b>.
            After discounting, it is <b>{package_margin:.1%}</b>.
            Discounting has put <b>{money(margin_lost)}</b> of contribution margin at risk.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# PEER COMPARISON
# =========================================================

peer_df = build_peer_comparison(total_revenue, total_quantity, total_freight, region_key)

st.markdown("## Peer Package Comparison")
st.markdown('<div class="card">', unsafe_allow_html=True)

st.dataframe(
    peer_df.style.format(
        {
            "Estimated Package": "${:,.0f}",
            "Freight Assumption": "${:,.0f}",
            "Average $ / m": "${:,.2f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.caption(REGIONS[region_key].notes)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# LINE DETAIL
# =========================================================

with st.expander("View detailed product line output"):
    display_df = df.copy()

    st.dataframe(
        display_df.style.format(
            {
                "Quantity m": "{:,.0f}",
                "RRP / m": "${:,.2f}",
                "Discount %": "{:.0f}%",
                "Net price / m": "${:,.2f}",
                "Cost / m": "${:,.2f}",
                "Product revenue": "${:,.0f}",
                "Product cost": "${:,.0f}",
                "Freight cost": "${:,.0f}",
                "Total cost": "${:,.0f}",
                "Contribution $": "${:,.0f}",
                "Contribution margin %": "{:.1%}",
                "RRP contribution $": "${:,.0f}",
                "RRP margin %": "{:.1%}",
                "Margin lost $": "${:,.0f}",
                "Margin lost pp": "{:.1f} pts",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# DOWNLOAD
# =========================================================

csv = df.to_csv(index=False)

st.download_button(
    label="Download quote analysis",
    data=csv,
    file_name="atlan_package_pricing_output.csv",
    mime="text/csv",
    use_container_width=True,
)
