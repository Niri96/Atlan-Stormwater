# FULL WORKING STREAMLIT APP

# SAVE AS: app.py

from **future** import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
import streamlit as st

st.set_page_config(
page_title="Atlan Pricing Engine",
page_icon="💧",
layout="wide",
)

# =========================================================

# STYLING

# =========================================================

st.markdown("""

<style>

.stApp {
    background: #F4F7FB;
}

.block-container {
    max-width: 1450px;
    padding-top: 0.8rem;
    padding-bottom: 1rem;
}

.hero {
    background: linear-gradient(135deg, #071B3A 0%, #0B5CFF 100%);
    padding: 20px 24px;
    border-radius: 20px;
    color: white;
    margin-bottom: 16px;
}

.hero h1 {
    font-size: 28px;
    margin-bottom: 4px;
    font-weight: 850;
}

.hero p {
    font-size: 13px;
    opacity: 0.9;
}

.card {
    background: white;
    border-radius: 18px;
    padding: 16px;
    margin-bottom: 14px;
    border: 1px solid rgba(7,27,58,0.06);
    box-shadow: 0 6px 18px rgba(7,27,58,0.04);
}

.title {
    font-size: 17px;
    font-weight: 800;
    color: #071B3A;
}

.subtle {
    color: rgba(7,27,58,0.60);
    font-size: 11px;
}

[data-testid="stMetric"] {
    background: white;
    border-radius: 14px;
    padding: 10px 12px;
    border: 1px solid rgba(7,27,58,0.06);
}

[data-testid="stMetricLabel"] {
    font-size: 11px;
}

[data-testid="stMetricValue"] {
    font-size: 21px;
    font-weight: 850;
}

.stSelectbox label,
.stNumberInput label,
.stRadio label {
    font-size: 11px !important;
    font-weight: 650 !important;
}

div.stButton > button {
    border-radius: 10px;
    font-weight: 700;
    font-size: 12px;
}

</style>

""", unsafe_allow_html=True)

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

REGIONS = {
"VIC": 1.00,
"QLD": 0.95,
"NSW": 0.97,
"WA": 1.05,
"SA": 1.02,
"TAS": 1.08,
}

COMPETITORS = {
"Competitor A": 0.88,
"Competitor B": 1.00,
"Competitor C": 1.16,
"Competitor D": 0.96,
"Competitor E": 0.82,
}

ZONES = {
"Metro": 30,
"Outer Metro": 60,
"Regional": 150,
"Remote": 350,
"TAS": 600,
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
total_km = km * 2

```
fuel_cost = total_km * 1.25 * diesel_price / 3
maintenance = total_km * 0.22

drive_hours = total_km / avg_speed
labour = (drive_hours + site_hours) * driver_rate

return fuel_cost + maintenance + labour
```

# =========================================================

# SESSION STATE

# =========================================================

if "deliveries" not in st.session_state:
st.session_state.deliveries = []

def add_delivery():
st.session_state.deliveries.append({
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
"site_hours": 1,
})

if len(st.session_state.deliveries) == 0:
add_delivery()

# =========================================================

# HERO

# =========================================================

st.markdown("""

<div class="hero">
<h1>Atlan Pricing Engine</h1>
<p>
Build delivery packages, apply discounts, calculate freight and compare Atlan against peer pricing.
</p>
</div>
""", unsafe_allow_html=True)

# =========================================================

# SIDEBAR

# =========================================================

with st.sidebar:

```
region = st.selectbox(
    "Region",
    list(REGIONS.keys())
)

driver_rate = st.number_input(
    "Driver $ / hr",
    value=100.0
)

diesel_price = st.number_input(
    "Diesel $ / L",
    value=3.0
)

avg_speed = st.number_input(
    "Average km/h",
    value=60.0
)

target_margin = st.slider(
    "Target Margin %",
    0,
    70,
    35
) / 100

risk_margin = st.slider(
    "High Risk Margin %",
    0,
    50,
    25
) / 100
```

# =========================================================

# PACKAGE BUILDER

# =========================================================

top1, top2 = st.columns([0.8, 0.2])

with top1:
st.markdown("### Package Builder")

with top2:
if st.button("+ Add Delivery", type="primary", use_container_width=True):
add_delivery()
st.rerun()

all_rows = []

for delivery in st.session_state.deliveries:

```
st.markdown('<div class="card">', unsafe_allow_html=True)

st.markdown(
    f'<div class="title">Delivery {delivery["id"]}</div>',
    unsafe_allow_html=True
)

for i, product in enumerate(delivery["products"]):

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        product["pipe_size"] = st.selectbox(
            "Pipe",
            list(PIPE_RRP.keys()),
            index=list(PIPE_RRP.keys()).index(product["pipe_size"]),
            key=f"pipe_{delivery['id']}_{i}",
            format_func=lambda x: f"{x}mm"
        )

    with c2:
        product["quantity"] = st.number_input(
            "Qty m",
            value=float(product["quantity"]),
            step=10.0,
            key=f"qty_{delivery['id']}_{i}"
        )

    with c3:
        st.metric(
            "RRP/m",
            f"${PIPE_RRP[product['pipe_size']]:,.0f}"
        )

    with c4:
        st.metric(
            "Cost/m",
            f"${PIPE_COST[product['pipe_size']]:,.0f}"
        )

    with c5:
        product["discount"] = st.selectbox(
            "Discount",
            DISCOUNT_OPTIONS,
            index=DISCOUNT_OPTIONS.index(product["discount"]),
            key=f"discount_{delivery['id']}_{i}",
            format_func=lambda x: f"{x}%"
        )

    if st.button(
        "+ Add Pipe Size",
        key=f"add_pipe_{delivery['id']}_{i}"
    ):
        delivery["products"].append({
            "pipe_size": 375,
            "quantity": 100,
            "discount": 0,
        })
        st.rerun()

with st.expander("Freight Settings", expanded=False):

    f1, f2, f3, f4 = st.columns(4)

    with f1:
        delivery["zone"] = st.selectbox(
            "Zone",
            list(ZONES.keys()),
            key=f"zone_{delivery['id']}"
        )

    with f2:
        delivery["km"] = st.number_input(
            "One-way km",
            value=float(delivery["km"]),
            step=10.0,
            key=f"km_{delivery['id']}"
        )

    with f3:
        delivery["site_hours"] = st.number_input(
            "Site hrs",
            value=float(delivery["site_hours"]),
            step=0.5,
            key=f"site_{delivery['id']}"
        )

    with f4:
        delivery["manual_freight"] = st.number_input(
            "Manual freight override",
            value=float(delivery["manual_freight"]),
            step=50.0,
            key=f"manual_{delivery['id']}"
        )

freight = (
    delivery["manual_freight"]
    if delivery["manual_freight"] > 0
    else calculate_freight(
        delivery["km"],
        driver_rate,
        diesel_price,
        avg_speed,
        delivery["site_hours"]
    )
)

freight_per_product = freight / len(delivery["products"])

delivery_revenue = 0
delivery_contribution = 0

for product in delivery["products"]:

    rrp = PIPE_RRP[product["pipe_size"]]
    cost = PIPE_COST[product["pipe_size"]]
    qty = product["quantity"]
    discount = product["discount"]

    sell = rrp * (1 - discount / 100)

    revenue = sell * qty
    product_cost = cost * qty
    total_cost = product_cost + freight_per_product

    contribution = revenue - total_cost
    margin = safe_divide(contribution, revenue)

    rrp_revenue = rrp * qty
    rrp_contribution = rrp_revenue - total_cost

    margin_lost = rrp_contribution - contribution

    all_rows.append({
        "Pipe": f"{product['pipe_size']}mm",
        "Qty": qty,
        "Discount %": discount,
        "Revenue": revenue,
        "Freight": freight_per_product,
        "Contribution": contribution,
        "Margin %": margin,
        "Margin Lost": margin_lost,
    })

    delivery_revenue += revenue
    delivery_contribution += contribution

delivery_margin = safe_divide(
    delivery_contribution,
    delivery_revenue
)

m1, m2, m3, m4 = st.columns(4)

m1.metric("Revenue", money(delivery_revenue))
m2.metric("Freight", money(freight))
m3.metric("Contribution", money(delivery_contribution))
m4.metric("Margin", pct(delivery_margin))

st.markdown("</div>", unsafe_allow_html=True)
```

# =========================================================

# SUMMARY

# =========================================================

df = pd.DataFrame(all_rows)

total_revenue = df["Revenue"].sum()
total_contribution = df["Contribution"].sum()
total_freight = df["Freight"].sum()
margin_lost = df["Margin Lost"].sum()

package_margin = safe_divide(
total_contribution,
total_revenue
)

st.markdown("### Executive Summary")

st.markdown('<div class="card">', unsafe_allow_html=True)

s1, s2, s3, s4, s5 = st.columns(5)

s1.metric("Revenue", money(total_revenue))
s2.metric("Contribution", money(total_contribution))
s3.metric("Margin", pct(package_margin))
s4.metric("Margin at Risk", money(margin_lost))
s5.metric("Freight", money(total_freight))

st.markdown("</div>", unsafe_allow_html=True)

# =========================================================

# PEER FREIGHT

# =========================================================

with st.expander("Peer Freight Assumptions"):

```
peer_freight = {}

cols = st.columns(len(COMPETITORS))

for col, comp in zip(cols, COMPETITORS.keys()):

    with col:
        peer_freight[comp] = st.number_input(
            comp,
            value=float(total_freight),
            step=50.0,
            key=f"peer_{comp}"
        )
```

# =========================================================

# PEER COMPARISON

# =========================================================

peer_rows = []

for comp, factor in COMPETITORS.items():

```
peer_product = 0

for _, row in df.iterrows():
    peer_product += (
        row["Revenue"]
        * factor
        * REGIONS[region]
    )

total_package = peer_product + peer_freight[comp]

peer_rows.append({
    "Supplier": comp,
    "Product Package": peer_product,
    "Peer Freight": peer_freight[comp],
    "Total Package": total_package,
})
```

peer_rows.append({
"Supplier": "Atlan Proposed Package",
"Product Package": total_revenue,
"Peer Freight": total_freight,
"Total Package": total_revenue,
})

peer_df = pd.DataFrame(peer_rows)

st.markdown("### Peer Package Comparison")

st.markdown('<div class="card">', unsafe_allow_html=True)

st.dataframe(
peer_df.style.format({
"Product Package": "${:,.0f}",
"Peer Freight": "${:,.0f}",
"Total Package": "${:,.0f}",
}),
use_container_width=True,
hide_index=True,
)

peer_only = peer_df[
peer_df["Supplier"] != "Atlan Proposed Package"
]

peer_avg = peer_only["Total Package"].mean()

gap_vs_avg = safe_divide(
total_revenue - peer_avg,
peer_avg
)

c1, c2, c3, c4 = st.columns(4)

c1.metric("Atlan Package", money(total_revenue))
c2.metric("Peer Average", money(peer_avg), delta=f"{gap_vs_avg:.1%}")
c3.metric("Peer Low", money(peer_only["Total Package"].min()))
c4.metric("Peer High", money(peer_only["Total Package"].max()))

if gap_vs_avg > 0.10:
st.warning(
f"Atlan is priced {gap_vs_avg:.1%} above peer average."
)
elif gap_vs_avg < -0.05:
st.success(
f"Atlan is priced {abs(gap_vs_avg):.1%} below peer average."
)
else:
st.info(
f"Atlan is broadly market aligned at {gap_vs_avg:.1%}."
)

st.markdown("</div>", unsafe_allow_html=True)

# =========================================================

# DETAIL OUTPUT

# =========================================================

with st.expander("Detailed Product Output"):

```
st.dataframe(
    df.style.format({
        "Revenue": "${:,.0f}",
        "Freight": "${:,.0f}",
        "Contribution": "${:,.0f}",
        "Margin %": "{:.1%}",
        "Margin Lost": "${:,.0f}",
    }),
    use_container_width=True,
    hide_index=True,
)
```

csv = df.to_csv(index=False)

st.download_button(
label="Download Pricing Output",
data=csv,
file_name="atlan_pricing_output.csv",
mime="text/csv",
use_container_width=True,
)
