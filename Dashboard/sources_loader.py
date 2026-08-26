from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import comexstat_loader as cx
import economics_loader as econ

SOURCES_DIR = Path(__file__).resolve().parent.parent / "Database" / "Sources"
TDM_PATH = SOURCES_DIR / "tdm_brazil.parquet"
ICO_PATH = SOURCES_DIR / "ico_exports.parquet"


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


def cecafe_brazil_incl_soluble():
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
    """Outer-joined monthly Bags (K) for all sources, aligned on Date.
    Includes CECAFE+Soluble as an extra column alongside the 4 main
    sources — not meant for the general overlay, just the ICO-specific
    comparisons where a green-bean-only baseline isn't apples-to-apples."""
    frames = {
        "CECAFE": cecafe_brazil(),
        "Comexstat": comexstat_brazil(df_cx),
        "TDM": load_tdm_brazil(),
        "ICO": ico_brazil(),
        "CECAFE+Soluble": cecafe_brazil_incl_soluble(),
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
