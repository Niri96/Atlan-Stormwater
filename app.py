from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Atlan Pricing Engine", page_icon="💧", layout="wide")


# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Region:
    name: str
    market_factor: float
    freight_factor: float
    notes: str


@dataclass(frozen=True)
class Fleet:
    name: str
    litres_per_100km: float
    maintenance_per_km: float


# State → column name mapping for NetSuite price list
STATE_TO_NETSUITE_COL = {
    "VIC": "VIC",
    "NSW": "NSW / ACT",
    "QLD": "QLD",
    "WA": "WA",
    "SA": "SA",
    "TAS": "TAS",
    "NT": "NT",
}

# Competitor Intelligence: regions map to State column values
COMPETITOR_STATE_MAP = {
    "VIC": ["VIC/TAS", "VIC"],
    "TAS": ["VIC/TAS", "TAS"],
    "NSW": ["NSW/ACT", "NSW"],
    "QLD": ["QLD/NT", "QLD"],
    "WA": ["WA"],
    "SA": ["SA"],
    "NT": ["QLD/NT", "NT"],
}

REGIONS: Dict[str, Region] = {
    "VIC": Region("Victoria", 1.00, 1.00, "Balanced market with room for value-led pricing."),
    "QLD": Region("Queensland", 0.95, 1.05, "Competitive market with stronger price pressure."),
    "NSW": Region("New South Wales", 0.97, 1.10, "High-volume market with active peer competition."),
    "WA": Region("Western Australia", 1.05, 1.18, "Higher freight exposure and supply cost."),
    "SA": Region("South Australia", 1.02, 1.12, "Moderate pricing pressure with freight sensitivity."),
    "TAS": Region("Tasmania", 1.06, 1.30, "Freight-sensitive market with delivery complexity."),
    "NT": Region("Northern Territory", 0.94, 1.20, "Remote market with higher freight sensitivity."),
}

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

DISCOUNT_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]

# Fallback hardcoded pipe RRP (used when no NetSuite file uploaded)
FALLBACK_PIPE_RRP = {
    "225mm": 85,
    "300mm": 120,
    "375mm": 165,
    "450mm": 220,
    "525mm": 285,
    "600mm": 360,
    "750mm": 520,
    "900mm": 720,
    "1050mm": 950,
    "1200mm": 1250,
}

COST_FACTOR = 0.65  # product cost as fraction of RRP/sell price


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
<style>
.stApp { background: #F4F7FB; }
.block-container { max-width: 1450px; padding-top: 0.8rem; padding-bottom: 1rem; }
.hero {
    background: linear-gradient(135deg, #071B3A 0%, #0B5CFF 100%);
    padding: 22px 26px; border-radius: 22px; color: white;
    box-shadow: 0 14px 34px rgba(7,27,58,0.18); margin-bottom: 16px;
}
.hero h1 { font-size: 28px; margin-bottom: 4px; font-weight: 850; line-height: 1.1; }
.hero p { font-size: 13px; opacity: 0.90; margin-bottom: 0; line-height: 1.4; }
.card {
    background: white; border: 1px solid rgba(7,27,58,0.06); border-radius: 18px;
    padding: 16px; margin-bottom: 14px; box-shadow: 0 6px 18px rgba(7,27,58,0.04);
}
.title { font-size: 17px; font-weight: 800; color: #071B3A; margin-bottom: 2px; }
.subtle { color: rgba(7,27,58,0.60); font-size: 11px; line-height: 1.3; }
.good { background: #ECFDF3; }
.watch { background: #FFF7E6; }
.bad { background: #FFF1F1; }
.risk-box {
    border-radius: 16px; padding: 14px 16px; margin-top: 12px;
    border: 1px solid rgba(7,27,58,0.08); font-size: 12px;
}
[data-testid="stMetric"] {
    background: white; border-radius: 14px; padding: 10px 12px;
    border: 1px solid rgba(7,27,58,0.06); box-shadow: 0 4px 12px rgba(7,27,58,0.03);
}
[data-testid="stMetricLabel"] { font-size: 11px; color: rgba(7,27,58,0.62); }
[data-testid="stMetricValue"] { font-size: 21px; font-weight: 850; color: #071B3A; }
[data-testid="stMetricDelta"] { font-size: 11px; }
.stSelectbox label, .stNumberInput label, .stRadio label {
    font-size: 11px !important; font-weight: 650 !important;
}
.stTextInput input, .stNumberInput input { font-size: 12px !important; }
.stSelectbox div[data-baseweb="select"] { min-height: 34px; }
div.stButton > button { border-radius: 10px; font-weight: 700; font-size: 12px; padding: 0.35rem 0.8rem; }
div.stButton > button[kind="primary"] { background: #0B5CFF; border-color: #0B5CFF; }
section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid rgba(7,27,58,0.08); }
[data-testid="stDataFrame"] { font-size: 11px; }
.streamlit-expanderHeader { font-size: 13px !important; font-weight: 700 !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def safe_divide(a: float, b: float) -> float:
    return a / b if b else 0.0


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _read_spreadsheet(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read xlsx, xls (including XML-disguised), or csv robustly."""
    name = filename.lower()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(file_bytes))
    # Detect if file is actually XML content (NetSuite exports .xls as XML)
    sniff = file_bytes[:200].lstrip()
    is_xml = sniff.startswith(b"<?xml") or sniff.startswith(b"<html") or b"<Workbook" in sniff
    if is_xml:
        tables = pd.read_html(io.BytesIO(file_bytes), header=0)
        return tables[0]
    if name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
    return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")


@st.cache_data(show_spinner=False)
def load_netsuite(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Load NetSuite price list. Returns df with columns:
    Internal ID, Name, Display Name, Base Price, NSW / ACT, NT, QLD, SA, TAS, VIC, WA, Online Price
    """
    df = _read_spreadsheet(file_bytes, filename)
    df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_data(show_spinner=False)
def load_competitor(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Load Competitor Intelligence. Returns df with columns:
    SubmittedBy, State, SubmissionDate, Atlan Reference, Competitor,
    PipeSize, Length, Price, ApprovedBy, ApprovalDate, Price/m
    """
    df = _read_spreadsheet(file_bytes, filename)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def get_item_price(netsuite_df: pd.DataFrame, item_name: str, region_key: str) -> Optional[float]:
    """Look up price for item_name in the given region. Returns None if not found."""
    col = STATE_TO_NETSUITE_COL.get(region_key)
    if col is None or col not in netsuite_df.columns:
        # fall back to Base Price
        col = "Base Price"
    if col not in netsuite_df.columns:
        return None

    # match on Display Name or Name
    mask = (
        netsuite_df.get("Display Name", pd.Series(dtype=str)).str.strip().str.lower() == item_name.strip().lower()
    ) | (
        netsuite_df.get("Name", pd.Series(dtype=str)).str.strip().str.lower() == item_name.strip().lower()
    )
    rows = netsuite_df[mask]
    if rows.empty:
        return None

    val = rows.iloc[0][col]
    try:
        return float(val)
    except (ValueError, TypeError):
        # try Base Price fallback
        try:
            return float(rows.iloc[0].get("Base Price", None))
        except (ValueError, TypeError):
            return None


def get_competitor_prices(competitor_df: pd.DataFrame, region_key: str) -> Dict[str, Dict]:
    """
    Returns dict: {competitor_name: {"avg_price_per_m": float, "entries": int}}
    Filtered to the relevant state group for region_key.
    """
    state_vals = COMPETITOR_STATE_MAP.get(region_key, [region_key])
    mask = competitor_df["State"].str.strip().isin(state_vals)
    subset = competitor_df[mask].copy()

    if subset.empty:
        return {}

    # parse Price/m
    subset["price_m"] = pd.to_numeric(subset.get("Price/m", subset.get("Price / m", None)), errors="coerce")
    subset = subset.dropna(subset=["price_m"])

    result = {}
    for comp, grp in subset.groupby("Competitor"):
        result[str(comp)] = {
            "avg_price_per_m": grp["price_m"].mean(),
            "entries": len(grp),
            "min": grp["price_m"].min(),
            "max": grp["price_m"].max(),
        }
    return result


# ---------------------------------------------------------------------------
# Freight
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def add_delivery() -> None:
    new_id = st.session_state.next_delivery_id
    st.session_state.next_delivery_id += 1
    st.session_state.deliveries.append(
        {
            "id": new_id,
            "products": [{"item_name": "", "rrp_per_m": 0.0, "quantity_m": 100.0, "discount_pct": 0}],
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
    st.session_state.deliveries = [d for d in st.session_state.deliveries if d["id"] != delivery_id]


def add_product_to_delivery(delivery_id: int) -> None:
    for delivery in st.session_state.deliveries:
        if delivery["id"] == delivery_id:
            delivery["products"].append({"item_name": "", "rrp_per_m": 0.0, "quantity_m": 100.0, "discount_pct": 0})
            break


def remove_product_from_delivery(delivery_id: int, product_index: int) -> None:
    for delivery in st.session_state.deliveries:
        if delivery["id"] == delivery_id and len(delivery["products"]) > 1:
            delivery["products"].pop(product_index)
            break


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------

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

    temp_rows = []
    total_delivery_revenue = 0.0

    for product in delivery["products"]:
        item_name = product.get("item_name", "")
        quantity_m = product["quantity_m"]
        discount_pct = product["discount_pct"]
        rrp_per_m = product.get("rrp_per_m", 0.0) or 0.0

        cost_per_m = round(rrp_per_m * COST_FACTOR, 4)
        net_price_per_m = rrp_per_m * (1 - discount_pct / 100)

        rrp_revenue = rrp_per_m * quantity_m
        revenue = net_price_per_m * quantity_m
        product_cost = cost_per_m * quantity_m

        total_delivery_revenue += revenue

        temp_rows.append(
            {
                "Delivery": f"Delivery {delivery['id']}",
                "Item": item_name,
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
        allocation_pct = safe_divide(row["Revenue"], total_delivery_revenue)
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
    competitor_intel: Dict[str, Dict],
    total_revenue: float,
    total_freight: float,
) -> pd.DataFrame:
    total_quantity = detail_df["Quantity m"].sum()

    rows = []
    for comp_name, comp_data in competitor_intel.items():
        # estimate competitor total package: avg $/m × total quantity + freight (unknown, use Atlan's)
        comp_package = comp_data["avg_price_per_m"] * total_quantity
        rows.append(
            {
                "Supplier": comp_name,
                "Avg $/m": comp_data["avg_price_per_m"],
                "Est. Product Package": comp_package,
                "Peer Freight (est.)": total_freight,
                "Est. Total Package": comp_package + total_freight,
                "Data Points": comp_data["entries"],
                "Price Range": f"${comp_data['min']:,.2f} – ${comp_data['max']:,.2f}",
            }
        )

    rows.append(
        {
            "Supplier": "Atlan Proposed Package",
            "Avg $/m": safe_divide(total_revenue, total_quantity),
            "Est. Product Package": total_revenue,
            "Peer Freight (est.)": total_freight,
            "Est. Total Package": total_revenue + total_freight,
            "Data Points": len(detail_df),
            "Price Range": "—",
        }
    )

    return pd.DataFrame(rows).sort_values("Est. Total Package").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

if "deliveries" not in st.session_state:
    st.session_state.deliveries = []
if "next_delivery_id" not in st.session_state:
    st.session_state.next_delivery_id = 1
if not st.session_state.deliveries:
    add_delivery()


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------

st.markdown(
    """
<div class="hero">
    <h1>Atlan Stormwater Pricing Engine</h1>
    <p>
        Build a multi-delivery pipe package, apply controlled discounts, calculate freight by delivery,
        and compare Atlan's total package against competitor intelligence.
    </p>
</div>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Data Sources")

    netsuite_file = st.file_uploader(
        "NetSuite Price List (.xlsx / .csv)",
        type=["xlsx", "xls", "csv"],
        key="netsuite_upload",
        help="Export from NetSuite. Needs columns: Name or Display Name, Base Price, VIC, NSW / ACT, QLD, etc.",
    )
    competitor_file = st.file_uploader(
        "Competitor Intelligence (.xlsx / .csv)",
        type=["xlsx", "xls", "csv"],
        key="competitor_upload",
        help="Columns: SubmittedBy, State, Competitor, Price/m, etc.",
    )

    netsuite_df: Optional[pd.DataFrame] = None
    competitor_df: Optional[pd.DataFrame] = None

    if netsuite_file:
        try:
            netsuite_df = load_netsuite(netsuite_file.read(), netsuite_file.name)
            st.success(f"✓ NetSuite loaded — {len(netsuite_df):,} items")
        except Exception as e:
            st.error(f"Failed to load NetSuite file: {e}")

    if competitor_file:
        try:
            competitor_df = load_competitor(competitor_file.read(), competitor_file.name)
            st.success(f"✓ Competitor data loaded — {len(competitor_df):,} records")
        except Exception as e:
            st.error(f"Failed to load competitor file: {e}")

    if not netsuite_file:
        st.info("Upload NetSuite price list to enable live item lookup. Fallback prices are used until then.")

    st.divider()

    st.markdown("### Market & Region")
    region_key = st.selectbox(
        "State / Region",
        list(REGIONS.keys()),
        format_func=lambda x: f"{x} — {REGIONS[x].name}",
    )
    st.caption(REGIONS[region_key].notes)

    st.divider()

    st.markdown("### Freight Inputs")
    driver_rate = st.number_input("Driver $ / hr", min_value=0.0, value=100.0, step=5.0)
    diesel_price = st.number_input("Diesel $ / L", min_value=0.0, value=3.00, step=0.10)
    avg_speed = st.number_input("Average km / h", min_value=1.0, value=60.0, step=5.0)

    st.divider()

    st.markdown("### Guardrails")
    target_margin = st.slider("Target margin %", 0, 70, 35, 1) / 100
    risk_margin = st.slider("High-risk margin %", 0, 50, 25, 1) / 100


global_inputs = {"driver_rate": driver_rate, "diesel_price": diesel_price, "avg_speed": avg_speed}


# ---------------------------------------------------------------------------
# Build item options for selectors
# ---------------------------------------------------------------------------

if netsuite_df is not None:
    price_col = STATE_TO_NETSUITE_COL.get(region_key, "Base Price")
    if price_col not in netsuite_df.columns:
        price_col = "Base Price"

    # Only show items that have a price in this state (or Base Price)
    name_col = "Display Name" if "Display Name" in netsuite_df.columns else "Name"
    price_series = pd.to_numeric(netsuite_df.get(price_col, netsuite_df.get("Base Price")), errors="coerce")
    base_series = pd.to_numeric(netsuite_df.get("Base Price", pd.Series(dtype=float)), errors="coerce")
    effective_price = price_series.combine_first(base_series)

    item_mask = effective_price.notna() & (effective_price > 0)
    item_names = netsuite_df.loc[item_mask, name_col].dropna().str.strip().sort_values().tolist()
else:
    # Fall back to simple pipe sizes
    item_names = list(FALLBACK_PIPE_RRP.keys())


def resolve_price(item_name: str) -> float:
    """Return sell price per metre for item_name in current region."""
    if netsuite_df is not None:
        p = get_item_price(netsuite_df, item_name, region_key)
        if p is not None:
            return p
    # fallback
    return FALLBACK_PIPE_RRP.get(item_name, 0.0)


# ---------------------------------------------------------------------------
# Package Builder
# ---------------------------------------------------------------------------

top_left, top_right = st.columns([0.78, 0.22])
with top_left:
    st.markdown("### Package Builder")
    st.caption(
        f"Prices loaded from {'NetSuite (' + STATE_TO_NETSUITE_COL.get(region_key,'Base Price') + ' column)' if netsuite_df is not None else 'fallback defaults'}. "
        "Each delivery can include multiple items. Freight is allocated across products."
    )
with top_right:
    if st.button("+ Add Delivery", type="primary", use_container_width=True):
        add_delivery()
        st.rerun()


all_rows = []

for delivery in list(st.session_state.deliveries):
    st.markdown('<div class="card">', unsafe_allow_html=True)

    h1, h2 = st.columns([0.82, 0.18])
    with h1:
        st.markdown(f'<div class="title">Delivery {delivery["id"]}</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtle">Select items from the price list, enter quantity and discount.</div>', unsafe_allow_html=True)
    with h2:
        if len(st.session_state.deliveries) > 1:
            if st.button("Remove", key=f"remove_delivery_{delivery['id']}", use_container_width=True):
                remove_delivery(delivery["id"])
                st.rerun()

    for idx, product in enumerate(list(delivery["products"])):
        p1, p2, p3, p4, p5, p6 = st.columns([0.26, 0.14, 0.14, 0.14, 0.16, 0.16])

        with p1:
            current_item = product.get("item_name", "")
            if current_item not in item_names:
                current_item = item_names[0] if item_names else ""
            try:
                default_idx = item_names.index(current_item)
            except ValueError:
                default_idx = 0

            selected_item = st.selectbox(
                "Item",
                item_names,
                index=default_idx,
                key=f"item_{delivery['id']}_{idx}",
            )
            product["item_name"] = selected_item
            # Resolve and store price
            resolved_price = resolve_price(selected_item)
            product["rrp_per_m"] = resolved_price

        with p2:
            product["quantity_m"] = st.number_input(
                "Qty m",
                min_value=0.0,
                value=float(product["quantity_m"]),
                step=10.0,
                key=f"qty_{delivery['id']}_{idx}",
            )

        with p3:
            st.metric("Price/m", f"${product['rrp_per_m']:,.2f}")

        with p4:
            st.metric("Cost/m", f"${product['rrp_per_m'] * COST_FACTOR:,.2f}")

        with p5:
            product["discount_pct"] = st.selectbox(
                "Discount",
                DISCOUNT_OPTIONS,
                index=DISCOUNT_OPTIONS.index(product["discount_pct"]),
                key=f"discount_{delivery['id']}_{idx}",
                format_func=lambda x: f"{x}%",
            )

        with p6:
            net = product["rrp_per_m"] * (1 - product["discount_pct"] / 100)
            st.metric("Net/m", f"${net:,.2f}")
            if len(delivery["products"]) > 1:
                if st.button("✕", key=f"remove_product_{delivery['id']}_{idx}", use_container_width=True):
                    remove_product_from_delivery(delivery["id"], idx)
                    st.rerun()

    if st.button("+ Add Item", key=f"add_product_{delivery['id']}", use_container_width=True):
        add_product_to_delivery(delivery["id"])
        st.rerun()

    with st.expander("Freight Settings", expanded=False):
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            delivery["freight_method"] = st.radio(
                "Method", ["Auto calculate", "Manual override"], horizontal=True, key=f"freight_method_{delivery['id']}"
            )
        with f2:
            delivery["trip_type"] = st.radio(
                "Trip", ["Return", "One-way"], horizontal=True, key=f"trip_{delivery['id']}"
            )
        with f3:
            delivery["zone"] = st.selectbox(
                "Zone", list(ZONES.keys()), index=list(ZONES.keys()).index(delivery["zone"]), key=f"zone_{delivery['id']}"
            )
        with f4:
            if st.button("Use Zone km", key=f"use_zone_{delivery['id']}", use_container_width=True):
                delivery["km_one_way"] = float(ZONES[delivery["zone"]])
                st.rerun()

        f5, f6, f7, f8 = st.columns(4)
        with f5:
            delivery["km_one_way"] = st.number_input(
                "One-way km", min_value=0.0, value=float(delivery["km_one_way"]), step=10.0, key=f"km_{delivery['id']}"
            )
        with f6:
            delivery["fleet"] = st.selectbox(
                "Fleet", list(FLEET.keys()), index=list(FLEET.keys()).index(delivery["fleet"]), key=f"fleet_{delivery['id']}"
            )
        with f7:
            delivery["site_hours"] = st.number_input(
                "Site hrs", min_value=0.0, value=float(delivery["site_hours"]), step=0.5, key=f"site_hours_{delivery['id']}"
            )
        with f8:
            if delivery["freight_method"] == "Manual override":
                delivery["manual_freight"] = st.number_input(
                    "Manual freight $", min_value=0.0, value=float(delivery["manual_freight"]), step=50.0, key=f"manual_freight_{delivery['id']}"
                )

    delivery_rows, delivery_freight = calculate_delivery(delivery, global_inputs, region_key)
    all_rows.extend(delivery_rows)

    delivery_revenue = sum(r["Revenue"] for r in delivery_rows)
    delivery_contribution = sum(r["Contribution $"] for r in delivery_rows)
    delivery_margin = safe_divide(delivery_contribution, delivery_revenue)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Revenue", money(delivery_revenue))
    m2.metric("Freight", money(delivery_freight))
    m3.metric("Contribution", money(delivery_contribution))
    m4.metric("Margin", pct(delivery_margin))
    m5.metric("Lines", len(delivery["products"]))

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

detail_df = pd.DataFrame(all_rows)

if detail_df.empty:
    st.warning("Please add at least one product line.")
    st.stop()

total_quantity = detail_df["Quantity m"].sum()
total_rrp_revenue = detail_df["RRP Revenue"].sum()
total_revenue = detail_df["Revenue"].sum()
total_product_cost = detail_df["Product Cost"].sum()
total_freight = detail_df["Freight Allocated"].sum()
total_contribution = detail_df["Contribution $"].sum()

package_margin = safe_divide(total_contribution, total_revenue)
rrp_contribution = detail_df["RRP Contribution $"].sum()
rrp_margin = safe_divide(rrp_contribution, total_rrp_revenue)
weighted_discount = safe_divide(total_rrp_revenue - total_revenue, total_rrp_revenue)
margin_lost = rrp_contribution - total_contribution
margin_lost_pp = (rrp_margin - package_margin) * 100

st.markdown("### Executive Summary")
st.markdown('<div class="card">', unsafe_allow_html=True)

s1, s2, s3, s4, s5 = st.columns(5)
s1.metric("Revenue", money(total_revenue), delta=f"{pct(weighted_discount)} discount")
s2.metric("Contribution", money(total_contribution))
s3.metric("Margin", pct(package_margin))
s4.metric("Margin at Risk", money(margin_lost), delta=f"{margin_lost_pp:.1f} pts")
s5.metric("Freight", money(total_freight))

s6, s7, s8, s9, s10 = st.columns(5)
s6.metric("List Revenue", money(total_rrp_revenue))
s7.metric("Product Cost", money(total_product_cost))
s8.metric("Quantity", f"{total_quantity:,.0f}m")
s9.metric("List Margin", pct(rrp_margin))
s10.metric("Lines", len(detail_df))

if package_margin < risk_margin:
    risk_class, risk_title = "bad", "High margin risk"
    risk_message = "Below the high-risk threshold. Review discounting, freight recovery or cost."
elif package_margin < target_margin:
    risk_class, risk_title = "watch", "Margin below target"
    risk_message = "Above the risk floor but below target. Check whether the discount is justified."
else:
    risk_class, risk_title = "good", "Healthy package margin"
    risk_message = "Above the target contribution margin."

st.markdown(
    f"""
<div class="risk-box {risk_class}">
    <b>{risk_title}</b><br>
    {risk_message}
    At list price, margin would be <b>{rrp_margin:.1%}</b>. 
    After discount and freight, it is <b>{package_margin:.1%}</b>. 
    Contribution at risk is <b>{money(margin_lost)}</b>.
</div>
""",
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Competitor comparison
# ---------------------------------------------------------------------------

st.markdown("### Competitor Intelligence")
st.markdown('<div class="card">', unsafe_allow_html=True)

if competitor_df is not None:
    competitor_intel = get_competitor_prices(competitor_df, region_key)

    if competitor_intel:
        peer_df = build_peer_comparison(detail_df, competitor_intel, total_revenue, total_freight)

        st.caption(
            f"Competitor prices filtered to {region_key} / {', '.join(COMPETITOR_STATE_MAP.get(region_key, [region_key]))} region. "
            f"{sum(d['entries'] for d in competitor_intel.values())} records used."
        )

        st.dataframe(
            peer_df.style.format(
                {
                    "Avg $/m": "${:,.2f}",
                    "Est. Product Package": "${:,.0f}",
                    "Peer Freight (est.)": "${:,.0f}",
                    "Est. Total Package": "${:,.0f}",
                    "Data Points": "{:.0f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        comp_packages = peer_df.loc[peer_df["Supplier"] != "Atlan Proposed Package", "Est. Total Package"]
        if not comp_packages.empty:
            peer_avg = comp_packages.mean()
            gap = safe_divide(total_revenue - peer_avg, peer_avg)
            if gap > 0.10:
                st.warning(f"Atlan is priced {gap:.1%} above the competitor average package.")
            elif gap < -0.05:
                st.success(f"Atlan is priced {abs(gap):.1%} below the competitor average package.")
            else:
                st.info(f"Atlan is broadly market-aligned at {gap:.1%} versus the competitor average.")

        with st.expander("Raw competitor records for this region"):
            state_vals = COMPETITOR_STATE_MAP.get(region_key, [region_key])
            st.dataframe(
                competitor_df[competitor_df["State"].str.strip().isin(state_vals)],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info(f"No competitor records found for region **{region_key}** in the uploaded file.")
else:
    st.info("Upload the Competitor Intelligence file in the sidebar to enable peer comparison.")

st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Detailed output
# ---------------------------------------------------------------------------

with st.expander("Detailed Product Output", expanded=False):
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

csv = detail_df.to_csv(index=False)
st.download_button(
    label="Download pricing output",
    data=csv,
    file_name="atlan_pricing_output.csv",
    mime="text/csv",
    use_container_width=True,
)
