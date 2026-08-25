from pathlib import Path

import pandas as pd
import streamlit as st

from data_loader import MONTH_NAMES, PERIOD_ORDER, _crop_start, _crop_label

COMEXSTAT_DIR = Path(__file__).resolve().parent.parent / "Database" / "Comexstat"
COMEXSTAT_PATH = COMEXSTAT_DIR / "comexstat_coffee_exports.parquet"
URF_PATH = COMEXSTAT_DIR / "ref_urf.csv"

KG_PER_BAG = 60.0

# Brazilian coffee-growing states with an overwhelmingly dominant single
# variety (per typical Conab/CECAFE production splits) — used to build an
# independent, customs-data-only Arabica/Robusta proxy. States without a
# clear single-variety majority (e.g. Bahia, which mixes Cerrado Arabica
# and southern Conilon) are left unclassified rather than guessed at.
STATE_GROUP = {
    "MG": "Arabica", "SP": "Arabica", "PR": "Arabica", "GO": "Arabica",
    "ES": "Robusta", "RO": "Robusta",
}


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
    df["StateGroup"] = df["State"].map(STATE_GROUP).fillna("Unclassified")

    urf = pd.read_csv(URF_PATH, sep=";", encoding="latin1")
    urf["Port"] = urf["NO_URF"].str.split(" - ", n=1).str[-1].str.title()
    df = df.merge(urf[["CO_URF", "Port"]], on="CO_URF", how="left")

    return df.sort_values("Date").reset_index(drop=True)


def crop_year_order(df):
    return (df[["CropStart", "CropYear"]].drop_duplicates()
            .sort_values("CropStart")["CropYear"].tolist())


def state_totals(df, crop_year):
    """Total Bags (K) per state for one crop year, descending."""
    sub = df[df["CropYear"] == crop_year]
    totals = sub.groupby("State")["Bags (K)"].sum().sort_values(ascending=False)
    return [(s, v) for s, v in totals.items() if v > 0]


def state_monthly_series(df, states, crop_years=None):
    """Date-indexed monthly Bags (K) per state, for stacked/overlay charts."""
    sub = df[df["State"].isin(states)]
    if crop_years is not None:
        sub = sub[sub["CropYear"].isin(crop_years)]
    pivot = sub.pivot_table(index="Date", columns="State", values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(columns=states).fillna(0.0).sort_index()
    return pivot


def state_proxy_robusta_share(df):
    """Crop-year Robusta share using only the unambiguous single-variety
    states (STATE_GROUP) — an independent cross-check against CECAFE's own
    officially-tagged Arabica/Robusta split, built purely from customs data
    with no reliance on how CECAFE itself classifies each shipment."""
    classified = df[df["StateGroup"] != "Unclassified"]
    pivot = classified.pivot_table(index="CropYear", columns="StateGroup",
                                    values="Bags (K)", aggfunc="sum")
    years = crop_year_order(df)
    pivot = pivot.reindex(years).fillna(0.0)
    total = pivot.get("Arabica", 0) + pivot.get("Robusta", 0)
    share = (pivot.get("Robusta", 0) / total * 100).where(total > 0)
    return [(y, v) for y, v in share.items() if pd.notna(v)]


def port_totals(df, crop_year=None, top_n=10):
    """Total Bags (K) per port (customs office), descending."""
    sub = df if crop_year is None else df[df["CropYear"] == crop_year]
    totals = sub.groupby("Port")["Bags (K)"].sum().sort_values(ascending=False)
    return [(p, v) for p, v in totals.items() if v > 0]


def port_monthly_series(df, ports):
    sub = df[df["Port"].isin(ports)]
    pivot = sub.pivot_table(index="Date", columns="Port", values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(columns=ports).fillna(0.0).sort_index()
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
