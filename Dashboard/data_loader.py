from pathlib import Path

import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "Database" / "Cecafe Monthly.xlsx"

MONTH_ORDER = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]  # crop year: Jul -> Jun
MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
PERIOD_ORDER = [MONTH_NAMES[m] for m in MONTH_ORDER]

TOTAL = "Total"


def _crop_start(year, month):
    return year if month >= 7 else year - 1


def _crop_label(start):
    return f"{str(start)[2:]}/{str(start + 1)[2:]}"


@st.cache_data
def load_raw():
    df = pd.read_excel(DATA_PATH, sheet_name="Database")
    df["CropStart"] = df.apply(lambda r: _crop_start(int(r["Year"]), int(r["Month"])), axis=1)
    df["CropYear"] = df["CropStart"].apply(_crop_label)
    df["Period"] = df["Month"].map(MONTH_NAMES)
    return df


def types(df):
    return sorted(df["Type"].unique())


def destinations(df, exclude_total=True):
    dests = sorted(df["Destination"].unique())
    if exclude_total:
        dests = [d for d in dests if d != TOTAL]
    return dests


def year_columns(df_wide):
    return [c for c in df_wide.columns if c != "Period"]


def _crop_year_order(df):
    return (df[["CropStart", "CropYear"]]
            .drop_duplicates()
            .sort_values("CropStart")["CropYear"]
            .tolist())


def _pivot(df, type_, destination):
    sub = df[(df["Type"] == type_) & (df["Destination"] == destination)]
    pivot = sub.pivot_table(index="Period", columns="CropYear", values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(PERIOD_ORDER)
    ordered_cols = [c for c in _crop_year_order(df) if c in pivot.columns]
    pivot = pivot[ordered_cols].reset_index()
    return pivot


def flow_wide(df, type_, destination):
    """Monthly bags (Period rows, crop-year columns) for one Type/Destination."""
    return _pivot(df, type_, destination)


def proportion_wide(df, type_, destination):
    """Destination's share of that Type's Total exports, per month (%)."""
    dest_wide = _pivot(df, type_, destination)
    total_wide = _pivot(df, type_, TOTAL)
    year_cols = year_columns(dest_wide)
    prop = dest_wide.copy()
    for y in year_cols:
        prop[y] = dest_wide[y] / total_wide[y] * 100
    return prop


def latest_crop_year_label(df, type_):
    sub = df[df["Type"] == type_]
    return _crop_label(sub["CropStart"].max())
