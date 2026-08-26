from pathlib import Path

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
    summed across all partner countries. TDM's GBE (green bean equivalent)
    is in metric tons — converted to K 60kg bags via GBE * 1000 / 60 / 1000."""
    df = pd.read_parquet(TDM_PATH)
    df["Date"] = pd.to_datetime(dict(year=df.Year, month=df.Month, day=1))
    df["Bags (K)"] = df["GBE"] / 60.0
    return df[["Date", "Bags (K)"]].sort_values("Date").reset_index(drop=True)


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
    """CECAFE's own Total Volume (Arabica + Robusta), K bags."""
    econ_df = econ.load_economics()
    out = econ_df[["Date", "Total Volume"]].copy()
    out["Bags (K)"] = out["Total Volume"] / 1000.0
    return out[["Date", "Bags (K)"]]


def comexstat_brazil(df_cx):
    """Comexstat's own Total, K bags."""
    mt = cx.monthly_totals(df_cx)
    return mt[["Date", "Bags (K)"]]


def merged_sources(df_cx):
    """Outer-joined monthly Bags (K) for all four sources, aligned on Date."""
    frames = {
        "CECAFE": cecafe_brazil(),
        "Comexstat": comexstat_brazil(df_cx),
        "TDM": load_tdm_brazil(),
        "ICO": ico_brazil(),
    }
    out = None
    for name, f in frames.items():
        f = f.rename(columns={"Bags (K)": name}).set_index("Date")
        out = f if out is None else out.join(f, how="outer")
    return out.sort_index().reset_index()


def correlation_matrix(merged):
    cols = [c for c in merged.columns if c != "Date"]
    return merged[cols].corr()
