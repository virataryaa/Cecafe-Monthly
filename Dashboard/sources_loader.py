from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import comexstat_loader as cx
import economics_loader as econ

SOURCES_DIR = Path(__file__).resolve().parent.parent / "Database" / "Sources"
TDM_PATH = SOURCES_DIR / "tdm_brazil.parquet"
TDM_SOLUBLE_PATH = SOURCES_DIR / "tdm_brazil_soluble.parquet"
COMEXSTAT_SOLUBLE_PATH = SOURCES_DIR / "comexstat_brazil_soluble.parquet"
ICO_PATH = SOURCES_DIR / "ico_exports.parquet"

# ICO's GBE (Green Bean Equivalent) convention for soluble/instant coffee:
# 1 kg soluble product ~= 2.6 kg green bean equivalent (a real physical
# conversion for the concentration during processing, unlike the green-bean
# 1.05x factor above which has no such physical basis). TDM's own GBE
# column for soluble already applies exactly this factor (confirmed
# constant across every row) — Comexstat has no GBE field at all, so it's
# applied manually below.
SOLUBLE_GBE_FACTOR = 2.6


@st.cache_data
def load_tdm_brazil():
    """Brazil green-bean exports from TDM's bilateral trade-flow data,
    summed across all partner countries. Uses raw QTY1 (metric tons),
    NOT TDM's GBE column — GBE is just QTY1 * 1.05 (a flat, constant
    multiplier confirmed across every row), which on its own accounts for
    most of a persistent ~5% gap vs CECAFE that never reverted (unlike
    Comexstat, which oscillates around 0% against CECAFE). Raw QTY1 brings
    TDM's average gap down from +5.6% to +1.1% and restores sign-flipping
    like the other sources, so this is the apples-to-apples comparison.
    Converted to K 60kg bags via QTY1 * 1000 / 60 / 1000 = QTY1 / 60.

    TDM occasionally has a single-partner reporting anomaly (e.g.
    Brazil->Germany, Jan 2015, where Germany alone was 52% of that month's
    total vs the normal ~20-25% for a top buyer) that isn't a real trade
    spike. That month runs 1.59x its centered 5-month median — clearly
    separated from the next-highest ratio anywhere in the series (1.29x,
    a real broad-based peak). Cap anything above 1.5x to that median,
    rather than let one bad cell distort the whole series."""
    df = pd.read_parquet(TDM_PATH)
    df["Date"] = pd.to_datetime(dict(year=df.Year, month=df.Month, day=1))
    df = df.sort_values("Date").reset_index(drop=True)
    df["Bags (K)"] = df["QTY1"] / 60.0

    rolling_med = df["Bags (K)"].rolling(5, center=True, min_periods=3).median()
    is_outlier = df["Bags (K)"] > rolling_med * 1.5
    df.loc[is_outlier, "Bags (K)"] = rolling_med[is_outlier]

    return df[["Date", "Bags (K)"]]


@st.cache_data
def load_tdm_brazil_soluble():
    """Brazil soluble/instant coffee exports from TDM (COMMODITY_TAG =
    'Instant & Mixes', HS 2101.11/2101.12), in K 60kg green-bean-equivalent
    bags. Uses TDM's GBE column here (not raw QTY1 like the green-bean
    series) since GBE = QTY1 * 2.6 for every soluble row — that's the real
    soluble-to-green conversion, not an unexplained padding."""
    df = pd.read_parquet(TDM_SOLUBLE_PATH)
    df["Date"] = pd.to_datetime(dict(year=df.Year, month=df.Month, day=1))
    df["Bags (K)"] = df["GBE"] / 60.0
    return df[["Date", "Bags (K)"]].sort_values("Date").reset_index(drop=True)


def tdm_brazil_total():
    """TDM green bean + soluble (GBE-converted), K bags — comparable in
    scope to ICO's blended headline figure."""
    green = load_tdm_brazil().rename(columns={"Bags (K)": "Green"})
    soluble = load_tdm_brazil_soluble().rename(columns={"Bags (K)": "Soluble"})
    out = green.merge(soluble, on="Date", how="outer").fillna(0.0)
    out["Bags (K)"] = out["Green"] + out["Soluble"]
    return out[["Date", "Bags (K)"]].sort_values("Date").reset_index(drop=True)


@st.cache_data
def load_comexstat_brazil_soluble():
    """Brazil soluble coffee exports from Comexstat (NCM 2101.11.10/.90,
    2101.12.00), extracted the same way as the green-bean pull. KG_LIQUIDO
    is raw product weight (Comexstat has no GBE field), converted to K
    bags via the same SOLUBLE_GBE_FACTOR TDM's own GBE column uses."""
    df = pd.read_parquet(COMEXSTAT_SOLUBLE_PATH)
    df["Date"] = pd.to_datetime(dict(year=df.Year, month=df.Month, day=1))
    df["Bags (K)"] = (df["KG_LIQUIDO"] * SOLUBLE_GBE_FACTOR) / 60.0 / 1000.0
    return df[["Date", "Bags (K)"]].sort_values("Date").reset_index(drop=True)


def comexstat_brazil_total(df_cx):
    """Comexstat green bean + soluble (GBE-converted), K bags."""
    green = comexstat_brazil(df_cx).rename(columns={"Bags (K)": "Green"})
    soluble = load_comexstat_brazil_soluble().rename(columns={"Bags (K)": "Soluble"})
    out = green.merge(soluble, on="Date", how="outer").fillna(0.0)
    out["Bags (K)"] = out["Green"] + out["Soluble"]
    return out[["Date", "Bags (K)"]].sort_values("Date").reset_index(drop=True)


@st.cache_data
def load_ico_exports():
    """ICO Monthly Trade Statistics, every country/grouping ICO reports —
    GBE already in 60kg bags (ICO's own unit), 2016-present. Extracted from
    123 individual monthly report files (Comexstat/CECAFE-style bulk files
    aren't published by ICO)."""
    df = pd.read_parquet(ICO_PATH)
    df["Date"] = pd.to_datetime(dict(year=df.Year, month=df.Month, day=1))
    return df


def ico_brazil():
    """ICO's Brazil series only, as K bags."""
    df = load_ico_exports()
    br = df[df["Country"] == "Brazil"].copy()
    br["Bags (K)"] = br["GBE_bags"] / 1000.0
    return br[["Date", "Bags (K)"]].sort_values("Date").reset_index(drop=True)


def cecafe_brazil():
    """CECAFE's own Total Volume (Arabica + Robusta, green bean only), K bags."""
    econ_df = econ.load_economics()
    out = econ_df[["Date", "Total Volume"]].copy()
    out["Bags (K)"] = out["Total Volume"] / 1000.0
    return out[["Date", "Bags (K)"]]


def cecafe_brazil_total():
    """CECAFE's Total Volume plus Soluble, K bags — the ICO-comparable
    baseline. Confirmed empirically: ICO's headline Brazil export figure
    runs ~11.6% above green-bean CECAFE on average, every year, but only
    ~0.4% above once Soluble is added — i.e. ICO's own number already
    includes soluble/instant coffee (as GBE), which green-bean-only
    CECAFE/Comexstat/TDM do not."""
    econ_df = econ.load_economics()
    out = econ_df[["Date", "Total Volume Incl Soluble"]].copy()
    out["Bags (K)"] = out["Total Volume Incl Soluble"] / 1000.0
    return out[["Date", "Bags (K)"]]


def comexstat_brazil(df_cx):
    """Comexstat's own Total, K bags."""
    mt = cx.monthly_totals(df_cx)
    return mt[["Date", "Bags (K)"]]


def merged_sources(df_cx):
    """Outer-joined monthly Bags (K) for every source and scope, aligned
    on Date. Green-bean scope (CECAFE, Comexstat, TDM) is directly
    comparable across those three; the +Soluble ("total coffee, GBE")
    columns are the ones comparable to ICO, whose headline figure already
    blends green and soluble."""
    frames = {
        "CECAFE": cecafe_brazil(),
        "Comexstat": comexstat_brazil(df_cx),
        "TDM": load_tdm_brazil(),
        "ICO": ico_brazil(),
        "CECAFE+Soluble": cecafe_brazil_total(),
        "Comexstat+Soluble": comexstat_brazil_total(df_cx),
        "TDM+Soluble": tdm_brazil_total(),
    }
    out = None
    for name, f in frames.items():
        f = f.rename(columns={"Bags (K)": name}).set_index("Date")
        out = f if out is None else out.join(f, how="outer")
    return out.sort_index().reset_index()


def correlation_matrix(merged):
    """Pairwise correlation, with the self-correlation diagonal blanked out
    (always 1 by definition, not informative)."""
    cols = [c for c in merged.columns if c != "Date"]
    corr = merged[cols].corr()
    for c in cols:
        corr.loc[c, c] = np.nan
    return corr
