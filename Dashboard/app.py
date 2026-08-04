import os
from datetime import datetime

import streamlit as st

from data_loader import (load_raw, types, destinations, year_columns,
                          flow_wide, proportion_wide, DATA_PATH, TOTAL)
from charts import monthly_comparison, cumulative_forecast, min_max_avg, summary_table, ytd_comparison, overview_row
from table_html import raw_table_html, summary_table_html, overview_table_html

st.set_page_config(page_title="Cecafe: Brazil Coffee Exports", layout="wide")

CSS = """
<style>
.stApp { background-color: #ffffff; }
.block-container { max-width: 1400px; padding-top: 3rem; }

.cecafe-header-menu h1 {
    color: #1e3a5f;
    font-size: 28px;
    font-weight: 800;
    letter-spacing: 0.02em;
    text-align: center;
    margin: 0;
}

/* Default (menu list) buttons: minimalist cards */
div[data-testid="stButton"] { margin-bottom: 6px; }
.stButton>button {
    background-color: #f9f9f7;
    color: #0b0b0b;
    border: 1px solid #ececea;
    border-radius: 10px;
    width: 100%;
    padding: 11px 18px;
    text-align: left;
    font-size: 14px;
    font-weight: 500;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 1px 2px rgba(11, 11, 11, 0.02);
    transition: transform 0.15s ease, box-shadow 0.15s ease,
                border-color 0.15s ease, background-color 0.15s ease;
}
.stButton>button::after {
    content: "→";
    color: #c3c2b7;
    font-weight: 400;
    margin-left: 12px;
    transition: transform 0.15s ease, color 0.15s ease;
}
.stButton>button:hover {
    background-color: #ffffff;
    border-color: #0f766e;
    color: #0f766e;
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(15, 118, 110, 0.12);
}
.stButton>button:hover::after {
    color: #0f766e;
    transform: translateX(2px);
}

/* Dataset page header: plain text title + small Back button */
.st-key-dataset_header {
    padding: 6px 20px 18px;
}
.st-key-dataset_header h1 {
    color: #1e3a5f;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin: 0;
    text-align: center;
}
.st-key-dataset_header button {
    background-color: #f2f5f8 !important;
    border: 1px solid #dbe3ea !important;
    border-radius: 999px !important;
    color: #1e3a5f !important;
    font-weight: 500;
    font-size: 13px;
    padding: 6px 14px !important;
    width: auto !important;
    min-width: 0 !important;
    display: inline-flex !important;
    white-space: nowrap;
    box-shadow: none !important;
    transform: none !important;
}
.st-key-dataset_header button:hover {
    background-color: #e6edf5 !important;
    border-color: #1e3a5f !important;
}
.st-key-dataset_header button::after { content: none !important; }

/* Small muted pill bars (Overview period pickers) */
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
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "menu"

df = load_raw()
TYPES = types(df)          # ["Arabica", "Robusta"]
DESTS = destinations(df)   # excludes "Total"


def go_to(page):
    st.session_state.page = page


def _latest_period_label(type_):
    df_wide = flow_wide(df, type_, TOTAL)
    year_cols = year_columns(df_wide)
    current_year = year_cols[-1]
    s = df_wide[current_year]
    idx = s.last_valid_index()
    if idx is None:
        return current_year
    return f"{df_wide.loc[idx, 'Period']} {current_year}"


def render_menu():
    left, center, right = st.columns([1, 2, 1])
    with center:
        st.markdown(
            '<div style="text-align:center;"><div class="cecafe-header-menu"><h1>CECAFE</h1></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="text-align:center;color:#898781;font-size:13px;margin-top:6px;">'
            'Brazil Green Coffee Exports &middot; Monthly by Destination</div>',
            unsafe_allow_html=True,
        )

        updated_str = datetime.fromtimestamp(os.path.getmtime(DATA_PATH)).strftime("%d %b %Y, %H:%M")
        arabica_latest = _latest_period_label("Arabica")
        robusta_latest = _latest_period_label("Robusta")
        st.markdown(
            f'<div style="text-align:center;color:#898781;font-size:12px;margin:10px 0 18px;">'
            f'Data last updated {updated_str} &nbsp;&middot;&nbsp; '
            f'Arabica through {arabica_latest} &nbsp;&middot;&nbsp; '
            f'Robusta through {robusta_latest}</div>',
            unsafe_allow_html=True,
        )

        st.button("Overview", key="menu_Overview", on_click=go_to, args=("Overview",),
                   use_container_width=True)

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown('<div class="section-label">Arabica</div>', unsafe_allow_html=True)
            for dest in DESTS + [TOTAL]:
                st.button(dest, key=f"menu_Arabica_{dest}",
                           on_click=go_to, args=(f"Arabica||{dest}",), use_container_width=True)
        with col_right:
            st.markdown('<div class="section-label">Robusta</div>', unsafe_allow_html=True)
            for dest in DESTS + [TOTAL]:
                st.button(dest, key=f"menu_Robusta_{dest}",
                           on_click=go_to, args=(f"Robusta||{dest}",), use_container_width=True)


def render_overview():
    with st.container(key="dataset_header"):
        col_back, col_title, col_spacer = st.columns([1, 5, 1], vertical_alignment="center")
        with col_back:
            st.button("← Back", on_click=go_to, args=("menu",))
        with col_title:
            st.markdown("<h1>Overview</h1>", unsafe_allow_html=True)

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
        for dest in DESTS + [TOTAL]:
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


def render_dataset(type_, destination):
    with st.container(key="dataset_header"):
        col_back, col_title, col_spacer = st.columns([1, 5, 1], vertical_alignment="center")
        with col_back:
            st.button("← Back", on_click=go_to, args=("menu",))
        with col_title:
            st.markdown(f"<h1>{type_} Exports &middot; {destination}</h1>", unsafe_allow_html=True)

    df_wide = flow_wide(df, type_, destination)
    year_cols = year_columns(df_wide)
    unit = "K bags"

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


if st.session_state.page == "menu":
    render_menu()
elif st.session_state.page == "Overview":
    render_overview()
else:
    type_, destination = st.session_state.page.split("||")
    render_dataset(type_, destination)
