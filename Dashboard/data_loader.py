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
