from __future__ import annotations

import streamlit as st
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RegionProfile:
    key: str
    name: str
    freight_multiplier: float
    market_pressure: float


@dataclass(frozen=True)
class Competitor:
    name: str
    pricing_position: str
    price_factor: float


REGIONS: Dict[str, RegionProfile] = {
    "QLD": RegionProfile("QLD", "Queensland", 1.05, 0.95),
    "NSW": RegionProfile("NSW", "New South Wales", 1.10, 0.97),
    "VIC": RegionProfile("VIC", "Victoria", 1.08, 1.00),
    "WA": RegionProfile("WA", "Western Australia", 1.18, 1.05),
    "SA": RegionProfile("SA", "South Australia", 1.12, 1.02),
}

COMPETITORS: List[Competitor] = [
    Competitor("Competitor A", "Aggressive / low-cost", 0.90),
    Competitor("Competitor B", "Market average", 1.00),
    Competitor("Competitor C", "Premium supplier", 1.15),
    Competitor("Competitor D", "Regional player", 0.96),
]

PIPE_BASE_PRICE_PER_M: Dict[int, float] = {
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


def quantity_discount(quantity_m: float) -> float:
    if quantity_m >= 1000:
        return 0.88
    if quantity_m >= 500:
        return 0.92
    if quantity_m >= 250:
        return 0.95
    if quantity_m >= 100:
        return 0.98
    return 1.00


def build_competitor_pricing_sheet(
    pipe_size_mm: int,
    quantity_m: float,
    region_key: str,
) -> List[dict]:
    region = REGIONS[region_key]
    base_price = PIPE_BASE_PRICE_PER_M[pipe_size_mm]
    discount = quantity_discount(quantity_m)

    rows = []

    for competitor in COMPETITORS:
        price_per_m = (
            base_price
            * competitor.price_factor
            * region.freight_multiplier
            * region.market_pressure
            * discount
        )

        total_price = price_per_m * quantity_m

        rows.append({
            "Competitor": competitor.name,
            "Pricing position": competitor.pricing_position,
            "Pipe size": f"{pipe_size_mm}mm",
            "Quantity": f"{quantity_m:,.0f}m",
            "Region": region.name,
            "Estimated price / m": round(price_per_m, 2),
            "Estimated total price": round(total_price, 0),
        })

    return rows


st.set_page_config(
    page_title="Competitor Pipe Pricing Tool",
    layout="wide",
)

st.title("Competitor Pipe Pricing Tool")
st.caption("Enter pipe size, quantity, and region to generate an indicative competitor pricing sheet.")

with st.sidebar:
    st.header("Inputs")

    pipe_size_mm = st.selectbox(
        "Pipe size",
        sorted(PIPE_BASE_PRICE_PER_M.keys()),
        index=2,
        format_func=lambda x: f"{x}mm",
    )

    quantity_m = st.number_input(
        "Quantity / length to sell (m)",
        min_value=1.0,
        value=120.0,
        step=10.0,
    )

    region_key = st.selectbox(
        "Region",
        list(REGIONS.keys()),
        format_func=lambda x: REGIONS[x].name,
    )

    generate = st.button("Generate competitor pricing sheet", type="primary")


if generate:
    pricing_sheet = build_competitor_pricing_sheet(
        pipe_size_mm=pipe_size_mm,
        quantity_m=quantity_m,
        region_key=region_key,
    )

    prices = [row["Estimated price / m"] for row in pricing_sheet]

    market_low = min(prices)
    market_average = sum(prices) / len(prices)
    market_high = max(prices)

    k1, k2, k3 = st.columns(3)
    k1.metric("Lowest competitor price", f"${market_low:,.2f}/m")
    k2.metric("Market average", f"${market_average:,.2f}/m")
    k3.metric("Highest competitor price", f"${market_high:,.2f}/m")

    st.markdown("### Competitor Pricing Sheet")

    st.dataframe(
        pricing_sheet,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        label="Download pricing sheet as CSV",
        data="\n".join([
            ",".join(pricing_sheet[0].keys()),
            *[
                ",".join(str(value) for value in row.values())
                for row in pricing_sheet
            ],
        ]),
        file_name="competitor_pipe_pricing_sheet.csv",
        mime="text/csv",
    )

else:
    st.info("Enter the pipe size, quantity, and region, then click generate.")
