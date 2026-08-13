from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROLLEX_DIR = Path(__file__).resolve().parents[3] / "ICEBREAKER" / "Rollex" / "Database"
KC_PATH = ROLLEX_DIR / "rollex_KC.parquet"  # Arabica, cents/lb
RC_PATH = ROLLEX_DIR / "rollex_RC.parquet"  # Robusta, $/tonne

# KC is quoted in cents/lb, RC in $/tonne. 1 metric tonne = 2204.62 lb, so
# cents/lb x 22.0462 = $/tonne — puts both legs on the same footing before
# taking a spread.
CENTS_LB_TO_USD_TONNE = 22.0462


@st.cache_data
def load_daily_spread():
    """Daily roll-adjusted Arabica & Robusta prices ($/tonne) and their
    spread (Arabica - Robusta), from the two Rollex parquet files."""
    kc = pd.read_parquet(KC_PATH, columns=["rollex_px"]).rename(columns={"rollex_px": "Arabica"})
    rc = pd.read_parquet(RC_PATH, columns=["rollex_px"]).rename(columns={"rollex_px": "Robusta"})
    kc["Arabica"] = kc["Arabica"] * CENTS_LB_TO_USD_TONNE

    out = kc.join(rc, how="inner").sort_index()
    out["Spread"] = out["Arabica"] - out["Robusta"]
    out.index.name = "Date"
    return out.reset_index()


@st.cache_data
def monthly_price_series():
    """Daily prices resampled to calendar-month averages — matches the
    monthly granularity of the Cecafe export data."""
    daily = load_daily_spread()
    monthly = (
        daily.set_index("Date")[["Arabica", "Robusta", "Spread"]]
        .resample("MS").mean()
        .reset_index()
    )
    return monthly


def lagged_merge(share_df, lag_months):
    """Joins monthly Robusta-share (Date, RobustaSharePct) to the price
    series `lag_months` earlier — i.e. share in month M is compared against
    the average spread from month (M - lag_months), on the premise that
    shipped volumes reflect purchase/booking decisions made earlier."""
    prices = monthly_price_series().copy()
    prices["Date"] = prices["Date"] + pd.DateOffset(months=lag_months)
    merged = share_df.merge(prices, on="Date", how="inner")
    return merged.dropna(subset=["RobustaSharePct", "Spread"])


def lag_scan(share_df, max_lag=12):
    """Pearson correlation between Robusta share and the Arabica-Robusta
    spread at each lag from 0..max_lag months — used to find which lag
    best explains the export mix, rather than assuming one."""
    rows = []
    for lag in range(max_lag + 1):
        merged = lagged_merge(share_df, lag)
        n = len(merged)
        if n >= 6:
            r = merged["RobustaSharePct"].corr(merged["Spread"])
        else:
            r = np.nan
        rows.append({"Lag": lag, "Correlation": r, "N": n})
    return pd.DataFrame(rows)
