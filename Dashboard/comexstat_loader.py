from pathlib import Path

import pandas as pd
import streamlit as st

from data_loader import MONTH_NAMES, PERIOD_ORDER, _crop_start, _crop_label

COMEXSTAT_DIR = Path(__file__).resolve().parent.parent / "Database" / "Comexstat"
COMEXSTAT_PATH = COMEXSTAT_DIR / "comexstat_coffee_exports.parquet"
URF_PATH = COMEXSTAT_DIR / "ref_urf.csv"
VIA_PATH = COMEXSTAT_DIR / "ref_via.csv"

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


def _geo_filter(df, field, entity):
    """entity == 'Total' means every row for that field (no filter) — the
    all-Brazil aggregate offered alongside individual states/ports/destinations."""
    return df if entity == "Total" else df[df[field] == entity]


def geo_long_run(df, field, entity):
    """Full chronological monthly Bags (K) history for one State, Port, or
    Destination (or 'Total' for all of Brazil) — feeds the drill-down chart."""
    sub = _geo_filter(df, field, entity)
    grouped = sub.groupby("Date", as_index=False)["Bags (K)"].sum().sort_values("Date")
    return grouped


def geo_wide(df, field, entity):
    """Period rows x CropYear columns of Bags (K) for one State, Port, or
    Destination (or 'Total') — same shape seasonal_table_html expects
    elsewhere in this app."""
    sub = _geo_filter(df, field, entity)
    pivot = sub.pivot_table(index="Period", columns="CropYear", values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(PERIOD_ORDER)
    years = crop_year_order(df)
    pivot = pivot.reindex(columns=years).reset_index()
    return pivot


def geo_price_totals(df, field, crop_year, top_n=10):
    """FOB value / bag for the top_n largest entities (by volume) within
    one crop year — restricted to each geography's biggest players so a
    handful of tiny or odd shipments can't produce a misleading per-bag
    price the way ranking by price directly would."""
    sub = df[df["CropYear"] == crop_year]
    grouped = sub.groupby(field).agg(bags=("Bags (K)", "sum"), fob=("VL_FOB", "sum"))
    grouped = grouped[grouped["bags"] > 0].sort_values("bags", ascending=False).head(top_n)
    grouped["price"] = grouped["fob"] / (grouped["bags"] * 1000)
    return list(zip(grouped.index, grouped["price"]))


def state_port_matrix(df, crop_year, top_states=8, top_ports=8):
    """State x Port matrix of Bags (K) for one crop year, restricted to
    each side's biggest players — which states route through which ports."""
    sub = df[df["CropYear"] == crop_year]
    s_order = [s for s, _ in geo_totals(sub, "State")][:top_states]
    p_order = [p for p, _ in geo_totals(sub, "Port")][:top_ports]
    sub = sub[sub["State"].isin(s_order) & sub["Port"].isin(p_order)]
    matrix = sub.pivot_table(index="State", columns="Port", values="Bags (K)", aggfunc="sum")
    return matrix.reindex(index=s_order, columns=p_order)


def geo_share_trend(df, field, top_n=5):
    """% share of that crop year's total Bags (K), per crop year, for the
    top_n entities (by all-time volume) — is any single state/port
    gaining or losing share over time, not just its raw size."""
    years = crop_year_order(df)
    top_entities = [k for k, _ in geo_totals(df, field)][:top_n]
    pivot = df.pivot_table(index="CropYear", columns=field, values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(years)
    totals = df.groupby("CropYear")["Bags (K)"].sum().reindex(years)
    shares = pivot[top_entities].div(totals, axis=0) * 100
    return years, [(e, shares[e].tolist()) for e in top_entities]


def destination_hhi_trend(df):
    """Herfindahl-Hirschman Index of destination concentration per crop
    year (0-10,000; higher = more concentrated in fewer buyers) — is
    Brazil's coffee buyer base diversifying or consolidating over time."""
    years = crop_year_order(df)
    pivot = df.pivot_table(index="CropYear", columns="Destination", values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(years)
    totals = pivot.sum(axis=1)
    shares = pivot.div(totals, axis=0)
    hhi = (shares ** 2).sum(axis=1) * 10000
    return years, hhi.tolist()


def geo_yoy_growth(df, field, crop_year, min_bags=20.0):
    """Year-over-year % change per entity, crop year vs the prior one,
    restricted to entities with at least min_bags K bags in either year
    so a near-zero base can't produce a meaningless 5,000% swing.

    Compared on a YTD-aligned basis — only the Jul-Jun periods the current
    crop year has actually reported so far — so a partial current year
    (e.g. just Jul) isn't compared against a prior full 12-month year,
    which would show a fake ~90%+ "decline" everywhere."""
    years = crop_year_order(df)
    if crop_year not in years or years.index(crop_year) == 0:
        return []
    prev_year = years[years.index(crop_year) - 1]
    covered = set(df.loc[df["CropYear"] == crop_year, "Period"])
    periods = [p for p in PERIOD_ORDER if p in covered]

    cur = df[(df["CropYear"] == crop_year) & (df["Period"].isin(periods))].groupby(field)["Bags (K)"].sum()
    prev = df[(df["CropYear"] == prev_year) & (df["Period"].isin(periods))].groupby(field)["Bags (K)"].sum()
    both = pd.concat([cur.rename("cur"), prev.rename("prev")], axis=1).fillna(0.0)
    both = both[(both["cur"] >= min_bags) | (both["prev"] >= min_bags)]
    both = both[both["prev"] > 0]
    both["yoy"] = (both["cur"] - both["prev"]) / both["prev"] * 100
    return list(both["yoy"].sort_values(ascending=False).items())


def non_maritime_share_trend(df):
    """% of exports NOT shipped by sea, per crop year — mostly road
    (Mercosur land-border trade); a rising trend would flag more overland
    trade than the historical near-100%-maritime norm."""
    via = pd.read_csv(VIA_PATH, sep=";", encoding="latin1")
    d = df.merge(via, on="CO_VIA", how="left")
    years = crop_year_order(df)
    pivot = d.pivot_table(index="CropYear", columns="NO_VIA", values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(years).fillna(0.0)
    maritime = pivot["MARITIMA"] if "MARITIMA" in pivot.columns else 0.0
    total = pivot.sum(axis=1)
    share = ((total - maritime) / total * 100).fillna(0.0)
    return years, share.tolist()


def small_destinations(df, crop_year, max_bags=5.0):
    """Destinations with a small but nonzero volume in one crop year —
    surfaces odd/unexpected buyers (e.g. Colombia, itself a major producer,
    buying Brazilian green coffee) worth a second look."""
    sub = df[df["CropYear"] == crop_year]
    grouped = sub.groupby("Destination").agg(**{
        "Bags (K)": ("Bags (K)", "sum"), "FOB (USD)": ("VL_FOB", "sum")})
    grouped = grouped[(grouped["Bags (K)"] > 0) & (grouped["Bags (K)"] <= max_bags)]
    grouped["Price ($/bag)"] = grouped["FOB (USD)"] / (grouped["Bags (K)"] * 1000)
    return grouped.sort_values("Bags (K)", ascending=False).reset_index()


def monthly_totals(df):
    """Total Bags (K), FOB value (USD), and implied price ($/bag) per
    calendar month — the Comexstat side of the reconciliation vs CECAFE."""
    grouped = df.groupby("Date").agg(**{
        "Bags (K)": ("Bags (K)", "sum"),
        "FOB (USD)": ("VL_FOB", "sum"),
    }).reset_index()
    grouped["Price ($/bag)"] = grouped["FOB (USD)"] / (grouped["Bags (K)"] * 1000)
    return grouped.sort_values("Date")
