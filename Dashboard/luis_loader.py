from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from statsmodels.tsa.stattools import grangercausalitytests

LUIS_PATH = Path(__file__).resolve().parent.parent / "Database" / "Luis data.xlsx"
EXPORTS_PATH = Path(__file__).resolve().parent.parent / "Database" / "Brazil total exports.xlsx"

# 60kg saca (the Brazilian trade bag) unit conversions.
CENTS_LB_TO_USD_BAG = 1.32277   # NY (Arabica) cents/lb -> $/60kg bag
USD_TONNE_TO_USD_BAG = 0.06     # London (Robusta) $/tonne -> $/60kg bag

MAX_LAG = 12


@st.cache_data
def load_prices():
    """Daily NY (Arabica) & London (Robusta) futures from Luis's data,
    converted to $/60kg bag (the Brazilian trade unit) and resampled to
    monthly averages to match the export data's granularity."""
    raw = pd.read_excel(LUIS_PATH, sheet_name="Database", header=None, skiprows=2,
                         usecols=[0, 1, 2, 4], names=["Date", "NY", "London", "USD"])
    raw["Date"] = pd.to_datetime(raw["Date"])
    raw = raw.dropna(subset=["Date", "NY", "London", "USD"])
    raw = raw[(raw["NY"] > 0) & (raw["London"] > 0) & (raw["USD"] > 0)]

    raw["Arabica"] = raw["NY"] * CENTS_LB_TO_USD_BAG
    raw["Robusta"] = raw["London"] * USD_TONNE_TO_USD_BAG
    raw["Spread"] = raw["Arabica"] - raw["Robusta"]

    return (raw.set_index("Date")[["Arabica", "Robusta", "Spread"]]
            .resample("MS").mean().reset_index())


@st.cache_data
def load_export_share():
    """Monthly Brazil total (world) coffee export volumes by type
    (Conillon = Robusta, Arabica), and Conillon's share of the combined
    total — a global, not destination-specific, export mix."""
    raw = pd.read_excel(EXPORTS_PATH, sheet_name="Sheet1")
    raw.columns = ["Month", "Year", "Conillon", "Arabica"]
    raw["Date"] = pd.to_datetime(dict(year=raw["Year"], month=raw["Month"], day=1))
    raw["Total"] = raw["Conillon"] + raw["Arabica"]
    raw["RobustaSharePct"] = raw["Conillon"] / raw["Total"] * 100
    return raw[["Date", "Conillon", "Arabica", "Total", "RobustaSharePct"]].dropna()


def lagged_merge(lag_months):
    """Robusta export share in month M joined to the price series from
    month (M - lag_months) — shipped volumes reflect price signals seen
    many months earlier, not the same month's price."""
    share = load_export_share()[["Date", "RobustaSharePct", "Total"]]
    prices = load_prices().copy()
    prices["Date"] = prices["Date"] + pd.DateOffset(months=lag_months)
    return share.merge(prices, on="Date", how="inner").dropna()


def lag_scan(max_lag=MAX_LAG):
    """Pearson correlation (price level vs share level) at each lag, for
    Arabica, Robusta and the spread. Kept for transparency, but note: only
    Robusta price survives the Granger causality test below — the level
    correlations here (especially Arabica's and the spread's) are largely
    trend artifacts, not evidence of a real relationship."""
    rows = []
    for lag in range(max_lag + 1):
        m = lagged_merge(lag)
        rows.append({
            "Lag": lag, "N": len(m),
            "Arabica": m["RobustaSharePct"].corr(m["Arabica"]),
            "Robusta": m["RobustaSharePct"].corr(m["Robusta"]),
            "Spread": m["RobustaSharePct"].corr(m["Spread"]),
        })
    return pd.DataFrame(rows)


@st.cache_data
def granger_scan(exog_col, maxlag=MAX_LAG):
    """Granger causality p-values: does `exog_col`'s month-over-month log
    change help predict Robusta share's month-over-month change, at each
    lag from 1..maxlag? Uses log first-differences (verified stationary)
    rather than raw levels, since correlating two trending level series
    produces spurious results."""
    m = lagged_merge(0).sort_values("Date").reset_index(drop=True)
    d = pd.DataFrame({
        "dShare": m["RobustaSharePct"].diff(),
        "dExog": np.log(m[exog_col]).diff(),
    }).dropna()

    res = grangercausalitytests(d[["dShare", "dExog"]], maxlag=maxlag, verbose=False)
    rows = [{"Lag": lag, "PValue": res[lag][0]["ssr_ftest"][1]} for lag in range(1, maxlag + 1)]
    return pd.DataFrame(rows)


def current_read(lag):
    """Simple OLS of Robusta share on Robusta price at the given lag, fit
    on history, then applied to the latest available Robusta price to
    project where the share is headed ~lag months out. The residual std
    gives a rough +/- band, not a formal confidence interval."""
    m = lagged_merge(lag).sort_values("Date").reset_index(drop=True)
    x = m["Robusta"].to_numpy()
    y = m["RobustaSharePct"].to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    resid_std = (y - (slope * x + intercept)).std()

    latest = load_prices().dropna(subset=["Robusta"]).iloc[-1]
    projected_share = slope * latest["Robusta"] + intercept

    return dict(
        latest_price=latest["Robusta"], latest_date=latest["Date"],
        projected_share=projected_share, resid_std=resid_std,
        target_date=latest["Date"] + pd.DateOffset(months=lag),
        lag=lag, n=len(m),
    )
