from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import io
import re
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Atlan Pricing Engine", page_icon="💧", layout="wide")


# ============================================================
# CONFIG
# ============================================================

NETSUITE_PRICE_LIST_URL = (
    "https://atlanstormwater.sharepoint.com/sites/Atlan-Stormwater/SP/MFR/"
    "Manage%20Financial%20Resources/PowerBI/NetSuite%20Price%20list.xls"
    "?d=w8e3651f9bd1b4a818d6995a163c4fe2e"
)

COMPETITOR_PRICE_URL = (
    "https://atlanstormwater.sharepoint.com/:x:/s/Atlan-Stormwater/SP/MFR/"
    "IQDJg3lu2-FsQJSd4zop7isvAeCBUaoExJKwlJKcfc9ocOY?e=MH8ZXC"
)


@dataclass(frozen=True)
class Region:
    name: str
    market_factor: float
    freight_factor: float
    target_margin: float
    price_column: str
    notes: str


@dataclass(frozen=True)
class CompetitorAssumption:
    name: str
    positioning: str
    price_factor: float
    freight_factor: float


@dataclass(frozen=True)
class Fleet:
    name: str
    litres_per_100km: float
    maintenance_per_km: float


REGIONS: Dict[str, Region] = {
    "QLD": Region("Queensland", 0.95, 1.05, 0.24, "QLD", "Competitive market with stronger price pressure."),
    "NT": Region("Northern Territory", 1.05, 1.20, 0.35, "NT", "Remote market with freight exposure."),
    "VIC": Region("Victoria", 1.00, 1.00, 0.30, "VIC", "Balanced market with room for value-led pricing."),
    "NSW": Region("New South Wales", 0.97, 1.10, 0.40, "NSW / ACT", "High-volume market with active peer competition."),
    "WA": Region("Western Australia", 1.05, 1.18, 0.35, "WA", "Higher freight exposure and supply cost."),
    "SA": Region("South Australia", 1.02, 1.12, 0.32, "SA", "Moderate pricing pressure with freight sensitivity."),
    "TAS": Region("Tasmania", 1.06, 1.30, 0.35, "TAS", "Freight-sensitive market with delivery complexity."),
}

FALLBACK_COMPETITORS: List[CompetitorAssumption] = [
    CompetitorAssumption("Competitor A", "Aggressive / low-cost", 0.88, 0.95),
    CompetitorAssumption("Competitor B", "Market average", 1.00, 1.00),
    CompetitorAssumption("Competitor C", "Premium supplier", 1.16, 1.10),
    CompetitorAssumption("Competitor D", "Regional player", 0.96, 0.90),
    CompetitorAssumption("Competitor E", "Import / price-led", 0.82, 1.15),
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


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
<style>
.stApp { background: #F4F7FB; }

.block-container {
    max-width: 1550px;
    padding-top: 0.8rem;
    padding-bottom: 1rem;
}

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

.card {
    background: white;
    border: 1px solid rgba(7,27,58,0.06);
    border-radius: 18px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 6px 18px rgba(7,27,58,0.04);
}

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

.good { background: #ECFDF3; }
.watch { background: #FFF7E6; }
.bad { background: #FFF1F1; }

.risk-box {
    border-radius: 16px;
    padding: 14px 16px;
    margin-top: 12px;
    border: 1px solid rgba(7,27,58,0.08);
    font-size: 12px;
}

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
    font-size: 21px;
    font-weight: 850;
    color: #071B3A;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# GENERIC HELPERS
# ============================================================

def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def safe_divide(a: float, b: float) -> float:
    return a / b if b else 0.0


def clean_money_value(value) -> Optional[float]:
    if value is None or pd.isna(value):
        return None

    value = str(value)
    value = value.replace("$", "").replace(",", "").strip()

    if value == "":
        return None

    try:
        return float(value)
    except ValueError:
        return None


def extract_pipe_size(text: str) -> Optional[int]:
    if not text:
        return None

    text = str(text).upper()

    match = re.search(r"(\d{2,4})\s*MM", text)

    if match:
        return int(match.group(1))

    match = re.search(r"ATF(\d{2,4})", text)

    if match:
        return int(match.group(1))

    return None


def normalise_state(value: str) -> str:
    return str(value).upper().strip()


def state_matches(source_state: str, region_key: str) -> bool:
    source_state = normalise_state(source_state)

    if region_key in source_state:
        return True

    if region_key == "NSW" and ("NSW" in source_state or "ACT" in source_state):
        return True

    if region_key == "QLD" and ("QLD" in source_state or "NT" in source_state):
        return True

    if region_key == "NT" and ("NT" in source_state or "QLD" in source_state):
        return True

    return False


# ============================================================
# FILE LOADERS
# ============================================================

def parse_xml_spreadsheet(file_bytes: bytes) -> pd.DataFrame:
    ns = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}

    root = ET.fromstring(file_bytes)
    worksheet = root.find("ss:Worksheet", ns)

    if worksheet is None:
        raise ValueError("No worksheet found in XML spreadsheet.")

    table = worksheet.find("ss:Table", ns)

    if table is None:
        raise ValueError("No table found in XML spreadsheet.")

    rows = table.findall("ss:Row", ns)
    output_rows = []

    for row in rows:
        row_values = []
        current_col = 0

        for cell in row.findall("ss:Cell", ns):
            index_attr = cell.attrib.get("{urn:schemas-microsoft-com:office:spreadsheet}Index")

            if index_attr:
                target_col = int(index_attr) - 1
                while current_col < target_col:
                    row_values.append(None)
                    current_col += 1

            data = cell.find("ss:Data", ns)
            row_values.append(data.text if data is not None else None)
            current_col += 1

        output_rows.append(row_values)

    if not output_rows:
        return pd.DataFrame()

    headers = output_rows[0]
    data = output_rows[1:]
    max_cols = len(headers)

    clean_rows = []
    for row in data:
        row = row[:max_cols] + [None] * max(0, max_cols - len(row))
        clean_rows.append(row)

    return pd.DataFrame(clean_rows, columns=headers)


def load_excel_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    stripped = file_bytes[:300].lstrip()

    if stripped.startswith(b"<?xml") or stripped.startswith(b"<Workbook"):
        df = parse_xml_spreadsheet(file_bytes)
    else:
        df = pd.read_excel(io.BytesIO(file_bytes))

    df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_data(show_spinner=False)
def load_excel_from_url(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()

    if "text/html" in content_type:
        raise ValueError(
            "SharePoint returned an HTML page instead of the Excel file. "
            "Upload the file manually or use a direct download link."
        )

    return load_excel_from_bytes(response.content)


# ============================================================
# PRICE LIST PREP
# ============================================================

def prepare_pipe_price_list(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    for col in [
        "Internal ID",
        "Name",
        "Type",
        "Display Name",
        "Base Price",
        "NSW / ACT",
        "NT",
        "QLD",
        "SA",
        "TAS",
        "VIC",
        "WA",
    ]:
        if col not in df.columns:
            df[col] = None

    for col in ["Base Price", "NSW / ACT", "NT", "QLD", "SA", "TAS", "VIC", "WA"]:
        df[col] = df[col].apply(clean_money_value)

    df["Name"] = df["Name"].fillna("").astype(str)
    df["Display Name"] = df["Display Name"].fillna("").astype(str)
    df["Type"] = df["Type"].fillna("").astype(str)

    df["Search Text"] = (
        df["Name"].astype(str)
        + " | "
        + df["Display Name"].astype(str)
        + " | "
        + df["Type"].astype(str)
    )

    df["Pipe Size"] = df["Search Text"].apply(extract_pipe_size)

    pipe_df = df[
        df["Search Text"].str.contains("PIPE|ATF", case=False, na=False)
    ].copy()

    exclusions = "FLANGE|BEND|TEE|COUPLER|REDUCER|GASKET|GRATE|CAP|LID|RISER|ADAPTOR|ADAPTER"
    pipe_df = pipe_df[
        ~pipe_df["Search Text"].str.contains(exclusions, case=False, na=False)
    ].copy()

    pipe_df["Item Label"] = (
        pipe_df["Name"].astype(str)
        + " — "
        + pipe_df["Display Name"].astype(str)
    )

    pipe_df = pipe_df.sort_values(["Pipe Size", "Name"], na_position="last").reset_index(drop=True)

    return pipe_df


def get_state_price(row: pd.Series, region_key: str) -> float:
    state_col = REGIONS[region_key].price_column

    state_price = clean_money_value(row.get(state_col))
    base_price = clean_money_value(row.get("Base Price"))

    if state_price is not None:
        return float(state_price)

    if base_price is not None:
        return float(base_price)

    return 0.0


def prepare_competitor_prices(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    required_cols = [
        "SubmittedBy",
        "State",
        "SubmissionDate",
        "Atlan Reference",
        "Competitor",
        "PipeSize",
        "Length",
        "Price",
        "ApprovedBy",
        "ApprovalDate",
        "Price/m",
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    df["State"] = df["State"].astype(str).str.upper().str.strip()
    df["Competitor"] = df["Competitor"].astype(str).str.strip()
    df["Atlan Reference"] = df["Atlan Reference"].astype(str).str.upper().str.strip()
    df["PipeSize"] = df["PipeSize"].astype(str).str.upper().str.strip()

    df["Length"] = pd.to_numeric(df["Length"], errors="coerce")
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    df["Price/m"] = pd.to_numeric(df["Price/m"], errors="coerce")

    df["Competitor Price / m"] = df["Price/m"]

    df.loc[
        df["Competitor Price / m"].isna()
        & df["Price"].notna()
        & df["Length"].notna()
        & (df["Length"] != 0),
        "Competitor Price / m",
    ] = df["Price"] / df["Length"]

    df["Competitor Pipe Size"] = df["Atlan Reference"].apply(extract_pipe_size)
    df.loc[df["Competitor Pipe Size"].isna(), "Competitor Pipe Size"] = df["PipeSize"].apply(extract_pipe_size)

    df = df[df["Competitor Price / m"].notna()].copy()

    return df.reset_index(drop=True)


# ============================================================
# FREIGHT
# ============================================================

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


# ============================================================
# SESSION HELPERS
# ============================================================

def default_product(pipe_df: pd.DataFrame, region_key: str) -> dict:
    first_row = pipe_df.iloc[0]
    state_price = get_state_price(first_row, region_key)

    return {
        "item_index": 0,
        "internal_id": str(first_row.get("Internal ID", "")),
        "item_name": str(first_row.get("Name", "")),
        "display_name": str(first_row.get("Display Name", "")),
        "pipe_size": first_row.get("Pipe Size"),
        "quantity_m": 100.0,
        "rrp_per_m": float(state_price),
        "price_per_m": float(state_price),
        "cost_per_m": float(state_price * 0.65),
    }


def normalise_product(product: dict, pipe_df: pd.DataFrame, region_key: str) -> None:
    if "item_index" not in product:
        product["item_index"] = 0

    item_index = int(product["item_index"])

    if item_index < 0 or item_index >= len(pipe_df):
        item_index = 0
        product["item_index"] = 0

    selected_row = pipe_df.iloc[item_index]
    state_price = get_state_price(selected_row, region_key)

    product.setdefault("internal_id", str(selected_row.get("Internal ID", "")))
    product.setdefault("item_name", str(selected_row.get("Name", "")))
    product.setdefault("display_name", str(selected_row.get("Display Name", "")))
    product.setdefault("pipe_size", selected_row.get("Pipe Size"))
    product.setdefault("quantity_m", 100.0)
    product.setdefault("rrp_per_m", float(state_price))
    product.setdefault("price_per_m", float(state_price))
    product.setdefault("cost_per_m", float(state_price * 0.65))


def update_product_from_selected_item(product: dict, selected_row: pd.Series, region_key: str) -> None:
    state_price = get_state_price(selected_row, region_key)

    product["internal_id"] = str(selected_row.get("Internal ID", ""))
    product["item_name"] = str(selected_row.get("Name", ""))
    product["display_name"] = str(selected_row.get("Display Name", ""))
    product["pipe_size"] = selected_row.get("Pipe Size")
    product["rrp_per_m"] = float(state_price)
    product["price_per_m"] = float(state_price)
    product["cost_per_m"] = float(state_price * 0.65)


def add_delivery(pipe_df: pd.DataFrame, region_key: str) -> None:
    new_id = st.session_state.next_delivery_id
    st.session_state.next_delivery_id += 1

    st.session_state.deliveries.append(
        {
            "id": new_id,
            "products": [default_product(pipe_df, region_key)],
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


def add_product_to_delivery(delivery_id: int, pipe_df: pd.DataFrame, region_key: str) -> None:
    for delivery in st.session_state.deliveries:
        if delivery["id"] == delivery_id:
            delivery["products"].append(default_product(pipe_df, region_key))
            break


def remove_product_from_delivery(delivery_id: int, product_index: int) -> None:
    for delivery in st.session_state.deliveries:
        if delivery["id"] == delivery_id and len(delivery["products"]) > 1:
            delivery["products"].pop(product_index)
            break


# ============================================================
# CALCULATIONS
# ============================================================

def calculate_delivery(delivery: dict, global_inputs: dict, region_key: str) -> tuple[list[dict], float]:
    if delivery["freight_method"] == "Manual override":
        delivery_freight = float(delivery.get("manual_freight", 0.0))
    else:
        delivery_freight = calculate_freight(
            fleet_name=delivery["fleet"],
            km_one_way=float(delivery["km_one_way"]),
            driver_rate=float(global_inputs["driver_rate"]),
            diesel_price=float(global_inputs["diesel_price"]),
            avg_speed=float(global_inputs["avg_speed"]),
            site_hours=float(delivery["site_hours"]),
            trip_type=delivery["trip_type"],
            region_key=region_key,
        )

    temp_rows = []
    total_delivery_revenue = 0.0

    for product in delivery["products"]:
        quantity_m = float(product.get("quantity_m", 0.0))
        rrp_per_m = float(product.get("rrp_per_m", 0.0))
        price_per_m = float(product.get("price_per_m", 0.0))
        cost_per_m = float(product.get("cost_per_m", 0.0))

        rrp_revenue = rrp_per_m * quantity_m
        revenue = price_per_m * quantity_m
        product_cost = cost_per_m * quantity_m
        price_adjustment_pct = safe_divide(rrp_revenue - revenue, rrp_revenue) * 100

        total_delivery_revenue += revenue

        temp_rows.append(
            {
                "Delivery": f"Delivery {delivery['id']}",
                "Internal ID": product.get("internal_id"),
                "Item Name": product.get("item_name"),
                "Display Name": product.get("display_name"),
                "Pipe Size": product.get("pipe_size"),
                "Quantity m": quantity_m,
                "RRP / m": rrp_per_m,
                "Price / m": price_per_m,
                "Cost / m": cost_per_m,
                "Price Adjustment %": price_adjustment_pct,
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


def get_competitor_price_for_item(
    competitor_rows: pd.DataFrame,
    atlan_reference: str,
    pipe_size,
) -> Optional[float]:
    atlan_reference = str(atlan_reference).upper().strip()

    direct_match = competitor_rows[
        competitor_rows["Atlan Reference"].astype(str).str.upper().str.strip() == atlan_reference
    ]

    if not direct_match.empty:
        return float(direct_match["Competitor Price / m"].mean())

    if pipe_size is not None and not pd.isna(pipe_size):
        size_match = competitor_rows[
            competitor_rows["Competitor Pipe Size"].astype(str) == str(pipe_size)
        ]

        if not size_match.empty:
            return float(size_match["Competitor Price / m"].mean())

    if not competitor_rows.empty:
        return float(competitor_rows["Competitor Price / m"].mean())

    return None


def build_peer_comparison(
    detail_df: pd.DataFrame,
    peer_freight: Dict[str, float],
    region_key: str,
    total_revenue: float,
    total_freight: float,
    competitor_price_df: pd.DataFrame,
) -> pd.DataFrame:
    total_quantity = detail_df["Quantity m"].sum()
    rows = []

    if competitor_price_df is not None and not competitor_price_df.empty:
        comp_df = competitor_price_df[
            competitor_price_df["State"].apply(lambda x: state_matches(x, region_key))
        ].copy()

        for competitor_name in sorted(comp_df["Competitor"].dropna().unique()):
            competitor_rows = comp_df[comp_df["Competitor"] == competitor_name]
            product_package = 0.0

            for _, atlan_row in detail_df.iterrows():
                item_name = str(atlan_row["Item Name"]).upper().strip()
                quantity_m = float(atlan_row["Quantity m"])
                pipe_size = atlan_row.get("Pipe Size")

                competitor_price_m = get_competitor_price_for_item(
                    competitor_rows=competitor_rows,
                    atlan_reference=item_name,
                    pipe_size=pipe_size,
                )

                if competitor_price_m is None:
                    competitor_price_m = 0.0

                product_package += competitor_price_m * quantity_m

            freight = float(peer_freight.get(competitor_name, 0.0))
            total_package = product_package + freight

            rows.append(
                {
                    "Supplier": competitor_name,
                    "Positioning": "Actual submitted competitor price",
                    "Product Package": product_package,
                    "Peer Freight": freight,
                    "Total Package": total_package,
                    "Average $ / m": safe_divide(total_package, total_quantity),
                }
            )

    if not rows:
        region = REGIONS[region_key]

        for competitor in FALLBACK_COMPETITORS:
            product_package = 0.0

            for _, row in detail_df.iterrows():
                product_package += (
                    float(row["RRP / m"])
                    * float(row["Quantity m"])
                    * competitor.price_factor
                    * region.market_factor
                )

            freight = float(peer_freight.get(competitor.name, 0.0))
            total_package = product_package + freight

            rows.append(
                {
                    "Supplier": competitor.name,
                    "Positioning": competitor.positioning,
                    "Product Package": product_package,
                    "Peer Freight": freight,
                    "Total Package": total_package,
                    "Average $ / m": safe_divide(total_package, total_quantity),
                }
            )

    rows.append(
        {
            "Supplier": "Atlan Proposed Package",
            "Positioning": "Current quote",
            "Product Package": total_revenue,
            "Peer Freight": total_freight,
            "Total Package": total_revenue + total_freight,
            "Average $ / m": safe_divide(total_revenue + total_freight, total_quantity),
        }
    )

    return pd.DataFrame(rows).sort_values("Total Package").reset_index(drop=True)


# ============================================================
# APP START
# ============================================================

st.markdown(
    """
<div class="hero">
    <h1>Atlan Stormwater Pricing Engine</h1>
    <p>
        Pipe pricing is sourced from the NetSuite price list by state.
        Competitor pricing is sourced from the submitted competitor price register.
        You can manually override state target margin, price/m and cost/m.
    </p>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR LOAD DATA
# ============================================================

with st.sidebar:
    st.markdown("### NetSuite Price List")

    netsuite_url = st.text_input(
        "SharePoint NetSuite Price List URL",
        value=NETSUITE_PRICE_LIST_URL,
    )

    uploaded_price_list = st.file_uploader(
        "Upload NetSuite price list if SharePoint access fails",
        type=["xls", "xlsx"],
        key="netsuite_price_file",
    )

    try:
        if uploaded_price_list is not None:
            price_df_raw = load_excel_from_bytes(uploaded_price_list.read())
            st.success("NetSuite price list loaded from uploaded file.")
        else:
            price_df_raw = load_excel_from_url(netsuite_url)
            st.success("NetSuite price list loaded from SharePoint URL.")

        pipe_df = prepare_pipe_price_list(price_df_raw)

        if pipe_df.empty:
            st.error("No pipe items found in the NetSuite price list.")
            st.stop()

        st.caption(f"{len(pipe_df):,.0f} pipe-related items loaded.")

    except Exception as e:
        st.error("Could not load the NetSuite price list. Upload the file manually.")
        st.caption(str(e))
        st.stop()

    st.divider()

    st.markdown("### Competitor Price Source")

    competitor_url = st.text_input(
        "SharePoint Competitor Price URL",
        value=COMPETITOR_PRICE_URL,
    )

    uploaded_competitor_file = st.file_uploader(
        "Upload competitor pricing if SharePoint access fails",
        type=["xls", "xlsx"],
        key="competitor_price_file",
    )

    try:
        if uploaded_competitor_file is not None:
            competitor_df_raw = load_excel_from_bytes(uploaded_competitor_file.read())
            competitor_price_df = prepare_competitor_prices(competitor_df_raw)
            st.success("Competitor pricing loaded from uploaded file.")
        else:
            competitor_df_raw = load_excel_from_url(competitor_url)
            competitor_price_df = prepare_competitor_prices(competitor_df_raw)
            st.success("Competitor pricing loaded from SharePoint URL.")

        st.caption(f"{len(competitor_price_df):,.0f} competitor price records loaded.")

    except Exception as e:
        competitor_price_df = pd.DataFrame()
        st.warning("Competitor pricing could not be loaded. Peer comparison will use assumptions.")
        st.caption(str(e))

    st.divider()

    st.markdown("### Market & Region")

    region_key = st.selectbox(
        "Region",
        list(REGIONS.keys()),
        format_func=lambda x: REGIONS[x].name,
    )

    region = REGIONS[region_key]

    st.caption(region.notes)
    st.caption(f"NetSuite price column used: {region.price_column}")

    target_margin = st.number_input(
        "State Target Margin %",
        min_value=0.0,
        max_value=80.0,
        value=float(region.target_margin * 100),
        step=1.0,
    ) / 100

    st.divider()

    st.markdown("### Freight Inputs")

    driver_rate = st.number_input("Driver $ / hr", min_value=0.0, value=100.0, step=5.0)
    diesel_price = st.number_input("Diesel $ / L", min_value=0.0, value=3.00, step=0.10)
    avg_speed = st.number_input("Average km / h", min_value=1.0, value=60.0, step=5.0)

    st.divider()

    st.markdown("### Guardrails")

    risk_margin = st.slider("High-risk margin %", 0, 50, 25, 1) / 100


global_inputs = {
    "driver_rate": driver_rate,
    "diesel_price": diesel_price,
    "avg_speed": avg_speed,
}


# ============================================================
# SESSION INIT
# ============================================================

if "deliveries" not in st.session_state:
    st.session_state.deliveries = []

if "next_delivery_id" not in st.session_state:
    st.session_state.next_delivery_id = 1

if not st.session_state.deliveries:
    add_delivery(pipe_df, region_key)


# ============================================================
# PACKAGE BUILDER
# ============================================================

top_left, top_right = st.columns([0.78, 0.22])

with top_left:
    st.markdown("### Package Builder")
    st.caption(
        "Select pipe item. Price/m is picked from the selected state price column and can be manually changed."
    )

with top_right:
    if st.button("+ Add Delivery", type="primary", use_container_width=True):
        add_delivery(pipe_df, region_key)
        st.rerun()


all_rows = []
item_labels = pipe_df["Item Label"].tolist()

for delivery in list(st.session_state.deliveries):
    st.markdown('<div class="card">', unsafe_allow_html=True)

    h1, h2 = st.columns([0.82, 0.18])

    with h1:
        st.markdown(f'<div class="title">Delivery {delivery["id"]}</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="subtle">Add pipe items, quantity, price/m and cost/m.</div>',
            unsafe_allow_html=True,
        )

    with h2:
        if len(st.session_state.deliveries) > 1:
            if st.button("Remove", key=f"remove_delivery_{delivery['id']}", use_container_width=True):
                remove_delivery(delivery["id"])
                st.rerun()

    for idx, product in enumerate(list(delivery["products"])):
        normalise_product(product, pipe_df, region_key)

        p1, p2, p3, p4, p5, p6, p7, p8 = st.columns(
            [0.25, 0.08, 0.10, 0.11, 0.11, 0.11, 0.12, 0.12]
        )

        old_item_index = int(product["item_index"])

        with p1:
            product["item_index"] = st.selectbox(
                "Pipe Item",
                range(len(item_labels)),
                index=old_item_index,
                key=f"item_{delivery['id']}_{idx}",
                format_func=lambda x: item_labels[x],
            )

        selected_row = pipe_df.iloc[int(product["item_index"])]
        selected_state_price = get_state_price(selected_row, region_key)

        if int(product["item_index"]) != old_item_index:
            update_product_from_selected_item(product, selected_row, region_key)

        with p2:
            product["quantity_m"] = st.number_input(
                "Qty m",
                min_value=0.0,
                value=float(product["quantity_m"]),
                step=10.0,
                key=f"qty_{delivery['id']}_{idx}",
            )

        with p3:
            st.metric(f"{region_key} Price/m", f"${selected_state_price:,.2f}")

        with p4:
            product["rrp_per_m"] = st.number_input(
                "RRP / m",
                min_value=0.0,
                value=float(product["rrp_per_m"]),
                step=5.0,
                key=f"rrp_per_m_{delivery['id']}_{idx}",
            )

        with p5:
            product["price_per_m"] = st.number_input(
                "Price / m",
                min_value=0.0,
                value=float(product["price_per_m"]),
                step=5.0,
                key=f"price_per_m_{delivery['id']}_{idx}",
            )

        with p6:
            product["cost_per_m"] = st.number_input(
                "Cost / m",
                min_value=0.0,
                value=float(product["cost_per_m"]),
                step=5.0,
                key=f"cost_per_m_{delivery['id']}_{idx}",
            )

        with p7:
            price_adjustment = safe_divide(
                product["rrp_per_m"] - product["price_per_m"],
                product["rrp_per_m"],
            ) * 100

            st.metric("Price Adj.", f"{price_adjustment:.1f}%")

            if st.button("Use State Price", key=f"use_state_price_{delivery['id']}_{idx}", use_container_width=True):
                update_product_from_selected_item(product, selected_row, region_key)
                st.rerun()

        with p8:
            if len(delivery["products"]) > 1:
                if st.button("Remove Pipe", key=f"remove_product_{delivery['id']}_{idx}", use_container_width=True):
                    remove_product_from_delivery(delivery["id"], idx)
                    st.rerun()

    if st.button("+ Add Pipe Item", key=f"add_product_{delivery['id']}", use_container_width=True):
        add_product_to_delivery(delivery["id"], pipe_df, region_key)
        st.rerun()

    with st.expander("Freight Settings", expanded=False):
        f1, f2, f3, f4 = st.columns(4)

        with f1:
            delivery["freight_method"] = st.radio(
                "Method",
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
                "Site hrs",
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

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Revenue", money(delivery_revenue))
    m2.metric("Freight", money(delivery_freight))
    m3.metric("Contribution", money(delivery_contribution))
    m4.metric("Margin", pct(delivery_margin))
    m5.metric("Lines", len(delivery["products"]))

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# SUMMARY
# ============================================================

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
weighted_price_adjustment = safe_divide(total_rrp_revenue - total_revenue, total_rrp_revenue)
margin_lost = rrp_contribution - total_contribution
margin_lost_pp = (rrp_margin - package_margin) * 100

st.markdown("### Executive Summary")
st.markdown('<div class="card">', unsafe_allow_html=True)

s1, s2, s3, s4, s5 = st.columns(5)
s1.metric("Revenue", money(total_revenue), delta=f"{pct(weighted_price_adjustment)} price adjustment")
s2.metric("Contribution", money(total_contribution))
s3.metric("Margin", pct(package_margin), delta=f"Target {pct(target_margin)}")
s4.metric("Margin at Risk", money(margin_lost), delta=f"{margin_lost_pp:.1f} pts")
s5.metric("Freight", money(total_freight))

s6, s7, s8, s9, s10 = st.columns(5)
s6.metric("RRP Revenue", money(total_rrp_revenue))
s7.metric("Product Cost", money(total_product_cost))
s8.metric("Quantity", f"{total_quantity:,.0f}m")
s9.metric("RRP Margin", pct(rrp_margin))
s10.metric("Lines", len(detail_df))

if package_margin < risk_margin:
    risk_class = "bad"
    risk_title = "High margin risk"
    risk_message = "Below the high-risk threshold. Review price, cost, freight recovery or price adjustment."
elif package_margin < target_margin:
    risk_class = "watch"
    risk_title = "Margin below state target"
    risk_message = f"Above the risk floor but below the selected {region_key} target margin of {target_margin:.1%}."
else:
    risk_class = "good"
    risk_title = "Healthy package margin"
    risk_message = f"Above the selected {region_key} target contribution margin of {target_margin:.1%}."

st.markdown(
    f"""
<div class="risk-box {risk_class}">
    <b>{risk_title}</b><br>
    {risk_message}
    At RRP, margin would be <b>{rrp_margin:.1%}</b>.
    After price adjustment and freight, it is <b>{package_margin:.1%}</b>.
    Contribution at risk is <b>{money(margin_lost)}</b>.
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# PEER COMPARISON
# ============================================================

st.markdown("### Peer Package Comparison")

if competitor_price_df is not None and not competitor_price_df.empty:
    competitor_names = sorted(
        competitor_price_df[
            competitor_price_df["State"].apply(lambda x: state_matches(x, region_key))
        ]["Competitor"].dropna().unique()
    )
else:
    competitor_names = [c.name for c in FALLBACK_COMPETITORS]

with st.expander("Peer Freight Assumptions", expanded=False):
    st.caption("Edit competitor freight manually. Defaults start at $0 unless you enter an estimate.")

    peer_freight = {}

    if competitor_names:
        peer_cols = st.columns(min(len(competitor_names), 5))

        for i, competitor_name in enumerate(competitor_names):
            with peer_cols[i % len(peer_cols)]:
                peer_freight[competitor_name] = st.number_input(
                    competitor_name,
                    min_value=0.0,
                    value=0.0,
                    step=50.0,
                    key=f"peer_freight_{competitor_name}",
                )
    else:
        peer_freight = {}


peer_df = build_peer_comparison(
    detail_df=detail_df,
    peer_freight=peer_freight,
    region_key=region_key,
    total_revenue=total_revenue,
    total_freight=total_freight,
    competitor_price_df=competitor_price_df,
)

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

peer_only_df = peer_df[peer_df["Supplier"] != "Atlan Proposed Package"].copy()

atlan_total = total_revenue + total_freight

if not peer_only_df.empty:
    peer_avg_total = peer_only_df["Total Package"].mean()
    peer_low_total = peer_only_df["Total Package"].min()
    peer_high_total = peer_only_df["Total Package"].max()

    gap_vs_peer_avg = safe_divide(atlan_total - peer_avg_total, peer_avg_total)
    gap_vs_peer_low = safe_divide(atlan_total - peer_low_total, peer_low_total)
    gap_vs_peer_high = safe_divide(atlan_total - peer_high_total, peer_high_total)

    rank_df = peer_df.sort_values("Total Package").reset_index(drop=True)
    atlan_rank = int(rank_df.index[rank_df["Supplier"] == "Atlan Proposed Package"][0]) + 1
    total_suppliers = len(rank_df)

    st.markdown("#### Atlan vs Peer Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Atlan Package", money(atlan_total))
    c2.metric("Peer Average", money(peer_avg_total), delta=f"{gap_vs_peer_avg:.1%}")
    c3.metric("Peer Low", money(peer_low_total), delta=f"{gap_vs_peer_low:.1%}")
    c4.metric("Peer High", money(peer_high_total), delta=f"{gap_vs_peer_high:.1%}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Market Rank", f"{atlan_rank} of {total_suppliers}")
    c6.metric("Atlan Avg $ / m", f"${safe_divide(atlan_total, total_quantity):,.2f}")
    c7.metric("Peer Avg $ / m", f"${safe_divide(peer_avg_total, total_quantity):,.2f}")
    c8.metric("Atlan Freight", money(total_freight))

    if gap_vs_peer_avg > 0.10:
        st.warning(
            f"Atlan is priced {gap_vs_peer_avg:.1%} above the peer average. "
            "This needs clear premium justification around availability, delivery reliability, quality or service."
        )
    elif gap_vs_peer_avg < -0.05:
        st.success(
            f"Atlan is priced {abs(gap_vs_peer_avg):.1%} below the peer average. "
            "This is commercially competitive, but check margin protection."
        )
    else:
        st.info(
            f"Atlan is broadly market-aligned at {gap_vs_peer_avg:.1%} versus the peer average."
        )

    st.markdown("#### Detailed Peer Gap Analysis")

    peer_summary = peer_df.copy()
    peer_summary["Gap vs Atlan $"] = peer_summary["Total Package"] - atlan_total
    peer_summary["Gap vs Atlan %"] = peer_summary["Gap vs Atlan $"].apply(
        lambda x: safe_divide(x, atlan_total)
    )

    st.dataframe(
        peer_summary.style.format(
            {
                "Product Package": "${:,.0f}",
                "Peer Freight": "${:,.0f}",
                "Total Package": "${:,.0f}",
                "Average $ / m": "${:,.2f}",
                "Gap vs Atlan $": "${:,.0f}",
                "Gap vs Atlan %": "{:.1%}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No peer records available for this state.")

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# DETAILED OUTPUT
# ============================================================

with st.expander("Detailed Product Output", expanded=False):
    st.dataframe(
        detail_df.style.format(
            {
                "Quantity m": "{:,.0f}",
                "RRP / m": "${:,.2f}",
                "Price / m": "${:,.2f}",
                "Cost / m": "${:,.2f}",
                "Price Adjustment %": "{:.1f}%",
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
