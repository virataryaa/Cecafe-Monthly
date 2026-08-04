import os
from datetime import datetime

import pandas as pd
import streamlit as st

from data_loader import (load_raw, types, destinations_for_type, year_columns,
                          flow_wide, proportion_wide, compare_wide, get_crop_years,
                          destination_mix, destination_month_matrix, long_run_series,
                          robusta_share_series, DATA_PATH, TOTAL, ALL_TYPES, EUROPE_LABEL)
from charts import (monthly_comparison, cumulative_forecast, min_max_avg, summary_table,
                     ytd_comparison, compare_series, pie_breakdown, ranking_bar,
                     destination_heatmap, long_run_line, share_line)
from table_html import raw_table_html, summary_table_html, overview_table_html

st.set_page_config(page_title="Cecafe: Brazil Coffee Exports", layout="wide")

CSS = """
<style>
.stApp { background-color: #ffffff; }
.block-container { max-width: 1400px; padding-top: 2.5rem; }

.cecafe-header h1 {
    color: #1e3a5f;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: 0.02em;
    margin: 0;
}
.cecafe-header p {
    color: #898781;
    font-size: 13px;
    margin: 4px 0 0;
}

/* Slicer bar */
div[data-testid="stSelectbox"] label p,
div[data-testid="stMultiSelect"] label p {
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #898781 !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"],
div[data-testid="stMultiSelect"] div[data-baseweb="select"] {
    border-radius: 8px;
}

.section-label {
    font-size: 13px;
    font-weight: 700;
    color: #898781;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 16px 0 8px;
}

button[data-baseweb="tab"] p { font-size: 13px !important; font-weight: 600; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

df = load_raw()
TYPES = types(df)  # ["Arabica", "Robusta", "Total"]


def type_label(t):
    return "Arabica + Robusta" if t == ALL_TYPES else t


def _latest_period_label(type_):
    df_wide = flow_wide(df, type_, TOTAL)
    year_cols = year_columns(df_wide)
    current_year = year_cols[-1]
    s = df_wide[current_year]
    idx = s.last_valid_index()
    if idx is None:
        return current_year
    return f"{df_wide.loc[idx, 'Period']} {current_year}"


updated_str = datetime.fromtimestamp(os.path.getmtime(DATA_PATH)).strftime("%d %b %Y, %H:%M")
arabica_latest = _latest_period_label("Arabica")
robusta_latest = _latest_period_label("Robusta")
st.markdown(
    f'<div class="cecafe-header"><h1>CECAFE — Brazil Green Coffee Exports</h1>'
    f'<p>Data last updated {updated_str} &nbsp;&middot;&nbsp; '
    f'Arabica through {arabica_latest} &nbsp;&middot;&nbsp; '
    f'Robusta through {robusta_latest}</p></div>',
    unsafe_allow_html=True,
)
st.write("")

tab_detail, tab_insights = st.tabs(["Detail", "Insights"])

PANEL_H = 330


def render_single(type_, destination):
    df_wide = flow_wide(df, type_, destination)
    year_cols = year_columns(df_wide)
    unit = "K bags"
    lbl = type_label(type_)

    st.markdown(f"#### {lbl} Exports &middot; {destination}", unsafe_allow_html=True)

    cols = st.columns([1, 1])
    with cols[0]:
        st.plotly_chart(monthly_comparison(df_wide, year_cols, title="Monthly Exports", height=PANEL_H),
                         use_container_width=True)
        st.plotly_chart(min_max_avg(df_wide, year_cols, height=PANEL_H), use_container_width=True)
    with cols[1]:
        st.plotly_chart(
            cumulative_forecast(df_wide, year_cols, title="Cumulative Exports (crop year)", height=2 * PANEL_H + 40),
            use_container_width=True,
        )

    bottom_cols = st.columns([1, 3])
    with bottom_cols[0]:
        table, period_label = summary_table(df_wide, year_cols, "flow")
        st.markdown(summary_table_html(table, period_label, unit), unsafe_allow_html=True)
    with bottom_cols[1]:
        st.plotly_chart(ytd_comparison(df_wide, year_cols, kind="flow", height=PANEL_H),
                         use_container_width=True)

    st.markdown(
        raw_table_html(df_wide, year_cols, title=f"{lbl} Exports to {destination}", unit=unit, kind="flow"),
        unsafe_allow_html=True,
    )

    if destination != TOTAL:
        prop_wide = proportion_wide(df, type_, destination)
        prop_year_cols = year_columns(prop_wide)
        st.markdown(
            raw_table_html(prop_wide, prop_year_cols,
                            title=f"{destination} — Share of Total {lbl} Exports", unit="%", kind="ratio"),
            unsafe_allow_html=True,
        )


def render_compare(type_, dests):
    lbl = type_label(type_)
    ref_wide = flow_wide(df, type_, TOTAL)
    year_cols_full = year_columns(ref_wide)

    crop_year = st.selectbox("Crop Year", year_cols_full, index=len(year_cols_full) - 1,
                              key=f"compare_crop_year_{type_}")
    idx_sel = year_cols_full.index(crop_year)
    prev_year = year_cols_full[idx_sel - 1] if idx_sel > 0 else None

    st.markdown(f"#### {lbl} Exports &middot; {', '.join(dests)} &middot; {crop_year}",
                unsafe_allow_html=True)

    combined = compare_wide(df, type_, dests, crop_year)
    cols = st.columns([1, 1])
    with cols[0]:
        st.plotly_chart(compare_series(combined, dests, f"Monthly Exports — {crop_year}", height=PANEL_H),
                         use_container_width=True)
    with cols[1]:
        st.plotly_chart(
            compare_series(combined, dests, f"Cumulative Exports — {crop_year}", height=PANEL_H, cumulative=True),
            use_container_width=True,
        )

    rows = []
    for d in dests:
        w = flow_wide(df, type_, d)
        latest_total = w[crop_year].sum(skipna=True)
        prev_total = w[prev_year].sum(skipna=True) if prev_year else None
        yoy = None
        if prev_total not in (None, 0) and pd.notna(prev_total):
            yoy = (latest_total - prev_total) / prev_total * 100
        rows.append({"name": d, "period": crop_year, "prev": prev_total, "latest": latest_total,
                     "yoy": yoy, "vs_avg": None, "unit": "K bags"})
    st.markdown(
        overview_table_html(rows, f"{lbl} — Total by Destination", prev_year or "—", crop_year),
        unsafe_allow_html=True,
    )


with tab_detail:
    col_type, col_dest, _ = st.columns([1, 2, 2])
    with col_type:
        type_ = st.selectbox("Type", TYPES, key="slicer_type")
    dest_options = destinations_for_type(df, type_) + [EUROPE_LABEL, TOTAL]
    with col_dest:
        destination = st.multiselect("Destination", dest_options, default=[dest_options[0]],
                                      key=f"slicer_destination_{type_}")

    if not destination:
        st.info("Select at least one destination.")
    elif len(destination) == 1:
        render_single(type_, destination[0])
    else:
        render_compare(type_, destination)


with tab_insights:
    col_type, col_year, _ = st.columns([1, 2, 2])
    with col_type:
        type_ins = st.selectbox("Type", TYPES, key="insights_type")
    crop_years = get_crop_years(df, type_ins)
    with col_year:
        crop_year_ins = st.select_slider("Crop Year", options=crop_years, value=crop_years[-1],
                                          key="insights_crop_year")
    lbl_ins = type_label(type_ins)

    mix = destination_mix(df, type_ins, crop_year_ins)
    if mix:
        labels = [d for d, _ in mix]
        values = [v for _, v in mix]
        st.markdown(f'<div class="section-label">Destination Mix — {lbl_ins} {crop_year_ins}</div>',
                    unsafe_allow_html=True)
        cols = st.columns([1, 1])
        with cols[0]:
            st.plotly_chart(pie_breakdown(labels, values, "Share of Exports", height=PANEL_H),
                             use_container_width=True)
        with cols[1]:
            st.plotly_chart(ranking_bar(labels, values, "Top Destinations", height=PANEL_H),
                             use_container_width=True)
    else:
        st.info("No data for this Type / Crop Year.")

    matrix = destination_month_matrix(df, type_ins, crop_year_ins)
    if not matrix.empty:
        st.markdown(f'<div class="section-label">Destination &times; Month — {lbl_ins} {crop_year_ins}</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(
            destination_heatmap(matrix, f"{lbl_ins} Exports by Destination & Month (K bags)",
                                 height=max(280, 40 * len(matrix) + 100)),
            use_container_width=True,
        )

    st.markdown('<div class="section-label">Long-Run History</div>', unsafe_allow_html=True)
    longrun_dest_options = destinations_for_type(df, type_ins) + [EUROPE_LABEL, TOTAL]
    longrun_dest = st.selectbox("Destination", longrun_dest_options, key=f"insights_longrun_dest_{type_ins}")
    series = long_run_series(df, type_ins, longrun_dest)
    st.plotly_chart(
        long_run_line(series["Date"], series["Bags (K)"],
                      f"{lbl_ins} Exports to {longrun_dest} — Full History (2007–Present)", height=PANEL_H),
        use_container_width=True,
    )

    st.markdown('<div class="section-label">Arabica / Robusta Mix</div>', unsafe_allow_html=True)
    share = robusta_share_series(df)
    st.plotly_chart(
        share_line([y for y, _ in share], [v for _, v in share],
                   "Robusta Share of Combined Exports (by Crop Year)", height=PANEL_H),
        use_container_width=True,
    )
