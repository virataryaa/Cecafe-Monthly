from pathlib import Path

import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "Database" / "Cecafe Monthly.xlsx"

MONTH_ORDER = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]  # crop year: Jul -> Jun
MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
PERIOD_ORDER = [MONTH_NAMES[m] for m in MONTH_ORDER]

TOTAL = "Total"        # Destination value meaning "all destinations"
ALL_TYPES = "Total"    # Type value meaning "Arabica + Robusta combined"

EUROPE_LABEL = "Europe (UK incl.)"
EUROPE_MEMBERS = ["Belgium", "Germany", "Italy", "Netherlands", "Spain", "UK"]


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
    return sorted(df["Type"].unique()) + [ALL_TYPES]


def destinations(df, exclude_total=True):
    dests = sorted(df["Destination"].unique())
    if exclude_total:
        dests = [d for d in dests if d != TOTAL]
    return dests


def destinations_for_type(df, type_, exclude_total=True):
    """Destinations that actually have at least one reported month for this Type
    (e.g. Arabica never ships to Vietnam, Robusta never ships to China).
    For ALL_TYPES ("Total"), it's the union across both types."""
    if type_ == ALL_TYPES:
        sub = df[df["Bags (K)"].notna()]
    else:
        sub = df[(df["Type"] == type_) & df["Bags (K)"].notna()]
    dests = sorted(sub["Destination"].unique())
    if exclude_total:
        dests = [d for d in dests if d != TOTAL]
    return dests


def types_traded(df, destination):
    """Which of Arabica/Robusta actually have reported exports to this destination
    (e.g. China is Arabica-only, Colombia is Robusta-only) — used to flag when a
    Arabica/Robusta mix comparison isn't meaningful for a given destination."""
    if destination == EUROPE_LABEL:
        mask = df["Destination"].isin(EUROPE_MEMBERS)
    else:
        mask = df["Destination"] == destination
    sub = df[mask & df["Bags (K)"].notna()]
    return sorted(sub["Type"].unique())


def year_columns(df_wide):
    return [c for c in df_wide.columns if c != "Period"]


def _crop_year_order(df, type_=None):
    sub = df if type_ in (None, ALL_TYPES) else df[df["Type"] == type_]
    return (sub[["CropStart", "CropYear"]]
            .drop_duplicates()
            .sort_values("CropStart")["CropYear"]
            .tolist())


def _pivot(df, type_, destination):
    """Always reindexed to every crop year that exists for this Type (not just
    the ones this destination happens to have rows for), so every destination's
    wide table shares identical columns and lines up across destinations.
    type_ == ALL_TYPES sums Arabica + Robusta together (no Type filter).
    destination == EUROPE_LABEL sums the EUROPE_MEMBERS countries together."""
    type_mask = df["Type"].notna() if type_ == ALL_TYPES else df["Type"] == type_
    if destination == EUROPE_LABEL:
        dest_mask = df["Destination"].isin(EUROPE_MEMBERS)
    else:
        dest_mask = df["Destination"] == destination
    sub = df[type_mask & dest_mask]
    pivot = sub.pivot_table(index="Period", columns="CropYear", values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(PERIOD_ORDER)
    full_years = _crop_year_order(df, type_)
    pivot = pivot.reindex(columns=full_years).reset_index()
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


def ytd_period_window(df_wide, year_cols):
    """Periods (Jul, Jul-Aug, ...) actually reported so far for the latest
    crop year — used so every crop year's 'YTD' figure covers the same
    apples-to-apples span instead of summing a full season for old years
    against one month for the current year."""
    periods = df_wide["Period"].tolist()
    current_year = year_cols[-1]
    last_valid = df_wide[current_year].last_valid_index()
    n = 0 if last_valid is None else last_valid + 1
    included = periods[:n] or periods[:1]
    span = included[0] if len(included) == 1 else f"{included[0]}-{included[-1]}"
    return included, f"YTD ({span})"


def latest_crop_year_label(df, type_):
    sub = df[df["Type"] == type_]
    return _crop_label(sub["CropStart"].max())


def compare_wide(df, type_, dests, crop_year):
    """Period rows, one column per destination, values for a single chosen
    crop year — used to overlay multiple destinations on one chart."""
    out = pd.DataFrame({"Period": PERIOD_ORDER})
    for d in dests:
        w = _pivot(df, type_, d).set_index("Period")
        out[d] = w[crop_year].reindex(PERIOD_ORDER).values if crop_year in w.columns else pd.NA
    return out


def get_crop_years(df, type_):
    """Public, ordered list of crop-year labels available for a Type (oldest first)."""
    return _crop_year_order(df, type_)


def month_options(df):
    """Every (Year, Month) combination present in the data, chronological —
    feeds the Insights tab's monthly range slider."""
    combos = df[["Year", "Month"]].drop_duplicates().sort_values(["Year", "Month"])
    return [(int(y), int(m)) for y, m in combos.itertuples(index=False)]


def month_label(ym):
    year, month = ym
    return f"{MONTH_NAMES[month]} {year}"


def _month_key(year, month):
    return year * 12 + month


def crop_years_overlapping_months(df, start_ym, end_ym):
    """Crop-year labels that have at least one reported month inside the
    inclusive (Year, Month) range — used to window the crop-year-based charts
    (Robusta mix trend) off the same monthly slider as everything else."""
    key = _month_key(df["Year"], df["Month"])
    mask = (key >= _month_key(*start_ym)) & (key <= _month_key(*end_ym))
    sub = df[mask]
    return (sub[["CropStart", "CropYear"]].drop_duplicates()
            .sort_values("CropStart")["CropYear"].tolist())


def destination_mix(df, type_, start_ym, end_ym):
    """Total per real destination (Europe/Total excluded) within the inclusive
    (Year, Month) range, sorted descending — feeds the pie chart and the
    top-destinations ranking bar."""
    key = _month_key(df["Year"], df["Month"])
    mask = (key >= _month_key(*start_ym)) & (key <= _month_key(*end_ym))
    type_mask = df["Type"].notna() if type_ == ALL_TYPES else df["Type"] == type_
    sub = df[type_mask & mask & (df["Destination"] != TOTAL)]
    totals = sub.groupby("Destination")["Bags (K)"].sum()
    rows = [(d, v) for d, v in totals.items() if v > 0]
    rows.sort(key=lambda p: p[1], reverse=True)
    return rows


def destination_month_matrix(df, type_, start_ym, end_ym):
    """Destination x Period matrix (Jul..Jun) summed within the inclusive
    (Year, Month) range — feeds the heatmap. Rows sorted by total, descending."""
    key = _month_key(df["Year"], df["Month"])
    mask = (key >= _month_key(*start_ym)) & (key <= _month_key(*end_ym))
    type_mask = df["Type"].notna() if type_ == ALL_TYPES else df["Type"] == type_
    sub = df[type_mask & mask & (df["Destination"] != TOTAL)]
    matrix = sub.pivot_table(index="Destination", columns="Period", values="Bags (K)", aggfunc="sum")
    matrix = matrix.reindex(columns=PERIOD_ORDER)
    matrix = matrix.loc[matrix.sum(axis=1, skipna=True).sort_values(ascending=False).index]
    return matrix


def long_run_series(df, type_, destination):
    """Full chronological history (2007 -> present), not windowed to a crop
    year — for the long-run trend chart."""
    type_mask = df["Type"].notna() if type_ == ALL_TYPES else df["Type"] == type_
    if destination == EUROPE_LABEL:
        dest_mask = df["Destination"].isin(EUROPE_MEMBERS)
    else:
        dest_mask = df["Destination"] == destination
    sub = df[type_mask & dest_mask]
    grouped = sub.groupby(["Year", "Month"], as_index=False)["Bags (K)"].sum()
    grouped["Date"] = pd.to_datetime(dict(year=grouped["Year"], month=grouped["Month"], day=1))
    grouped = grouped.sort_values("Date")
    return grouped[["Date", "Bags (K)"]]


def robusta_share_series(df, destination=TOTAL):
    """Arabica vs Robusta mix by crop year: Robusta's % share of combined
    exports to `destination`, for every crop year both types have data."""
    arabica = _pivot(df, "Arabica", destination)
    robusta = _pivot(df, "Robusta", destination)
    crop_years = _crop_year_order(df)
    rows = []
    for y in crop_years:
        a = arabica[y].sum(skipna=True) if y in arabica.columns else 0.0
        r = robusta[y].sum(skipna=True) if y in robusta.columns else 0.0
        if a + r > 0:
            rows.append((y, r / (a + r) * 100))
    return rows


def monthly_type_mix(df, destination, crop_years=None):
    """Actual Arabica & Robusta bags per calendar month (not crop-year totals),
    plus Robusta's % share of that same month — feeds the monthly mix chart.
    crop_years, if given, restricts to those crop years before grouping."""
    if destination == EUROPE_LABEL:
        dest_mask = df["Destination"].isin(EUROPE_MEMBERS)
    else:
        dest_mask = df["Destination"] == destination
    sub = df[dest_mask]
    if crop_years is not None:
        sub = sub[sub["CropYear"].isin(crop_years)]

    pivot = sub.pivot_table(index=["Year", "Month"], columns="Type", values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(columns=["Arabica", "Robusta"]).fillna(0.0).reset_index()
    pivot["Date"] = pd.to_datetime(dict(year=pivot["Year"], month=pivot["Month"], day=1))
    pivot = pivot.sort_values("Date")

    total = pivot["Arabica"] + pivot["Robusta"]
    pivot["RobustaSharePct"] = (pivot["Robusta"] / total * 100).where(total > 0)
    return pivot[["Date", "Arabica", "Robusta", "RobustaSharePct"]]


# --- Excess vs normal shipments (potential certified-stock grading) -----------
# Lots are exchange contract size / bag weight:
#   Arabica  KC (ICE US):     37,500 lb / 132.277 lb per 60kg bag = 283.5 bags
#   Robusta  RC (ICE Europe): 10 tonnes / 60 kg                   = 166.67 bags
BAGS_PER_LOT = {"Arabica": 283.5, "Robusta": 10_000 / 60}

BASELINE_METHODS = ["6M", "1Y", "3Y", "5Y", "10Y"]


def bags_per_lot(type_):
    return BAGS_PER_LOT.get(type_)


def baseline_caption(method):
    if method == "6M":
        return "Baseline = average of the 6 months immediately before the selected month."
    n = {"1Y": 1, "3Y": 3, "5Y": 5, "10Y": 10}[method]
    span = "year" if n == 1 else f"{n} years"
    return f"Baseline = average of the same calendar month over the prior {span}."


def _baseline_value(sub, year, month, method):
    """Normal level for one Type/Destination at (year, month).
    6M is a trailing average of the preceding six months; 1Y/3Y/5Y average the
    same calendar month across prior years, so the seasonal shape is preserved."""
    if method == "6M":
        key = sub["Year"] * 12 + sub["Month"]
        cur = year * 12 + month
        win = sub[(key < cur) & (key >= cur - 6)]
    else:
        n = {"1Y": 1, "3Y": 3, "5Y": 5, "10Y": 10}[method]
        win = sub[(sub["Month"] == month) & (sub["Year"] < year) & (sub["Year"] >= year - n)]
    vals = win["Bags (K)"].dropna()
    return float(vals.mean()) if not vals.empty else float("nan")


def _excess_row(name, actual, base, per_lot):
    excess = actual - base if pd.notna(actual) and pd.notna(base) else float("nan")
    pct = (excess / base * 100) if pd.notna(excess) and base else None
    lots = (excess * 1000 / per_lot) if pd.notna(excess) else float("nan")
    return {"name": name, "actual": actual, "baseline": base,
            "excess": excess, "lots": lots, "pct": pct}


def excess_rows(df, type_, year, month, method):
    """Actual minus normal baseline for every destination of one Type in a given
    month, in K bags and in exchange lots. Same method for Arabica and Robusta;
    only the bags-per-lot divisor differs. Europe is appended as a net row so a
    hub's 'excess' that is really a neighbour's shortfall (discharge-port
    switching) is visible rather than double-counted."""
    per_lot = BAGS_PER_LOT[type_]
    typed = df[(df["Type"] == type_) & df["Bags (K)"].notna()]
    dests = [d for d in sorted(typed["Destination"].unique()) if d != TOTAL]

    rows = []
    for d in dests:
        sub = typed[typed["Destination"] == d]
        cur = sub[(sub["Year"] == year) & (sub["Month"] == month)]["Bags (K)"]
        actual = float(cur.iloc[0]) if not cur.empty else float("nan")
        rows.append(_excess_row(d, actual, _baseline_value(sub, year, month, method), per_lot))

    rows.sort(key=lambda r: (r["excess"] if pd.notna(r["excess"]) else float("-inf")), reverse=True)

    europe = [r for r in rows if r["name"] in EUROPE_MEMBERS]
    totals = []
    if europe:
        totals.append(_excess_row(EUROPE_LABEL,
                                  sum(r["actual"] for r in europe if pd.notna(r["actual"])),
                                  sum(r["baseline"] for r in europe if pd.notna(r["baseline"])),
                                  per_lot))
    totals.append(_excess_row("All destinations",
                             sum(r["actual"] for r in rows if pd.notna(r["actual"])),
                             sum(r["baseline"] for r in rows if pd.notna(r["baseline"])),
                             per_lot))
    return rows, totals


TRAILING_WINDOWS = [6, 12, 24]


def _seasonal_index(series, ref_years=10):
    """Each calendar month's average share of its year's total, rescaled so the
    twelve months average 1.0. A flat trailing average is not a fair yardstick
    for a seasonal flow — Robusta ships ~43% above its annual average every
    August — so the baseline is multiplied by this to make the comparison
    month-appropriate. Built only from complete calendar years, so the current
    partial year can't skew the shape toward the months it happens to cover."""
    counts = series.groupby("Year")["Bags (K)"].count()
    totals = series.groupby("Year")["Bags (K)"].sum()
    complete = sorted(y for y in counts.index if counts[y] == 12 and totals[y] > 0)
    use = complete[-ref_years:]
    if not use:
        return {m: 1.0 for m in range(1, 13)}
    win = series[series["Year"].isin(use)].copy()
    win["share"] = win["Bags (K)"] / win["Year"].map(totals)
    idx = win.groupby("Month")["share"].mean() * 12
    mean = idx.mean()
    if mean:
        idx = idx / mean
    return {m: float(idx.get(m, 1.0)) for m in range(1, 13)}


def _excess_frame(df, type_, destination, window, ref_years):
    s = long_run_series(df, type_, destination).copy()
    if s.empty:
        return s.assign(Year=[], Month=[], Trailing=[], Baseline=[], Excess=[])
    s["Year"] = s["Date"].dt.year
    s["Month"] = s["Date"].dt.month
    idx = _seasonal_index(s, ref_years)
    # shift(1) so the baseline is what was normal *going into* the month, never
    # contaminated by the month being judged.
    s["Trailing"] = s["Bags (K)"].shift(1).rolling(window, min_periods=window).mean()
    s["Baseline"] = s["Trailing"] * s["Month"].map(idx)
    s["Excess"] = s["Bags (K)"] - s["Baseline"]
    return s


def trailing_excess_series(df, type_, destination, window=12, months=36, ref_years=10):
    """Monthly actual against a seasonally adjusted trailing baseline, with the
    gap expressed in lots and accumulated across the crop year. Unlike the
    single-month table this shows *when* a build started, not just that the
    latest month is high.

    For Arabica + Robusta combined the lot conversion is done per type before
    summing, since a KC lot (283.5 bags) and an RC lot (166.67) differ."""
    base = _excess_frame(df, type_, destination, window, ref_years)
    if base.empty:
        return base

    base = base.set_index("Date")
    if type_ == ALL_TYPES:
        lots = pd.Series(0.0, index=base.index)
        for t in BAGS_PER_LOT:
            part = _excess_frame(df, t, destination, window, ref_years)
            if part.empty:
                continue
            part = part.set_index("Date")
            lots = lots.add(part["Excess"] * 1000 / BAGS_PER_LOT[t], fill_value=0.0)
        base["Lots"] = lots.reindex(base.index)
    else:
        base["Lots"] = base["Excess"] * 1000 / BAGS_PER_LOT[type_]

    base = base.reset_index()
    base["CropStart"] = [y if m >= 7 else y - 1 for y, m in zip(base["Year"], base["Month"])]
    base["CumLots"] = base.groupby("CropStart")["Lots"].cumsum()
    return base.tail(months).reset_index(drop=True)
