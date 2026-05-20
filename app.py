from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
import streamlit as st


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Atlan Pricing Engine",
    page_icon="💧",
    layout="wide",
)


# =========================================================
# DATA MODELS
# =========================================================

@dataclass(frozen=True)
class Region:
    name: str
    market_factor: float
    freight_factor: float
    notes: str


@dataclass(frozen=True)
class Competitor:
    name: str
    positioning: str
    price_factor: float
    default_freight_factor: float


@dataclass(frozen=True)
class Fleet:
    name: str
    litres_per_100km: float
    maintenance_per_km: float


# =========================================================
# ASSUMPTIONS
# =========================================================

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

DISCOUNT_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]

REGIONS: Dict[str, Region] = {
    "VIC": Region("Victoria", 1.00, 1.00, "Balanced market with room for value-led pricing."),
    "QLD": Region("Queensland", 0.95, 1.05, "Competitive market with stronger price pressure."),
    "NSW": Region("New South Wales", 0.97, 1.10, "High-volume market with active peer competition."),
    "WA": Region("Western Australia", 1.05, 1.18, "Higher freight exposure and supply cost."),
    "SA": Region("South Australia", 1.02, 1.12, "Moderate pricing pressure with freight sensitivity."),
    "TAS": Region("Tasmania", 1.06, 1.30, "Freight-sensitive market with additional delivery complexity."),
}

COMPETITORS: List[Competitor] = [
    Competitor("Competitor A", "Aggressive / low-cost", 0.88, 0.95),
    Competitor("Competitor B", "Market average", 1.00, 1.00),
    Competitor("Competitor C", "Premium supplier", 1.16, 1.10),
    Competitor("Competitor D", "Regional player", 0.96, 0.90),
    Competitor("Competitor E", "Import / price-led", 0.82, 1.15),
]

FLEET: Dict[str, Fleet] = {
    "Ute": Fleet("Ute", 12, 0.10),
    "Ute + trailer": Fleet("Ute + trailer", 16, 0.14),
    "6.5m truck": Fleet("6.5m truck", 20, 0.18),
    "6.5m truck + trailer": Fleet("6.5m truck + trailer", 25, 0.22),
    "8m truck": Fleet("8m truck", 30, 0.22),
    "8m truck + trailer": Fleet("8m truck + trailer", 35, 0.28),
}

ZONES = {
    "Metro": 30,
    "Outer Metro": 60,
    "Regional": 150,
    "Remote": 350,
    "TAS": 600,
}


# =========================================================
# STYLE
# =========================================================

st.markdown(
    """
<style>

.stApp {
    background: #F4F7FB;
}

.block-container {
    max-width: 1450px;
    padding-top: 0.8rem;
    padding-bottom: 1rem;
}

/* =========================================
HERO
========================================= */

.hero {
    background: linear-gradient(135deg, #071B3A 0%, #0B5CFF 100%);
    padding: 22px 26px;
    border-radius: 22px;
    color: white;
    box-shadow: 0 14px 34px rgba(7,27,58,0.18);
    margin-bottom: 16px;
}

.hero h1 {
    font-size: 28px;
    margin-bottom: 4px;
    font-weight: 850;
    line-height: 1.1;
}

.hero p {
    font-size: 13px;
    opacity: 0.90;
    margin-bottom: 0;
    line-height: 1.4;
}

/* =========================================
CARDS
========================================= */

.card {
    background: white;
    border: 1px solid rgba(7,27,58,0.06);
    border-radius: 18px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 6px 18px rgba(7,27,58,0.04);
}

.small-card {
    background: white;
    border-radius: 16px;
    padding: 14px;
    border: 1px solid rgba(7,27,58,0.06);
}

/* =========================================
TEXT
========================================= */

.title {
    font-size: 17px;
    font-weight: 800;
    color: #071B3A;
    margin-bottom: 2px;
}

.subtle {
    color: rgba(7,27,58,0.60);
    font-size: 11px;
    line-height: 1.3;
}

/* =========================================
RISK
========================================= */

.good {
    background: #ECFDF3;
}

.watch {
    background: #FFF7E6;
}

.bad {
    background: #FFF1F1;
}

.risk-box {
    border-radius: 16px;
    padding: 14px 16px;
    margin-top: 12px;
    border: 1px solid rgba(7,27,58,0.08);
    font-size: 12px;
}

/* =========================================
METRICS
========================================= */

[data-testid="stMetric"] {
    background: white;
    border-radius: 14px;
    padding: 10px 12px;
    border: 1px solid rgba(7,27,58,0.06);
    box-shadow: 0 4px 12px rgba(7,27,58,0.03);
}

[data-testid="stMetricLabel"] {
    font-size: 11px;
    color: rgba(7,27,58,0.62);
}

[data-testid="stMetricValue"] {
    font-size: 22px;
    font-weight: 850;
    color: #071B3A;
}

[data-testid="stMetricDelta"] {
    font-size: 11px;
}

/* =========================================
INPUTS
========================================= */

.stSelectbox label,
.stNumberInput label,
.stRadio label {
    font-size: 11px !important;
    font-weight: 650 !important;
}

.stTextInput input,
.stNumberInput input {
    font-size: 12px !important;
}

.stSelectbox div[data-baseweb="select"] {
    min-height: 34px;
}

/* =========================================
BUTTONS
========================================= */

div.stButton > button {
    border-radius: 10px;
    font-weight: 700;
    font-size: 12px;
    padding: 0.35rem 0.8rem;
}

div.stButton > button[kind="primary"] {
    background: #0B5CFF;
    border-color: #0B5CFF;
}

/* =========================================
SIDEBAR
========================================= */

section[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid rgba(7,27,58,0.08);
}

/* =========================================
DATAFRAMES
========================================= */

[data-testid="stDataFrame"] {
    font-size: 11px;
}

/* =========================================
EXPANDER
========================================= */

.streamlit-expanderHeader {
    font-size: 13px !important;
    font-weight: 700 !important;
}

</style>
""",
    unsafe_allow_html=True,
)
# =========================================================
# HELPERS
# =========================================================

def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def safe_divide(a: float, b: float) -> float:
    return a / b if b else 0.0


def calculate_freight(
    fleet_name: str,
    km_one_way: float,
    driver_rate: float,
    diesel_price: float,
    avg_speed: float,
    site_hours: float,
    trip_type: str,
    region_key: str,
) -> float:
    fleet = FLEET[fleet_name]
    region = REGIONS[region_key]

    total_km = km_one_way if trip_type == "One-way" else km_one_way * 2
    fuel_per_km = fleet.litres_per_100km / 100 * diesel_price
    vehicle_cost_per_km = fuel_per_km + fleet.maintenance_per_km

    drive_hours = safe_divide(total_km, avg_speed)
    labour_cost = (drive_hours + site_hours) * driver_rate
    vehicle_cost = total_km * vehicle_cost_per_km

    return (labour_cost + vehicle_cost) * region.freight_factor


def add_delivery() -> None:
    new_id = st.session_state.next_delivery_id
    st.session_state.next_delivery_id += 1

    st.session_state.deliveries.append(
        {
            "id": new_id,
            "products": [
                {
                    "pipe_size": 375,
                    "quantity_m": 100.0,
                    "discount_pct": 0,
                }
            ],
            "freight_method": "Auto calculate",
            "zone": "Metro",
            "km_one_way": 30.0,
            "trip_type": "Return",
            "fleet": "6.5m truck",
            "site_hours": 1.0,
            "manual_freight": 0.0,
        }
    )


def remove_delivery(delivery_id: int) -> None:
    st.session_state.deliveries = [
        d for d in st.session_state.deliveries if d["id"] != delivery_id
    ]


def add_product_to_delivery(delivery_id: int) -> None:
    for delivery in st.session_state.deliveries:
        if delivery["id"] == delivery_id:
            delivery["products"].append(
                {
                    "pipe_size": 375,
                    "quantity_m": 100.0,
                    "discount_pct": 0,
                }
            )
            break


def remove_product_from_delivery(delivery_id: int, product_index: int) -> None:
    for delivery in st.session_state.deliveries:
        if delivery["id"] == delivery_id:
            if len(delivery["products"]) > 1:
                delivery["products"].pop(product_index)
            break


def calculate_delivery(delivery: dict, global_inputs: dict, region_key: str) -> tuple[list[dict], float]:
    if delivery["freight_method"] == "Manual override":
        delivery_freight = delivery["manual_freight"]
    else:
        delivery_freight = calculate_freight(
            fleet_name=delivery["fleet"],
            km_one_way=delivery["km_one_way"],
            driver_rate=global_inputs["driver_rate"],
            diesel_price=global_inputs["diesel_price"],
            avg_speed=global_inputs["avg_speed"],
            site_hours=delivery["site_hours"],
            trip_type=delivery["trip_type"],
            region_key=region_key,
        )

    total_delivery_revenue_before_freight = 0.0
    temp_rows = []

    for product in delivery["products"]:
        pipe_size = product["pipe_size"]
        quantity_m = product["quantity_m"]
        discount_pct = product["discount_pct"]

        rrp_per_m = PIPE_RRP[pipe_size]
        cost_per_m = PIPE_COST[pipe_size]
        net_price_per_m = rrp_per_m * (1 - discount_pct / 100)

        rrp_revenue = rrp_per_m * quantity_m
        revenue = net_price_per_m * quantity_m
        product_cost = cost_per_m * quantity_m

        total_delivery_revenue_before_freight += revenue

        temp_rows.append(
            {
                "Delivery": f"Delivery {delivery['id']}",
                "Pipe Size": f"{pipe_size}mm",
                "Quantity m": quantity_m,
                "RRP / m": rrp_per_m,
                "Discount %": discount_pct,
                "Net Price / m": net_price_per_m,
                "RRP Revenue": rrp_revenue,
                "Revenue": revenue,
                "Product Cost": product_cost,
            }
        )

    final_rows = []

    for row in temp_rows:
        allocation_pct = safe_divide(row["Revenue"], total_delivery_revenue_before_freight)
        freight_allocated = delivery_freight * allocation_pct

        total_cost = row["Product Cost"] + freight_allocated
        contribution = row["Revenue"] - total_cost
        contribution_margin = safe_divide(contribution, row["Revenue"])

        rrp_contribution = row["RRP Revenue"] - total_cost
        rrp_margin = safe_divide(rrp_contribution, row["RRP Revenue"])

        margin_lost = rrp_contribution - contribution
        margin_lost_pp = (rrp_margin - contribution_margin) * 100

        row.update(
            {
                "Freight Allocated": freight_allocated,
                "Total Cost": total_cost,
                "Contribution $": contribution,
                "Contribution Margin %": contribution_margin,
                "RRP Contribution $": rrp_contribution,
                "RRP Margin %": rrp_margin,
                "Margin Lost $": margin_lost,
                "Margin Lost pp": margin_lost_pp,
            }
        )

        final_rows.append(row)

    return final_rows, delivery_freight


def build_peer_comparison(
    detail_df: pd.DataFrame,
    peer_freight: Dict[str, float],
    region_key: str,
    total_revenue: float,
    total_freight: float,
) -> pd.DataFrame:
    region = REGIONS[region_key]

    rows = []

    for competitor in COMPETITORS:
        product_revenue = 0.0

        for _, row in detail_df.iterrows():
            product_revenue += (
                row["RRP / m"]
                * row["Quantity m"]
                * competitor.price_factor
                * region.market_factor
            )

        freight = peer_freight.get(competitor.name, 0.0)
        total_package = product_revenue + freight

        rows.append(
            {
                "Supplier": competitor.name,
                "Positioning": competitor.positioning,
                "Product Package": product_revenue,
                "Peer Freight": freight,
                "Total Package": total_package,
                "Average $ / m": safe_divide(total_package, detail_df["Quantity m"].sum()),
            }
        )

    rows.append(
        {
            "Supplier": "Atlan Proposed Package",
            "Positioning": "Current quote",
            "Product Package": total_revenue,
            "Peer Freight": total_freight,
            "Total Package": total_revenue,
            "Average $ / m": safe_divide(total_revenue, detail_df["Quantity m"].sum()),
        }
    )

    return pd.DataFrame(rows).sort_values("Total Package").reset_index(drop=True)


# =========================================================
# SESSION STATE
# =========================================================

if "deliveries" not in st.session_state:
    st.session_state.deliveries = []

if "next_delivery_id" not in st.session_state:
    st.session_state.next_delivery_id = 1

if not st.session_state.deliveries:
    add_delivery()


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
<div class="hero">
    <h1>Atlan Stormwater Pricing Engine</h1>
    <p>
        Build a multi-delivery pipe package, apply controlled discounts, calculate freight by delivery,
        and compare Atlan’s total package against peers with editable freight assumptions.
    </p>
</div>
""",
    unsafe_allow_html=True,
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown("## Market & Region")

    region_key = st.selectbox(
        "Region",
        list(REGIONS.keys()),
        format_func=lambda x: REGIONS[x].name,
    )

    st.caption(REGIONS[region_key].notes)

    st.divider()

    st.markdown("## Global Freight Inputs")

    driver_rate = st.number_input("Driver $ / hr", min_value=0.0, value=100.0, step=5.0)
    diesel_price = st.number_input("Diesel $ / L", min_value=0.0, value=3.00, step=0.10)
    avg_speed = st.number_input("Average km / h", min_value=1.0, value=60.0, step=5.0)

    st.divider()

    st.markdown("## Commercial Guardrails")

    target_margin = st.slider("Target contribution margin %", 0, 70, 35, 1) / 100
    risk_margin = st.slider("High-risk margin threshold %", 0, 50, 25, 1) / 100


global_inputs = {
    "driver_rate": driver_rate,
    "diesel_price": diesel_price,
    "avg_speed": avg_speed,
}


# =========================================================
# PACKAGE BUILDER
# =========================================================

top_left, top_right = st.columns([0.78, 0.22])

with top_left:
    st.markdown("## Package Builder")
    st.caption("Each delivery can include multiple pipe sizes. Freight is calculated at delivery level and allocated across products.")

with top_right:
    if st.button("+ Add Delivery", type="primary", use_container_width=True):
        add_delivery()
        st.rerun()


all_rows = []
delivery_summary_rows = []

for delivery in list(st.session_state.deliveries):
    st.markdown('<div class="card">', unsafe_allow_html=True)

    h1, h2 = st.columns([0.82, 0.18])

    with h1:
        st.markdown(f'<div class="title">Delivery {delivery["id"]}</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtle">Add one or more pipe sizes for this delivery.</div>', unsafe_allow_html=True)

    with h2:
        if len(st.session_state.deliveries) > 1:
            if st.button("Remove Delivery", key=f"remove_delivery_{delivery['id']}", use_container_width=True):
                remove_delivery(delivery["id"])
                st.rerun()

    st.divider()

    for idx, product in enumerate(list(delivery["products"])):
        p1, p2, p3, p4, p5 = st.columns([0.22, 0.20, 0.18, 0.18, 0.22])

        with p1:
            product["pipe_size"] = st.selectbox(
                "Pipe Size",
                list(PIPE_RRP.keys()),
                index=list(PIPE_RRP.keys()).index(product["pipe_size"]),
                key=f"pipe_{delivery['id']}_{idx}",
                format_func=lambda x: f"{x}mm",
            )

        with p2:
            product["quantity_m"] = st.number_input(
                "Quantity / length m",
                min_value=0.0,
                value=float(product["quantity_m"]),
                step=10.0,
                key=f"qty_{delivery['id']}_{idx}",
            )

        with p3:
            st.metric("RRP / m", f"${PIPE_RRP[product['pipe_size']]:,.2f}")

        with p4:
            st.metric("Cost / m", f"${PIPE_COST[product['pipe_size']]:,.2f}")

        with p5:
            product["discount_pct"] = st.selectbox(
                "Discount off RRP",
                DISCOUNT_OPTIONS,
                index=DISCOUNT_OPTIONS.index(product["discount_pct"]),
                key=f"discount_{delivery['id']}_{idx}",
                format_func=lambda x: f"{x}%",
            )

        if len(delivery["products"]) > 1:
            if st.button("Remove this pipe size", key=f"remove_product_{delivery['id']}_{idx}"):
                remove_product_from_delivery(delivery["id"], idx)
                st.rerun()

        st.markdown("---")

    if st.button("+ Add Pipe Size to this Delivery", key=f"add_product_{delivery['id']}", use_container_width=True):
        add_product_to_delivery(delivery["id"])
        st.rerun()

    st.markdown("### Freight for this delivery")

    f1, f2, f3, f4 = st.columns(4)

    with f1:
        delivery["freight_method"] = st.radio(
            "Freight method",
            ["Auto calculate", "Manual override"],
            horizontal=True,
            key=f"freight_method_{delivery['id']}",
        )

    with f2:
        delivery["trip_type"] = st.radio(
            "Trip",
            ["Return", "One-way"],
            horizontal=True,
            key=f"trip_{delivery['id']}",
        )

    with f3:
        delivery["zone"] = st.selectbox(
            "Zone",
            list(ZONES.keys()),
            index=list(ZONES.keys()).index(delivery["zone"]),
            key=f"zone_{delivery['id']}",
        )

    with f4:
        if st.button("Use Zone km", key=f"use_zone_{delivery['id']}", use_container_width=True):
            delivery["km_one_way"] = float(ZONES[delivery["zone"]])
            st.rerun()

    f5, f6, f7, f8 = st.columns(4)

    with f5:
        delivery["km_one_way"] = st.number_input(
            "One-way km",
            min_value=0.0,
            value=float(delivery["km_one_way"]),
            step=10.0,
            key=f"km_{delivery['id']}",
        )

    with f6:
        delivery["fleet"] = st.selectbox(
            "Fleet",
            list(FLEET.keys()),
            index=list(FLEET.keys()).index(delivery["fleet"]),
            key=f"fleet_{delivery['id']}",
        )

    with f7:
        delivery["site_hours"] = st.number_input(
            "Site hours",
            min_value=0.0,
            value=float(delivery["site_hours"]),
            step=0.5,
            key=f"site_hours_{delivery['id']}",
        )

    with f8:
        if delivery["freight_method"] == "Manual override":
            delivery["manual_freight"] = st.number_input(
                "Manual freight",
                min_value=0.0,
                value=float(delivery["manual_freight"]),
                step=50.0,
                key=f"manual_freight_{delivery['id']}",
            )

    delivery_rows, delivery_freight = calculate_delivery(delivery, global_inputs, region_key)
    all_rows.extend(delivery_rows)

    delivery_revenue = sum(r["Revenue"] for r in delivery_rows)
    delivery_contribution = sum(r["Contribution $"] for r in delivery_rows)
    delivery_margin = safe_divide(delivery_contribution, delivery_revenue)

    delivery_summary_rows.append(
        {
            "Delivery": f"Delivery {delivery['id']}",
            "Revenue": delivery_revenue,
            "Freight": delivery_freight,
            "Contribution": delivery_contribution,
            "Margin": delivery_margin,
        }
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Delivery revenue", money(delivery_revenue))
    m2.metric("Delivery freight", money(delivery_freight))
    m3.metric("Contribution", money(delivery_contribution))
    m4.metric("Contribution margin", pct(delivery_margin))

    st.markdown("</div>", unsafe_allow_html=True)


detail_df = pd.DataFrame(all_rows)

if detail_df.empty:
    st.warning("Please add at least one product line.")
    st.stop()


# =========================================================
# SUMMARY CALCULATIONS
# =========================================================

total_quantity = detail_df["Quantity m"].sum()
total_rrp_revenue = detail_df["RRP Revenue"].sum()
total_revenue = detail_df["Revenue"].sum()
total_product_cost = detail_df["Product Cost"].sum()
total_freight = detail_df["Freight Allocated"].sum()
total_cost = detail_df["Total Cost"].sum()
total_contribution = detail_df["Contribution $"].sum()

package_margin = safe_divide(total_contribution, total_revenue)

rrp_contribution = detail_df["RRP Contribution $"].sum()
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
    risk_class = "bad"
    risk_title = "High margin risk"
    risk_message = "The package is below the high-risk margin threshold. Review discounting, freight recovery or product cost before submitting."
elif package_margin < target_margin:
    risk_class = "watch"
    risk_title = "Margin below target"
    risk_message = "The package is above the risk floor but below target. Check whether the discount is commercially justified."
else:
    risk_class = "good"
    risk_title = "Healthy package margin"
    risk_message = "The package is above the target contribution margin."

st.markdown(
    f"""
<div class="risk-box {risk_class}">
    <h3 style="margin-top:0;">{risk_title}</h3>
    <p>
        {risk_message}<br><br>
        At RRP, the package margin would be <b>{rrp_margin:.1%}</b>.
        After discounting and freight allocation, it is <b>{package_margin:.1%}</b>.
        Discounting has put <b>{money(margin_lost)}</b> of contribution margin at risk.
    </p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# PEER FREIGHT ASSUMPTIONS
# =========================================================

st.markdown("## Peer Freight Assumptions")
st.markdown('<div class="card">', unsafe_allow_html=True)

st.caption("Edit competitor freight manually. Defaults are based on Atlan freight adjusted by each competitor’s freight factor.")

peer_freight = {}

peer_cols = st.columns(len(COMPETITORS))

for col, competitor in zip(peer_cols, COMPETITORS):
    default_freight = total_freight * competitor.default_freight_factor

    with col:
        peer_freight[competitor.name] = st.number_input(
            competitor.name,
            min_value=0.0,
            value=float(default_freight),
            step=50.0,
            key=f"peer_freight_{competitor.name}",
        )

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# PEER COMPARISON
# =========================================================

peer_df = build_peer_comparison(
    detail_df=detail_df,
    peer_freight=peer_freight,
    region_key=region_key,
    total_revenue=total_revenue,
    total_freight=total_freight,
)

st.markdown("## Peer Package Comparison")
st.markdown('<div class="card">', unsafe_allow_html=True)

st.dataframe(
    peer_df.style.format(
        {
            "Product Package": "${:,.0f}",
            "Peer Freight": "${:,.0f}",
            "Total Package": "${:,.0f}",
            "Average $ / m": "${:,.2f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

peer_avg = peer_df.loc[peer_df["Supplier"] != "Atlan Proposed Package", "Total Package"].mean()
gap_vs_peer_avg = safe_divide(total_revenue - peer_avg, peer_avg)

if gap_vs_peer_avg > 0.10:
    st.warning(f"Atlan is priced {gap_vs_peer_avg:.1%} above the peer average package.")
elif gap_vs_peer_avg < -0.05:
    st.success(f"Atlan is priced {abs(gap_vs_peer_avg):.1%} below the peer average package.")
else:
    st.info(f"Atlan is broadly market-aligned at {gap_vs_peer_avg:.1%} versus the peer average.")

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# DETAIL OUTPUT
# =========================================================

with st.expander("View detailed product output"):
    st.dataframe(
        detail_df.style.format(
            {
                "Quantity m": "{:,.0f}",
                "RRP / m": "${:,.2f}",
                "Discount %": "{:.0f}%",
                "Net Price / m": "${:,.2f}",
                "RRP Revenue": "${:,.0f}",
                "Revenue": "${:,.0f}",
                "Product Cost": "${:,.0f}",
                "Freight Allocated": "${:,.0f}",
                "Total Cost": "${:,.0f}",
                "Contribution $": "${:,.0f}",
                "Contribution Margin %": "{:.1%}",
                "RRP Contribution $": "${:,.0f}",
                "RRP Margin %": "{:.1%}",
                "Margin Lost $": "${:,.0f}",
                "Margin Lost pp": "{:.1f} pts",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# DOWNLOAD
# =========================================================

csv = detail_df.to_csv(index=False)

st.download_button(
    label="Download pricing output",
    data=csv,
    file_name="atlan_pricing_output.csv",
    mime="text/csv",
    use_container_width=True,
)
