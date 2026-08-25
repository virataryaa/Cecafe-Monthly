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


def geo_matrix_range(df, row_field, col_field, year_start, year_end, top_rows=8, top_cols=8):
    """row_field x col_field matrix of Bags (K) for a calendar-year range,
    restricted to each side's biggest players — e.g. which states route
    through which ports, or which states supply which destinations."""
    sub = df[(df["Year"] >= year_start) & (df["Year"] <= year_end)]
    r_order = [r for r, _ in geo_totals(sub, row_field)][:top_rows]
    c_order = [c for c, _ in geo_totals(sub, col_field)][:top_cols]
    sub = sub[sub[row_field].isin(r_order) & sub[col_field].isin(c_order)]
    matrix = sub.pivot_table(index=row_field, columns=col_field, values="Bags (K)", aggfunc="sum")
    return matrix.reindex(index=r_order, columns=c_order)


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


def hhi_trend(df, field):
    """Herfindahl-Hirschman Index of concentration per crop year for any
    field (State/Port/Destination) — 0-10,000; higher = more concentrated
    in fewer entities. For Destination it's buyer concentration; for
    State/Port it's how concentrated Brazil's own export geography is."""
    years = crop_year_order(df)
    pivot = df.pivot_table(index="CropYear", columns=field, values="Bags (K)", aggfunc="sum")
    pivot = pivot.reindex(years)
    totals = pivot.sum(axis=1)
    shares = pivot.div(totals, axis=0)
    hhi = (shares ** 2).sum(axis=1) * 10000
    return years, hhi.tolist()


def geo_value_totals(df, field, crop_year):
    """Total FOB value ($M) per entity for one crop year, descending —
    who brings in the most export revenue, not just the most volume."""
    sub = df[df["CropYear"] == crop_year]
    totals = sub.groupby(field)["VL_FOB"].sum().sort_values(ascending=False) / 1e6
    return [(k, v) for k, v in totals.items() if v > 0]


def avg_lane_size_trend(df):
    """Average Bags (K) per active State-Port-Destination combination
    ('trade lane') per crop year. Comexstat's public bulk export file is
    already a monthly aggregate by (NCM code, country, state, transport
    mode, customs office) — not one row per individual shipment/bill of
    lading, which Comexstat doesn't publish — so this is the closest
    available proxy for shipment size, not a literal one. Rising = volume
    concentrating into fewer, larger lanes; falling = spreading across
    more, smaller ones."""
    years = crop_year_order(df)
    grouped = df.groupby(["CropYear", "State", "Port", "Destination"])["Bags (K)"].sum().reset_index()
    grouped = grouped[grouped["Bags (K)"] > 0]
    avg = grouped.groupby("CropYear")["Bags (K)"].mean().reindex(years)
    return years, avg.tolist()


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


def monthly_totals(df):
    """Total Bags (K), FOB value (USD), and implied price ($/bag) per
    calendar month — the Comexstat side of the reconciliation vs CECAFE."""
    grouped = df.groupby("Date").agg(**{
        "Bags (K)": ("Bags (K)", "sum"),
        "FOB (USD)": ("VL_FOB", "sum"),
    }).reset_index()
    grouped["Price ($/bag)"] = grouped["FOB (USD)"] / (grouped["Bags (K)"] * 1000)
    return grouped.sort_values("Date")
