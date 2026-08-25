from pathlib import Path

import pandas as pd
import streamlit as st

from data_loader import MONTH_NAMES, PERIOD_ORDER, _crop_start, _crop_label

COMEXSTAT_DIR = Path(__file__).resolve().parent.parent / "Database" / "Comexstat"
COMEXSTAT_PATH = COMEXSTAT_DIR / "comexstat_coffee_exports.parquet"
URF_PATH = COMEXSTAT_DIR / "ref_urf.csv"

KG_PER_BAG = 60.0


@st.cache_data
def load_comexstat():
    """Brazil customs (Comexstat) green-coffee export rows, 1997-present,
    filtered to the 3 green-bean NCM codes. Independent of the CECAFE
    association data used elsewhere in this app — different source,
    different methodology (customs clearance vs association reporting)."""
    df = pd.read_parquet(COMEXSTAT_PATH)
    df = df.rename(columns={"CO_ANO": "Year", "CO_MES": "Month", "SG_UF_NCM": "State",
                             "NO_PAIS_ING": "Destination"})
    df["CropStart"] = df.apply(lambda r: _crop_start(int(r["Year"]), int(r["Month"])), axis=1)
    df["CropYear"] = df["CropStart"].apply(_crop_label)
    df["Period"] = df["Month"].map(MONTH_NAMES)
    df["Date"] = pd.to_datetime(dict(year=df["Year"], month=df["Month"], day=1))
    df["Bags (K)"] = df["KG_LIQUIDO"] / KG_PER_BAG / 1000.0

    urf = pd.read_csv(URF_PATH, sep=";", encoding="latin1")
    urf["Port"] = urf["NO_URF"].str.split(" - ", n=1).str[-1].str.title()
    df = df.merge(urf[["CO_URF", "Port"]], on="CO_URF", how="left")

    return df.sort_values("Date").reset_index(drop=True)


def crop_year_order(df):
    return (df[["CropStart", "CropYear"]].drop_duplicates()
            .sort_values("CropStart")["CropYear"].tolist())


def geo_totals(df, field, crop_year=None):
    """Total Bags (K) per State or Port, descending. field is 'State' or
    'Port'; crop_year=None sums the full history."""
    sub = df if crop_year is None else df[df["CropYear"] == crop_year]
    totals = sub.groupby(field)["Bags (K)"].sum().sort_values(ascending=False)
    return [(k, v) for k, v in totals.items() if v > 0]


def geo_monthly_series(df, field, entities, crop_years=None):
    """Date-indexed monthly Bags (K), one column per entity — feeds
    stacked/overlay trend charts for a chosen set of states or ports."""
    sub = df[df[field].isin(entities)]
    if crop_years is not None:
        sub = sub[sub["CropYear"].isin(crop_years)]
    pivot = sub.pivot_table(index="Date", columns=field, values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(columns=entities).fillna(0.0).sort_index()
    return pivot


def geo_long_run(df, field, entity):
    """Full chronological monthly Bags (K) history for one State or Port —
    feeds the drill-down time series chart."""
    sub = df[df[field] == entity]
    grouped = sub.groupby("Date", as_index=False)["Bags (K)"].sum().sort_values("Date")
    return grouped


def geo_wide(df, field, entity):
    """Period rows x CropYear columns of Bags (K) for one State or Port —
    same shape seasonal_table_html expects elsewhere in this app."""
    sub = df[df[field] == entity]
    pivot = sub.pivot_table(index="Period", columns="CropYear", values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(PERIOD_ORDER)
    years = crop_year_order(df)
    pivot = pivot.reindex(columns=years).reset_index()
    return pivot


def monthly_totals(df):
    """Total Bags (K), FOB value (USD), and implied price ($/bag) per
    calendar month — the Comexstat side of the reconciliation vs CECAFE."""
    grouped = df.groupby("Date").agg(**{
        "Bags (K)": ("Bags (K)", "sum"),
        "FOB (USD)": ("VL_FOB", "sum"),
    }).reset_index()
    grouped["Price ($/bag)"] = grouped["FOB (USD)"] / (grouped["Bags (K)"] * 1000)
    return grouped.sort_values("Date")
