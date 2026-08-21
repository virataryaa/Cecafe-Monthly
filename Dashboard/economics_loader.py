from pathlib import Path

import pandas as pd
import streamlit as st

from data_loader import MONTH_NAMES, PERIOD_ORDER, _crop_start, _crop_label
from luis_loader import load_prices, PRICE_UNITS

ECONOMICS_PATH = Path(__file__).resolve().parent.parent / "Database" / "Cecafe Economics.xlsx"

# Source column names, keyed by type — avoids repeating the raw Excel headers
# (with their inconsistent spacing, e.g. "Revenue ( k Dollars)") everywhere.
COLS = {
    "Arabica": {"volume": "Arabica Volume (60kg Bags)", "revenue": "Arabica Revenue ( k Dollars)",
                "price": "Arabica Avg Price ($ per Bag)"},
    "Robusta": {"volume": "Robusta Volume (60kg Bags)", "revenue": "Robusta Revenue ( k Dollars)",
                "price": "Robusta Avg Price ($ per Bag)"},
}


@st.cache_data
def load_economics():
    """Monthly Brazil coffee export revenue & realized average price (own
    currency-value data, distinct from both the physical-volume-by-destination
    file and Luis's NY/London futures file) — 1990-present, no gaps."""
    df = pd.read_excel(ECONOMICS_PATH, sheet_name="Database")
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["CropStart"] = df.apply(lambda r: _crop_start(int(r["Year"]), int(r["Month"])), axis=1)
    df["CropYear"] = df["CropStart"].apply(_crop_label)
    df["Period"] = df["Month"].map(MONTH_NAMES)

    df["Total Revenue"] = df[COLS["Arabica"]["revenue"]] + df[COLS["Robusta"]["revenue"]]
    df["Total Volume"] = df[COLS["Arabica"]["volume"]] + df[COLS["Robusta"]["volume"]]
    df["Robusta Revenue SharePct"] = df[COLS["Robusta"]["revenue"]] / df["Total Revenue"] * 100
    return df.sort_values("Date").reset_index(drop=True)


def crop_year_order(df):
    return (df[["CropStart", "CropYear"]].drop_duplicates()
            .sort_values("CropStart")["CropYear"].tolist())


def econ_wide(df, col):
    """Period rows x CropYear columns for one metric column — same shape
    seasonal_table_html expects (one row per month already, so aggfunc is
    just a passthrough)."""
    pivot = df.pivot_table(index="Period", columns="CropYear", values=col, aggfunc="sum")
    pivot = pivot.reindex(PERIOD_ORDER)
    years = crop_year_order(df)
    pivot = pivot.reindex(columns=years).reset_index()
    return pivot


@st.cache_data
def price_vs_futures(type_):
    """Realized export price ($/bag, from Cecafe Economics) joined to the
    matching futures price (Luis data, native unit) for the same month —
    a cross-check of Brazil's own realized price against the market quote,
    not a lagged/causal comparison like the Price vs Exports tab."""
    econ = load_economics()[["Date", COLS[type_]["price"]]].rename(
        columns={COLS[type_]["price"]: "Realized"})
    fut = load_prices()[["Date", type_]].rename(columns={type_: "Futures"})
    merged = econ.merge(fut, on="Date", how="inner").dropna().sort_values("Date")
    return merged, PRICE_UNITS[type_]
