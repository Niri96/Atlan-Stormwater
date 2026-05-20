from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
import streamlit as st


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Atlan Pricing Engine",
    page_icon="💧",
    layout="wide",
)


# =========================================================
# STYLING
# =========================================================

st.markdown(
    """
<style>

.stApp {
    background: #F4F7FB;
}

.block-container {
    max-width: 1400px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

.hero {
    background: linear-gradient(135deg, #071B3A 0%, #0B5CFF 100%);
    padding: 36px;
    border-radius: 28px;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 22px 50px rgba(7,27,58,0.22);
}

.hero h1 {
    font-size: 42px;
    margin-bottom: 8px;
    font-weight: 850;
}

.hero p {
    font-size: 17px;
    opacity: 0.92;
    max-width: 900px;
}

.card {
    background: white;
    border-radius: 24px;
    padding: 24px;
    margin-bottom: 22px;
    border: 1px solid rgba(7,27,58,0.08);
    box-shadow: 0 10px 30px rgba(7,27,58,0.05);
}

.section-title {
    font-size: 22px;
    font-weight: 800;
    color: #071B3A;
    margin-bottom: 6px;
}

.subtle {
    color: rgba(7,27,58,0.62);
    font-size: 14px;
}

.line-header {
    font-size: 18px;
    font-weight: 800;
    color: #071B3A;
}

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
    border-radius: 22px;
    padding: 22px;
    margin-top: 18px;
}

[data-testid="stMetricValue"] {
    color: #071B3A;
    font-weight: 850;
}

[data-testid="stMetricLabel"] {
    color: rgba(7,27,58,0.68);
}

div.stButton > button {
    border-radius: 14px;
    font-weight: 750;
}

div.stButton > button[kind="primary"] {
    background: #0B5CFF;
    border-color: #0B5CFF;
}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# DATA
# =========================================================

PIPE_RRP = {
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

PIPE_COST = {
    size: round(rrp * 0.65, 2)
    for size, rrp in PIPE_RRP.items()
}

DISCOUNT_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]

ZONES = {
    "Metro": 30,
    "Outer Metro": 60,
    "Regional": 150,
    "Remote": 350,
    "TAS": 600,
}

COMPETITORS = {
    "Competitor A": 0.88,
    "Competitor B": 1.00,
    "Competitor C": 1.16,
    "Competitor D": 0.96,
    "Competitor E": 0.82,
}


# =========================================================
# HELPERS
# =========================================================

def money(x):
    return f"${x:,.0f}"


def pct(x):
    return f"{x:.1%}"


def safe_divide(a, b):
    return a / b if b else 0


def calculate_freight(
    km,
    driver_rate,
    diesel_price,
    avg_speed,
    site_hours,
):
    fuel_per_km = 1.25
    maintenance_per_km = 0.22

    total_km = km * 2

    fuel_cost = total_km * fuel_per_km * diesel_price / 3
    maintenance_cost = total_km * maintenance_per_km

    drive_hours = total_km / avg_speed
    labour_cost = (drive_hours + site_hours) * driver_rate

    return fuel_cost + maintenance_cost + labour_cost


# =========================================================
# SESSION STATE
# =========================================================

if "deliveries" not in st.session_state:
    st.session_state.deliveries = []


def add_delivery():
    st.session_state.deliveries.append(
        {
            "id": len(st.session_state.deliveries) + 1,
            "products": [
                {
                    "pipe_size": 375,
                    "quantity": 100,
                    "discount": 0,
                }
            ],
            "freight_method": "Auto",
            "zone": "Metro",
            "km": 30,
            "manual_freight": 0,
            "site_hours": 1.0,
        }
    )


if len(st.session_state.deliveries) == 0:
    add_delivery()


# =========================================================
# HERO
# =========================================================

st.markdown(
    """
<div class="hero">
    <h1>Atlan Stormwater Pricing Engine</h1>
    <p>
        Build a delivery package, apply controlled discounting,
        calculate freight live, and understand contribution margin risk.
    </p>
</div>
""",
    unsafe_allow_html=True,
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## Global Freight Inputs")

    driver_rate = st.number_input(
        "Driver $ / hr",
        value=100.0,
        step=5.0,
    )

    diesel_price = st.number_input(
        "Diesel $ / L",
        value=3.00,
        step=0.10,
    )

    avg_speed = st.number_input(
        "Average km/h",
        value=60.0,
        step=5.0,
    )

    st.divider()

    target_margin = st.slider(
        "Target contribution margin %",
        0,
        70,
        35,
    ) / 100

    risk_margin = st.slider(
        "High-risk margin threshold %",
        0,
        50,
        25,
    ) / 100


# =========================================================
# ADD DELIVERY BUTTON
# =========================================================

top1, top2 = st.columns([0.8, 0.2])

with top1:
    st.markdown("## Package Builder")

with top2:
    if st.button("+ Add Delivery", type="primary", use_container_width=True):
        add_delivery()
        st.rerun()


# =========================================================
# DELIVERY CARDS
# =========================================================

all_rows = []

for delivery in st.session_state.deliveries:

    st.markdown('<div class="card">', unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="line-header">
Delivery #{delivery["id"]}
</div>
<div class="subtle">
Each delivery can contain multiple pipe sizes.
</div>
""",
        unsafe_allow_html=True,
    )

    st.divider()

    # =====================================================
    # PRODUCTS
    # =====================================================

    for i, product in enumerate(delivery["products"]):

        p1, p2, p3, p4 = st.columns(4)

        with p1:
            product["pipe_size"] = st.selectbox(
                "Pipe Size",
                list(PIPE_RRP.keys()),
                key=f"pipe_{delivery['id']}_{i}",
                index=list(PIPE_RRP.keys()).index(product["pipe_size"]),
                format_func=lambda x: f"{x}mm",
            )

        with p2:
            product["quantity"] = st.number_input(
                "Quantity (m)",
                min_value=0.0,
                value=float(product["quantity"]),
                step=10.0,
                key=f"qty_{delivery['id']}_{i}",
            )

        with p3:
            st.metric(
                "RRP / m",
                f"${PIPE_RRP[product['pipe_size']]:,.2f}",
            )

        with p4:
            st.metric(
                "Cost / m",
                f"${PIPE_COST[product['pipe_size']]:,.2f}",
            )

        d1, d2 = st.columns([0.3, 0.7])

        with d1:
            product["discount"] = st.selectbox(
                "Discount %",
                DISCOUNT_OPTIONS,
                key=f"disc_{delivery['id']}_{i}",
                index=DISCOUNT_OPTIONS.index(product["discount"]),
                format_func=lambda x: f"{x}%",
            )

        with d2:
            if st.button(
                f"+ Add Pipe Size",
                key=f"add_pipe_{delivery['id']}_{i}",
                use_container_width=True,
            ):
                delivery["products"].append(
                    {
                        "pipe_size": 375,
                        "quantity": 100,
                        "discount": 0,
                    }
                )
                st.rerun()

        st.divider()

    # =====================================================
    # FREIGHT
    # =====================================================

    st.markdown("### Freight")

    f1, f2, f3, f4 = st.columns(4)

    with f1:
        delivery["freight_method"] = st.radio(
            "Freight Method",
            ["Auto", "Manual"],
            horizontal=True,
            key=f"freight_method_{delivery['id']}",
        )

    with f2:
        delivery["zone"] = st.selectbox(
            "Zone",
            list(ZONES.keys()),
            key=f"zone_{delivery['id']}",
        )

    with f3:
        delivery["km"] = st.number_input(
            "One-way km",
            value=float(delivery["km"]),
            step=10.0,
            key=f"km_{delivery['id']}",
        )

    with f4:
        delivery["site_hours"] = st.number_input(
            "Site Hours",
            value=float(delivery["site_hours"]),
            step=0.5,
            key=f"site_{delivery['id']}",
        )

    if st.button(
        "Use Zone km",
        key=f"use_zone_{delivery['id']}",
    ):
        delivery["km"] = ZONES[delivery["zone"]]
        st.rerun()

    if delivery["freight_method"] == "Manual":
        delivery["manual_freight"] = st.number_input(
            "Manual Freight Cost",
            value=float(delivery["manual_freight"]),
            step=50.0,
            key=f"manual_freight_{delivery['id']}",
        )

    # =====================================================
    # CALCULATIONS
    # =====================================================

    if delivery["freight_method"] == "Manual":
        freight_cost = delivery["manual_freight"]
    else:
        freight_cost = calculate_freight(
            km=delivery["km"],
            driver_rate=driver_rate,
            diesel_price=diesel_price,
            avg_speed=avg_speed,
            site_hours=delivery["site_hours"],
        )

    freight_per_product = freight_cost / len(delivery["products"])

    delivery_revenue = 0
    delivery_contribution = 0

    for product in delivery["products"]:

        pipe_size = product["pipe_size"]
        quantity = product["quantity"]
        discount = product["discount"]

        rrp = PIPE_RRP[pipe_size]
        cost = PIPE_COST[pipe_size]

        net_price = rrp * (1 - discount / 100)

        revenue = net_price * quantity
        product_cost = cost * quantity
        total_cost = product_cost + freight_per_product

        contribution = revenue - total_cost

        contribution_margin = safe_divide(
            contribution,
            revenue,
        )

        rrp_revenue = rrp * quantity
        rrp_contribution = rrp_revenue - total_cost

        margin_lost = rrp_contribution - contribution

        all_rows.append(
            {
                "Pipe Size": f"{pipe_size}mm",
                "Quantity": quantity,
                "Discount %": discount,
                "Revenue": revenue,
                "Product Cost": product_cost,
                "Freight": freight_per_product,
                "Contribution": contribution,
                "Contribution Margin %": contribution_margin,
                "Margin Lost": margin_lost,
            }
        )

        delivery_revenue += revenue
        delivery_contribution += contribution

    delivery_margin = safe_divide(
        delivery_contribution,
        delivery_revenue,
    )

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("Delivery Revenue", money(delivery_revenue))

    with m2:
        st.metric("Freight", money(freight_cost))

    with m3:
        st.metric("Contribution", money(delivery_contribution))

    with m4:
        st.metric("Margin %", pct(delivery_margin))

    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# PACKAGE SUMMARY
# =========================================================

df = pd.DataFrame(all_rows)

total_revenue = df["Revenue"].sum()
total_contribution = df["Contribution"].sum()
total_freight = df["Freight"].sum()
margin_lost = df["Margin Lost"].sum()

package_margin = safe_divide(
    total_contribution,
    total_revenue,
)

weighted_discount = safe_divide(
    margin_lost,
    total_revenue + margin_lost,
)

st.markdown("## Executive Summary")

st.markdown('<div class="card">', unsafe_allow_html=True)

s1, s2, s3, s4 = st.columns(4)

with s1:
    st.metric(
        "Revenue",
        money(total_revenue),
    )

with s2:
    st.metric(
        "Contribution",
        money(total_contribution),
    )

with s3:
    st.metric(
        "Contribution Margin",
        pct(package_margin),
    )

with s4:
    st.metric(
        "Margin at Risk",
        money(margin_lost),
    )

if package_margin < risk_margin:
    risk_class = "bad"
    title = "High Margin Risk"
elif package_margin < target_margin:
    risk_class = "watch"
    title = "Margin Below Target"
else:
    risk_class = "good"
    title = "Healthy Margin"

st.markdown(
    f"""
<div class="risk-box {risk_class}">
<h3>{title}</h3>

<p>
Weighted discount across the package is <b>{weighted_discount:.1%}</b>.
Discounting has put <b>{money(margin_lost)}</b> of contribution margin at risk.
</p>

</div>
""",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# PEER COMPARISON
# =========================================================

st.markdown("## Peer Comparison")

peer_rows = []

avg_price = safe_divide(
    total_revenue,
    df["Quantity"].sum(),
)

for competitor, factor in COMPETITORS.items():

    peer_revenue = (
        avg_price
        * df["Quantity"].sum()
        * factor
    )

    peer_rows.append(
        {
            "Supplier": competitor,
            "Estimated Package": peer_revenue,
            "Average $ / m": safe_divide(
                peer_revenue,
                df["Quantity"].sum(),
            ),
        }
    )

peer_rows.append(
    {
        "Supplier": "Atlan Proposed Package",
        "Estimated Package": total_revenue,
        "Average $ / m": avg_price,
    }
)

peer_df = pd.DataFrame(peer_rows)

st.markdown('<div class="card">', unsafe_allow_html=True)

st.dataframe(
    peer_df.style.format(
        {
            "Estimated Package": "${:,.0f}",
            "Average $ / m": "${:,.2f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# DETAIL OUTPUT
# =========================================================

with st.expander("Detailed Product Output"):

    st.dataframe(
        df.style.format(
            {
                "Revenue": "${:,.0f}",
                "Product Cost": "${:,.0f}",
                "Freight": "${:,.0f}",
                "Contribution": "${:,.0f}",
                "Contribution Margin %": "{:.1%}",
                "Margin Lost": "${:,.0f}",
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
    label="Download Pricing Output",
    data=csv,
    file_name="atlan_pricing_output.csv",
    mime="text/csv",
    use_container_width=True,
)
