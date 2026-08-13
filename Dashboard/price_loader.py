import io
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# Local network path (fast, used when this machine has the ICEBREAKER-Rollex
# share mounted). Streamlit Cloud only mounts this repo, not that sibling
# one, so it never has this path — falls back to the published GitHub copy.
LOCAL_ROLLEX_DIR = Path(__file__).resolve().parents[3] / "ICEBREAKER" / "Rollex" / "Database"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/virataryaa/ICEBREAKER-Rollex/main/Database"

# KC is quoted in cents/lb, RC in $/tonne. 1 metric tonne = 2204.62 lb, so
# cents/lb x 22.0462 = $/tonne — puts both legs on the same footing before
# taking a spread.
CENTS_LB_TO_USD_TONNE = 22.0462


def _read_rollex_parquet(filename, columns):
    local_path = LOCAL_ROLLEX_DIR / filename
    if local_path.exists():
        return pd.read_parquet(local_path, columns=columns)
    with urllib.request.urlopen(f"{GITHUB_RAW_BASE}/{filename}", timeout=30) as resp:
        raw = resp.read()
    return pd.read_parquet(io.BytesIO(raw), columns=columns)


@st.cache_data
def load_daily_spread():
    """Daily roll-adjusted Arabica & Robusta prices ($/tonne) and their
    spread (Arabica - Robusta), from the two Rollex parquet files."""
    kc = _read_rollex_parquet("rollex_KC.parquet", ["rollex_px"]).rename(columns={"rollex_px": "Arabica"})
    rc = _read_rollex_parquet("rollex_RC.parquet", ["rollex_px"]).rename(columns={"rollex_px": "Robusta"})
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
