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

COST_FACTOR = 0.65  # product cost as fraction of RRP/sell price


# ---------------------------------------------------------------------------
# Built-in price list (ATF product range)
# ---------------------------------------------------------------------------

_BUILTIN_PRICE_DATA = [
    {"Internal ID": 8766,  "Name": "ATF1050-CAP",         "Type": "Assembly",        "Display Name": "AtlanFlow 1050mm SN8 Cap Fitting",              "Base Price": None,   "NSW / ACT": 9279,   "NT": 9279,   "QLD": 9279,   "SA": 9279,   "TAS": 9279,   "VIC": 9279,   "WA": 9279},
    {"Internal ID": 8175,  "Name": "ATF1050.8",            "Type": "Assembly",        "Display Name": "AtlanFlow DN1050 SN8",                          "Base Price": 2091.7, "NSW / ACT": 2099.6, "NT": 2099.6, "QLD": 2091.7, "SA": 2191,   "TAS": 2191,   "VIC": 2091.7, "WA": None},
    {"Internal ID": 10190, "Name": "ATF1050.8-K",          "Type": "Kit/Package",     "Display Name": "ATF1050.8-K",                                   "Base Price": 1500,   "NSW / ACT": 1600,   "NT": 1576,   "QLD": 1546,   "SA": 2748,   "TAS": 2134,   "VIC": 8787,   "WA": None},
    {"Internal ID": 9942,  "Name": "ATF1050.8-PERF",       "Type": "Assembly",        "Display Name": "DN1050 SN8 Atlan Flow Perforated",              "Base Price": 199.9,  "NSW / ACT": 157.8,  "NT": 157.8,  "QLD": 199.9,  "SA": 211,    "TAS": 211,    "VIC": 119.9,  "WA": None},
    {"Internal ID": 8244,  "Name": "ATF1050.GASKET",       "Type": "Inventory Item",  "Display Name": "DN1050 GASKET",                                 "Base Price": 150,    "NSW / ACT": 150,    "NT": 150,    "QLD": 150,    "SA": 150,    "TAS": 150,    "VIC": 150,    "WA": 150},
    {"Internal ID": 8713,  "Name": "ATF110-45",            "Type": "Assembly",        "Display Name": "AtlanFlow 110mm SN8 45 Degree Fitting",         "Base Price": 309,    "NSW / ACT": 309,    "NT": 309,    "QLD": 309,    "SA": 309,    "TAS": 309,    "VIC": 309,    "WA": 309},
    {"Internal ID": 8714,  "Name": "ATF110-90",            "Type": "Assembly",        "Display Name": "AtlanFlow 110mm SN8 90 Degree Fitting",         "Base Price": 379,    "NSW / ACT": 379,    "NT": 379,    "QLD": 379,    "SA": 379,    "TAS": 379,    "VIC": 379,    "WA": 379},
    {"Internal ID": 8092,  "Name": "ATF110.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN110 SN8",                           "Base Price": 40,     "NSW / ACT": 39,     "NT": 39,     "QLD": 40,     "SA": 40,     "TAS": 40,     "VIC": 40,     "WA": 40},
    {"Internal ID": 8484,  "Name": "ATF110.8-PERF",        "Type": "Assembly",        "Display Name": "DN110 SN8 Atlan Flow Perforated",               "Base Price": 40,     "NSW / ACT": 39,     "NT": 39,     "QLD": 40,     "SA": 40,     "TAS": 40,     "VIC": 40,     "WA": 40},
    {"Internal ID": 8362,  "Name": "ATF110.GASKET",        "Type": "Inventory Item",  "Display Name": "DN110 GASKET",                                  "Base Price": 15,     "NSW / ACT": 15,     "NT": 15,     "QLD": 15,     "SA": 15,     "TAS": 15,     "VIC": 15,     "WA": 15},
    {"Internal ID": 9909,  "Name": "ATF1200.8",            "Type": "Assembly",        "Display Name": "AtlanFlow 1200 SN8",                            "Base Price": None,   "NSW / ACT": None,   "NT": None,   "QLD": None,   "SA": None,   "TAS": None,   "VIC": None,   "WA": None},
    {"Internal ID": 8718,  "Name": "ATF160-45",            "Type": "Assembly",        "Display Name": "AtlanFlow 160mm SN8 45 Degree Fitting",         "Base Price": 342,    "NSW / ACT": 342,    "NT": 342,    "QLD": 342,    "SA": 342,    "TAS": 342,    "VIC": 342,    "WA": 342},
    {"Internal ID": 8719,  "Name": "ATF160-90",            "Type": "Assembly",        "Display Name": "AtlanFlow 160mm SN8 90 Degree Fitting",         "Base Price": 432,    "NSW / ACT": 432,    "NT": 432,    "QLD": 432,    "SA": 432,    "TAS": 432,    "VIC": 432,    "WA": 432},
    {"Internal ID": 8098,  "Name": "ATF160.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN160 SN8",                           "Base Price": 73,     "NSW / ACT": 45.8,   "NT": 45.8,   "QLD": 73,     "SA": 70,     "TAS": 70,     "VIC": 73,     "WA": 73},
    {"Internal ID": 8483,  "Name": "ATF160.8-PERF",        "Type": "Assembly",        "Display Name": "DN160 SN8 Atlan Flow Perforated",               "Base Price": 73,     "NSW / ACT": 45.8,   "NT": 45.8,   "QLD": 73,     "SA": 70,     "TAS": 70,     "VIC": 73,     "WA": 73},
    {"Internal ID": 8321,  "Name": "ATF160.GASKET",        "Type": "Inventory Item",  "Display Name": "DN160 GASKET",                                  "Base Price": 20,     "NSW / ACT": 20,     "NT": 20,     "QLD": 20,     "SA": 20,     "TAS": 20,     "VIC": 20,     "WA": 20},
    {"Internal ID": 8723,  "Name": "ATF225-45",            "Type": "Assembly",        "Display Name": "AtlanFlow 225mm SN8 45 Degree Fitting",         "Base Price": 454,    "NSW / ACT": 454,    "NT": 454,    "QLD": 454,    "SA": 454,    "TAS": 454,    "VIC": 454,    "WA": 454},
    {"Internal ID": 8724,  "Name": "ATF225-90",            "Type": "Assembly",        "Display Name": "AtlanFlow 225mm SN8 90 Degree Fitting",         "Base Price": 554,    "NSW / ACT": 554,    "NT": 554,    "QLD": 554,    "SA": 554,    "TAS": 554,    "VIC": 554,    "WA": 554},
    {"Internal ID": 7943,  "Name": "ATF225.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN225 SN8",                           "Base Price": 109.8,  "NSW / ACT": 99.5,   "NT": 99.5,   "QLD": 109.8,  "SA": 138,    "TAS": 138,    "VIC": 109.8,  "WA": 109.8},
    {"Internal ID": 9170,  "Name": "ATF225.8-PERF",        "Type": "Assembly",        "Display Name": "DN225 SN8 Atlan Flow Perforated",               "Base Price": 109.8,  "NSW / ACT": 99.5,   "NT": 99.5,   "QLD": 109.8,  "SA": 138,    "TAS": 138,    "VIC": 109.8,  "WA": 109.8},
    {"Internal ID": 8245,  "Name": "ATF225.GASKET",        "Type": "Inventory Item",  "Display Name": "DN225 GASKET",                                  "Base Price": 25,     "NSW / ACT": 25,     "NT": 25,     "QLD": 25,     "SA": 25,     "TAS": 25,     "VIC": 25,     "WA": 25},
    {"Internal ID": 8728,  "Name": "ATF300-45",            "Type": "Assembly",        "Display Name": "AtlanFlow 300mm SN8 45 Degree Fitting",         "Base Price": 619,    "NSW / ACT": 619,    "NT": 619,    "QLD": 619,    "SA": 619,    "TAS": 619,    "VIC": 619,    "WA": 619},
    {"Internal ID": 8729,  "Name": "ATF300-90",            "Type": "Assembly",        "Display Name": "AtlanFlow 300mm SN8 90 Degree Fitting",         "Base Price": 782,    "NSW / ACT": 782,    "NT": 782,    "QLD": 782,    "SA": 782,    "TAS": 782,    "VIC": 782,    "WA": 782},
    {"Internal ID": 7969,  "Name": "ATF300.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN300 SN8",                           "Base Price": 199.9,  "NSW / ACT": 157.8,  "NT": 157.8,  "QLD": 199.9,  "SA": 211,    "TAS": 211,    "VIC": 199.9,  "WA": 199.9},
    {"Internal ID": 8546,  "Name": "ATF300.8-PERF",        "Type": "Assembly",        "Display Name": "DN300 SN8 Atlan Flow Perforated",               "Base Price": 199.9,  "NSW / ACT": 157.8,  "NT": 157.8,  "QLD": 199.9,  "SA": 211,    "TAS": 211,    "VIC": 119.9,  "WA": 199.9},
    {"Internal ID": 7994,  "Name": "ATF300.GASKET",        "Type": "Inventory Item",  "Display Name": "DN300 GASKET",                                  "Base Price": 30,     "NSW / ACT": 30,     "NT": 30,     "QLD": 30,     "SA": 30,     "TAS": 30,     "VIC": 30,     "WA": 30},
    {"Internal ID": 8733,  "Name": "ATF375-45",            "Type": "Assembly",        "Display Name": "AtlanFlow 375mm SN8 45 Degree Fitting",         "Base Price": 829,    "NSW / ACT": 829,    "NT": 829,    "QLD": 829,    "SA": 829,    "TAS": 829,    "VIC": 829,    "WA": 829},
    {"Internal ID": 8734,  "Name": "ATF375-90",            "Type": "Assembly",        "Display Name": "AtlanFlow 375mm SN8 90 Degree Fitting",         "Base Price": 1049,   "NSW / ACT": 1049,   "NT": 1049,   "QLD": 1049,   "SA": 1049,   "TAS": 1049,   "VIC": 1049,   "WA": 1049},
    {"Internal ID": 8017,  "Name": "ATF375.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN375 SN8",                           "Base Price": 317.8,  "NSW / ACT": 231.6,  "NT": 231.6,  "QLD": 317.8,  "SA": 345,    "TAS": 345,    "VIC": 317.8,  "WA": 317.8},
    {"Internal ID": 9175,  "Name": "ATF375.8-PERF",        "Type": "Assembly",        "Display Name": "DN375 SN8 Atlan Flow Perforated",               "Base Price": 317.8,  "NSW / ACT": 231.6,  "NT": 231.6,  "QLD": 317.8,  "SA": 345,    "TAS": 345,    "VIC": 317.8,  "WA": 317.8},
    {"Internal ID": 8238,  "Name": "ATF375.GASKET",        "Type": "Inventory Item",  "Display Name": "DN375 GASKET",                                  "Base Price": 35,     "NSW / ACT": 35,     "NT": 35,     "QLD": 35,     "SA": 35,     "TAS": 35,     "VIC": 35,     "WA": 35},
    {"Internal ID": 8738,  "Name": "ATF450-45",            "Type": "Assembly",        "Display Name": "AtlanFlow 450mm SN8 45 Degree Fitting",         "Base Price": 1151,   "NSW / ACT": 1151,   "NT": 1151,   "QLD": 1151,   "SA": 1151,   "TAS": 1151,   "VIC": 1151,   "WA": 1151},
    {"Internal ID": 8739,  "Name": "ATF450-90",            "Type": "Assembly",        "Display Name": "AtlanFlow 450mm SN8 90 Degree Fitting",         "Base Price": 1401,   "NSW / ACT": 1401,   "NT": 1401,   "QLD": 1401,   "SA": 1401,   "TAS": 1401,   "VIC": 1401,   "WA": 1401},
    {"Internal ID": 8024,  "Name": "ATF450.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN450 SN8",                           "Base Price": 411.4,  "NSW / ACT": 377.1,  "NT": 377.1,  "QLD": 411.4,  "SA": 485,    "TAS": 485,    "VIC": 411.4,  "WA": 411.4},
    {"Internal ID": 9171,  "Name": "ATF450.8-PERF",        "Type": "Assembly",        "Display Name": "DN450 SN8 Atlan Flow Perforated",               "Base Price": 411.4,  "NSW / ACT": 377.1,  "NT": 377.1,  "QLD": 411.4,  "SA": 485,    "TAS": 485,    "VIC": 411.4,  "WA": 411.4},
    {"Internal ID": 8239,  "Name": "ATF450.GASKET",        "Type": "Inventory Item",  "Display Name": "DN450 GASKET",                                  "Base Price": 40,     "NSW / ACT": 40,     "NT": 40,     "QLD": 40,     "SA": 40,     "TAS": 40,     "VIC": 40,     "WA": 40},
    {"Internal ID": 8743,  "Name": "ATF525-45",            "Type": "Assembly",        "Display Name": "AtlanFlow 525mm SN8 45 Degree Fitting",         "Base Price": 1478,   "NSW / ACT": 1478,   "NT": 1478,   "QLD": 1478,   "SA": 1478,   "TAS": 1478,   "VIC": 1478,   "WA": 1478},
    {"Internal ID": 8744,  "Name": "ATF525-90",            "Type": "Assembly",        "Display Name": "AtlanFlow 525mm SN8 90 Degree Fitting",         "Base Price": 1750,   "NSW / ACT": 1750,   "NT": 1750,   "QLD": 1750,   "SA": 1750,   "TAS": 1750,   "VIC": 1750,   "WA": 1750},
    {"Internal ID": 8103,  "Name": "ATF525.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN525 SN8",                           "Base Price": 527,    "NSW / ACT": 477.1,  "NT": 477.1,  "QLD": 527,    "SA": 648,    "TAS": 648,    "VIC": 527,    "WA": 527},
    {"Internal ID": 9172,  "Name": "ATF525.8-PERF",        "Type": "Assembly",        "Display Name": "DN525 SN8 Atlan Flow Perforated",               "Base Price": 527,    "NSW / ACT": 477.1,  "NT": 477.1,  "QLD": 527,    "SA": 648,    "TAS": 648,    "VIC": 527,    "WA": 527},
    {"Internal ID": 8240,  "Name": "ATF525.GASKET",        "Type": "Inventory Item",  "Display Name": "DN525 GASKET",                                  "Base Price": 45,     "NSW / ACT": 45,     "NT": 45,     "QLD": 45,     "SA": 45,     "TAS": 45,     "VIC": 45,     "WA": 45},
    {"Internal ID": 8074,  "Name": "ATF600.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN600 SN8",                           "Base Price": 773.1,  "NSW / ACT": 692.2,  "NT": 692.2,  "QLD": 773.1,  "SA": 820,    "TAS": 820,    "VIC": 773.1,  "WA": 773.1},
    {"Internal ID": 9173,  "Name": "ATF600.8-PERF",        "Type": "Assembly",        "Display Name": "DN600 SN8 Atlan Flow Perforated",               "Base Price": 773.1,  "NSW / ACT": 692.2,  "NT": 692.2,  "QLD": 773.1,  "SA": 820,    "TAS": 820,    "VIC": 773.1,  "WA": 773.1},
    {"Internal ID": 8241,  "Name": "ATF600.GASKET",        "Type": "Inventory Item",  "Display Name": "DN600 GASKET",                                  "Base Price": 50,     "NSW / ACT": 50,     "NT": 50,     "QLD": 50,     "SA": 50,     "TAS": 50,     "VIC": 50,     "WA": 50},
    {"Internal ID": 8193,  "Name": "ATF750.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN750 SN8",                           "Base Price": 1012.3, "NSW / ACT": 1098.1, "NT": 1098.1, "QLD": 1012.3, "SA": 1182,   "TAS": 1182,   "VIC": 1012.3, "WA": 1012.3},
    {"Internal ID": 9174,  "Name": "ATF750.8-PERF",        "Type": "Assembly",        "Display Name": "DN750 SN8 Atlan Flow Perforated",               "Base Price": 1012.3, "NSW / ACT": 1098.1, "NT": 1098.1, "QLD": 1012.3, "SA": 1182,   "TAS": 1182,   "VIC": 1012.3, "WA": 1012.3},
    {"Internal ID": 8242,  "Name": "ATF750.GASKET",        "Type": "Inventory Item",  "Display Name": "DN750 GASKET",                                  "Base Price": 85,     "NSW / ACT": 85,     "NT": 85,     "QLD": 85,     "SA": 85,     "TAS": 85,     "VIC": 85,     "WA": 85},
    {"Internal ID": 8154,  "Name": "ATF900.8",             "Type": "Assembly",        "Display Name": "AtlanFlow DN900 SN8",                           "Base Price": 1201.9, "NSW / ACT": 1629.8, "NT": 1629.8, "QLD": 1201.9, "SA": 1493,   "TAS": 1493,   "VIC": 1201.9, "WA": 1201.9},
    {"Internal ID": 8243,  "Name": "ATF900.GASKET",        "Type": "Inventory Item",  "Display Name": "DN900 GASKET",                                  "Base Price": 95,     "NSW / ACT": 95,     "NT": 95,     "QLD": 95,     "SA": 95,     "TAS": 95,     "VIC": 95,     "WA": 95},
    {"Internal ID": 8331,  "Name": "ATFJ100-225/300",      "Type": "Inventory Item",  "Display Name": "DN100 Joiner to 225/300 SN8 Atlan Flow",        "Base Price": 45,     "NSW / ACT": 45,     "NT": 45,     "QLD": 45,     "SA": 45,     "TAS": 45,     "VIC": 45,     "WA": 45},
    {"Internal ID": 8333,  "Name": "ATFJ100-375/450/525",  "Type": "Inventory Item",  "Display Name": "DN100 Joiner to 375/450/525 SN8 Atlan Flow",    "Base Price": 52,     "NSW / ACT": 52,     "NT": 52,     "QLD": 52,     "SA": 52,     "TAS": 52,     "VIC": 52,     "WA": 52},
    {"Internal ID": 8334,  "Name": "ATFJ150-300/375",      "Type": "Inventory Item",  "Display Name": "DN150 Joiner to 300/375 SN8 Atlan Flow",        "Base Price": 95,     "NSW / ACT": 95,     "NT": 95,     "QLD": 95,     "SA": 95,     "TAS": 95,     "VIC": 95,     "WA": 95},
    {"Internal ID": 8336,  "Name": "ATFJ150-375/450/525",  "Type": "Inventory Item",  "Display Name": "DN150 Joiner to 375/450/525 SN8 Atlan Flow",    "Base Price": 132,    "NSW / ACT": 132,    "NT": 132,    "QLD": 132,    "SA": 132,    "TAS": 132,    "VIC": 132,    "WA": 132},
    {"Internal ID": 8335,  "Name": "ATFJ150-600/750/900",  "Type": "Inventory Item",  "Display Name": "DN150 Joiner to 600/750/900 SN8 Atlan Flow",    "Base Price": 145,    "NSW / ACT": 145,    "NT": 145,     "QLD": 145,    "SA": 145,    "TAS": 145,    "VIC": 145,    "WA": 145},
]

BUILTIN_NETSUITE_DF = pd.DataFrame(_BUILTIN_PRICE_DATA)


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
    df = _read_spreadsheet(file_bytes, filename)
    df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_data(show_spinner=False)
def load_competitor(file_bytes: bytes, filename: str) -> pd.DataFrame:
    df = _read_spreadsheet(file_bytes, filename)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def get_item_price(netsuite_df: pd.DataFrame, item_name: str, region_key: str) -> Optional[float]:
    col = STATE_TO_NETSUITE_COL.get(region_key)
    if col is None or col not in netsuite_df.columns:
        col = "Base Price"
    if col not in netsuite_df.columns:
        return None

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
        v = float(val)
        if pd.isna(v):
            raise ValueError
        return v
    except (ValueError, TypeError):
        try:
            base = rows.iloc[0].get("Base Price", None)
            v = float(base)
            return None if pd.isna(v) else v
        except (ValueError, TypeError):
            return None


def get_competitor_prices(competitor_df: pd.DataFrame, region_key: str) -> Dict[str, pd.DataFrame]:
    import re
    state_vals = COMPETITOR_STATE_MAP.get(region_key, [region_key])
    mask = competitor_df["State"].str.strip().isin(state_vals)
    subset = competitor_df[mask].copy()

    if subset.empty:
        return {}

    subset["price"] = pd.to_numeric(subset.get("Price", pd.Series(dtype=float)), errors="coerce")

    def size_from_ref(val: str) -> float:
        m = re.search(r"ATF(\d{2,4})", str(val).upper())
        if m:
            return float(m.group(1))
        m2 = re.search(r"(\d{2,4})", str(val))
        return float(m2.group(1)) if m2 else float("nan")

    ref_col = "Atlan Reference" if "Atlan Reference" in subset.columns else None
    pipe_col = "PipeSize" if "PipeSize" in subset.columns else ("Pipe Size" if "Pipe Size" in subset.columns else None)

    subset["pipe_size_mm"] = float("nan")
    if ref_col:
        subset["pipe_size_mm"] = subset[ref_col].apply(size_from_ref)
    if pipe_col:
        from_pipe = pd.to_numeric(
            subset[pipe_col].astype(str).str.replace(r"[^\d.]", "", regex=True), errors="coerce"
        )
        subset["pipe_size_mm"] = subset["pipe_size_mm"].combine_first(from_pipe)

    subset = subset.dropna(subset=["price"])

    result = {}
    for comp, grp in subset.groupby("Competitor"):
        result[str(comp)] = grp[["pipe_size_mm", "price"]].copy().reset_index(drop=True)
    return result


def closest_competitor_price(comp_df: pd.DataFrame, target_size_mm: float) -> tuple[float, float]:
    sized = comp_df.dropna(subset=["pipe_size_mm"])
    if sized.empty:
        return float(comp_df["price"].iloc[0]), float("nan")
    closest_idx = (sized["pipe_size_mm"] - target_size_mm).abs().idxmin()
    row = sized.loc[closest_idx]
    return float(row["price"]), float(row["pipe_size_mm"])


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
        rrp_per_m = resolve_price(item_name) if item_name else (product.get("rrp_per_m", 0.0) or 0.0)

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
    competitor_intel: Dict[str, pd.DataFrame],
    total_revenue: float,
    total_freight: float,
    peer_freight: Dict[str, float] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if peer_freight is None:
        peer_freight = {}
    import re
    total_quantity = detail_df["Quantity m"].sum()

    def extract_size(item_name: str) -> float:
        m = re.search(r"(\d{2,4})", str(item_name))
        return float(m.group(1)) if m else float("nan")

    detail_df = detail_df.copy()
    detail_df["_size_mm"] = detail_df["Item"].apply(extract_size)

    atlan_package = sum(line["Net Price / m"] * line["Quantity m"] for _, line in detail_df.iterrows())
    atlan_qty = detail_df["Quantity m"].sum()

    summary_rows = []
    line_rows = []

    for comp_name, comp_df in competitor_intel.items():
        comp_package = 0.0
        for _, line in detail_df.iterrows():
            size_mm = line["_size_mm"]
            qty = line["Quantity m"]
            atlan_net_m = line["Net Price / m"]
            atlan_line_total = atlan_net_m * qty

            comp_price, matched_size = closest_competitor_price(comp_df, size_mm)
            if comp_price is None or pd.isna(comp_price):
                comp_price = 0.0
                matched_size = float("nan")

            comp_line_total = comp_price * qty
            comp_package += comp_line_total

            line_rows.append({
                "Competitor": comp_name,
                "Item": line["Item"],
                "Atlan Size (mm)": size_mm,
                "Comp. Matched Size (mm)": matched_size,
                "Comp. Price": comp_price,
                "Atlan Net $/m": atlan_net_m,
                "Qty m": qty,
                "Comp. Line Total": comp_line_total,
                "Atlan Line Total": atlan_line_total,
                "Line $ Diff": atlan_line_total - comp_line_total,
            })

        comp_freight = peer_freight.get(comp_name, total_freight)
        summary_rows.append({
            "Supplier": comp_name,
            "Product Package": comp_package,
            "Freight": comp_freight,
            "Total Package": comp_package + comp_freight,
            "Avg $/m": safe_divide(comp_package, atlan_qty),
        })

    summary_rows.append({
        "Supplier": "✦ Atlan Proposed",
        "Product Package": atlan_package,
        "Freight": total_freight,
        "Total Package": atlan_package + total_freight,
        "Avg $/m": safe_divide(atlan_package, atlan_qty),
    })

    summary_df = pd.DataFrame(summary_rows).sort_values("Total Package").reset_index(drop=True)
    line_df = pd.DataFrame(line_rows)
    return summary_df, line_df


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
        "NetSuite Price List — optional override (.xlsx / .csv)",
        type=["xlsx", "xls", "csv"],
        key="netsuite_upload",
        help="Upload a fresh NetSuite export to override the built-in ATF price list. Same column format required.",
    )
    competitor_file = st.file_uploader(
        "Competitor Intelligence (.xlsx / .csv)",
        type=["xlsx", "xls", "csv"],
        key="competitor_upload",
        help="Columns: SubmittedBy, State, Competitor, Price/m, etc.",
    )

    if netsuite_file:
        st.session_state["_netsuite_bytes"] = (netsuite_file.read(), netsuite_file.name)
    if competitor_file:
        st.session_state["_competitor_bytes"] = (competitor_file.read(), competitor_file.name)

    # Resolve which NetSuite df to use
    netsuite_df: Optional[pd.DataFrame] = None
    competitor_df: Optional[pd.DataFrame] = None
    netsuite_source = "built-in ATF price list"

    if "_netsuite_bytes" in st.session_state:
        try:
            b, name = st.session_state["_netsuite_bytes"]
            netsuite_df = load_netsuite(b, name)
            netsuite_source = f"uploaded file ({name})"
            st.success(f"✓ NetSuite override loaded — {len(netsuite_df):,} items")
        except Exception as e:
            st.error(f"Failed to load NetSuite file: {e}")
            netsuite_df = BUILTIN_NETSUITE_DF
    else:
        netsuite_df = BUILTIN_NETSUITE_DF
        st.info(f"✓ Using built-in ATF price list ({len(netsuite_df):,} items). Upload a file above to override.")

    if "_competitor_bytes" in st.session_state:
        try:
            b, name = st.session_state["_competitor_bytes"]
            competitor_df = load_competitor(b, name)
            st.success(f"✓ Competitor data loaded — {len(competitor_df):,} records")
        except Exception as e:
            st.error(f"Failed to load competitor file: {e}")

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

price_col = STATE_TO_NETSUITE_COL.get(region_key, "Base Price")
if price_col not in netsuite_df.columns:
    price_col = "Base Price"

name_col = "Display Name" if "Display Name" in netsuite_df.columns else "Name"
price_series = pd.to_numeric(netsuite_df.get(price_col, netsuite_df.get("Base Price", pd.Series(dtype=float))), errors="coerce")
base_series = pd.to_numeric(netsuite_df.get("Base Price", pd.Series(dtype=float)), errors="coerce")
effective_price = price_series.combine_first(base_series)

item_mask = effective_price.notna() & (effective_price > 0)
item_names = netsuite_df.loc[item_mask, name_col].dropna().str.strip().sort_values().tolist()


def resolve_price(item_name: str) -> float:
    """Return sell price per metre for item_name in current region."""
    p = get_item_price(netsuite_df, item_name, region_key)
    return p if p is not None else 0.0


# ---------------------------------------------------------------------------
# Package Builder
# ---------------------------------------------------------------------------

top_left, top_right = st.columns([0.78, 0.22])
with top_left:
    st.markdown("### Package Builder")
    st.caption(
        f"Prices from {netsuite_source} — {STATE_TO_NETSUITE_COL.get(region_key, 'Base Price')} column. "
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
            resolved_price = resolve_price(selected_item)
            product["rrp_per_m"] = resolved_price

        current_price = resolve_price(product["item_name"]) if product.get("item_name") else 0.0
        product["rrp_per_m"] = current_price

        with p2:
            product["quantity_m"] = st.number_input(
                "Qty m",
                min_value=0.0,
                value=float(product["quantity_m"]),
                step=10.0,
                key=f"qty_{delivery['id']}_{idx}",
            )

        with p3:
            st.metric("Price/m", f"${current_price:,.2f}")

        with p4:
            st.metric("Cost/m", f"${current_price * COST_FACTOR:,.2f}")

        with p5:
            product["discount_pct"] = st.selectbox(
                "Discount",
                DISCOUNT_OPTIONS,
                index=DISCOUNT_OPTIONS.index(product["discount_pct"]),
                key=f"discount_{delivery['id']}_{idx}",
                format_func=lambda x: f"{x}%",
            )

        with p6:
            net = current_price * (1 - product["discount_pct"] / 100)
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
        comp_names = list(competitor_intel.keys())

        with st.expander("Peer Freight Assumptions", expanded=False):
            st.caption("Competitor freight defaults to Atlan's calculated freight. Edit each manually if known.")
            peer_freight = {}
            peer_cols = st.columns(len(comp_names))
            for col, comp_name in zip(peer_cols, comp_names):
                with col:
                    peer_freight[comp_name] = st.number_input(
                        comp_name,
                        min_value=0.0,
                        value=float(total_freight),
                        step=50.0,
                        key=f"peer_freight_{comp_name}",
                    )

        summary_df, line_df = build_peer_comparison(
            detail_df, competitor_intel, total_revenue, total_freight, peer_freight
        )

        st.caption(
            f"Competitor prices filtered to {region_key} / {', '.join(COMPETITOR_STATE_MAP.get(region_key, [region_key]))} region. "
            f"{sum(len(d) for d in competitor_intel.values())} records used. "
            f"Product package = competitor Price × your quantity for the closest matching pipe size."
        )

        st.dataframe(
            summary_df.style.format(
                {
                    "Avg $/m": "${:,.2f}",
                    "Product Package": "${:,.0f}",
                    "Freight": "${:,.0f}",
                    "Total Package": "${:,.0f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        comp_packages = summary_df.loc[summary_df["Supplier"] != "✦ Atlan Proposed", "Total Package"]
        if not comp_packages.empty:
            peer_avg = comp_packages.mean()
            gap = safe_divide(total_revenue - peer_avg, peer_avg)
            if gap > 0.10:
                st.warning(f"Atlan is priced {gap:.1%} above the competitor average package.")
            elif gap < -0.05:
                st.success(f"Atlan is priced {abs(gap):.1%} below the competitor average package.")
            else:
                st.info(f"Atlan is broadly market-aligned at {gap:.1%} versus the competitor average.")

        if not line_df.empty:
            with st.expander("Line-by-line competitor breakdown", expanded=False):
                st.caption("For each Atlan line item, the closest matching pipe size in competitor data is used.")
                fmt = {
                    "Atlan Size (mm)": "{:.0f}",
                    "Comp. Matched Size (mm)": "{:.0f}",
                    "Comp. Price": "${:,.2f}",
                    "Atlan Net $/m": "${:,.2f}",
                    "Qty m": "{:,.0f}",
                    "Comp. Line Total": "${:,.0f}",
                    "Atlan Line Total": "${:,.0f}",
                    "Line $ Diff": "${:,.0f}",
                }
                st.dataframe(line_df.style.format(fmt), use_container_width=True, hide_index=True)

        with st.expander("Raw competitor records for this region", expanded=False):
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
