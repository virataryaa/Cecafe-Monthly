import os
from datetime import datetime

import streamlit as st

from data_loader import (load_raw, types, destinations_for_type, year_columns,
                          flow_wide, proportion_wide, DATA_PATH, TOTAL)
from charts import monthly_comparison, cumulative_forecast, min_max_avg, summary_table, ytd_comparison, overview_row
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
div[data-testid="stSelectbox"] label p {
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #898781 !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] {
    border-radius: 8px;
}

/* Pill bars (Overview period pickers) */
div[class*="_period_wrap"] button {
    font-size: 12px !important;
    padding: 3px 12px !important;
    min-height: 0 !important;
    color: #898781 !important;
    border-color: #e1e0d9 !important;
    background-color: #fbfbfa !important;
}
div[class*="_period_wrap"] button p {
    font-size: 12px !important;
    color: inherit !important;
}
div[class*="_period_wrap"] button[aria-pressed="true"],
div[class*="_period_wrap"] button[aria-checked="true"] {
    color: #52514e !important;
    border-color: #c3c2b7 !important;
    background-color: #f2f1ee !important;
    font-weight: 600;
}

.section-label {
    font-size: 13px;
    font-weight: 700;
    color: #898781;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 4px 0 8px;
}

/* Tabs */
button[data-baseweb="tab"] p { font-size: 13px !important; font-weight: 600; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

df = load_raw()
TYPES = types(df)  # ["Arabica", "Robusta"]


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

tab_detail, tab_overview = st.tabs(["Detail", "Overview"])


def render_detail():
    col_type, col_dest, _ = st.columns([1, 1, 3])
    with col_type:
        type_ = st.selectbox("Type", TYPES, key="slicer_type")
    dest_options = destinations_for_type(df, type_) + [TOTAL]
    with col_dest:
        destination = st.selectbox("Destination", dest_options, key=f"slicer_destination_{type_}")

    df_wide = flow_wide(df, type_, destination)
    year_cols = year_columns(df_wide)
    unit = "K bags"

    st.markdown(f"#### {type_} Exports &middot; {destination}", unsafe_allow_html=True)

    PANEL_H = 330
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
        raw_table_html(df_wide, year_cols, title=f"{type_} Exports to {destination}", unit=unit, kind="flow"),
        unsafe_allow_html=True,
    )

    if destination != TOTAL:
        prop_wide = proportion_wide(df, type_, destination)
        prop_year_cols = year_columns(prop_wide)
        st.markdown(
            raw_table_html(prop_wide, prop_year_cols,
                            title=f"{destination} — Share of Total {type_} Exports", unit="%", kind="ratio"),
            unsafe_allow_html=True,
        )


def render_overview():
    def _render_group(type_):
        ref_wide = flow_wide(df, type_, TOTAL)
        year_cols = year_columns(ref_wide)
        current_year = year_cols[-1]
        mask = ref_wide[current_year].notna()
        periods = ref_wide.loc[mask, "Period"].tolist()
        if not periods:
            return
        label_to_idx = dict(zip(periods, ref_wide.loc[mask].index.tolist()))

        st.markdown(f'<div class="section-label">{type_}</div>', unsafe_allow_html=True)
        with st.container(key=f"overview_{type_}_period_wrap"):
            selected = st.pills(
                f"{type_} period", options=periods, default=periods[-1],
                selection_mode="single", key=f"overview_{type_}_period",
                label_visibility="collapsed",
            )
        if selected is None:
            selected = periods[-1]
        period_idx = label_to_idx[selected]

        standalone_rows, cumulative_rows = [], []
        for dest in destinations_for_type(df, type_) + [TOTAL]:
            dest_wide = flow_wide(df, type_, dest)
            r = overview_row(dest_wide, year_cols, "flow", idx=period_idx)
            standalone_rows.append({**r["standalone"], "name": dest, "unit": "K bags", "period": r["period"]})
            cumulative_rows.append({**r["cumulative"], "name": dest, "unit": "K bags", "period": r["period"]})

        prev_year, cy = year_cols[-2], year_cols[-1]
        left, right = st.columns(2)
        with left:
            st.markdown(overview_table_html(standalone_rows, f"{type_} — Monthly", prev_year, cy),
                        unsafe_allow_html=True)
        with right:
            st.markdown(overview_table_html(cumulative_rows, f"{type_} — Cumulative YTD", prev_year, cy),
                        unsafe_allow_html=True)

    _render_group("Arabica")
    _render_group("Robusta")


with tab_detail:
    render_detail()

with tab_overview:
    render_overview()
