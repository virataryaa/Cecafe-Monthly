import os
from datetime import datetime

import pandas as pd
import streamlit as st

from data_loader import (load_raw, types, destinations_for_type, types_traded, year_columns,
                          flow_wide, proportion_wide, compare_wide, get_crop_years,
                          destination_mix, destination_month_matrix, long_run_series,
                          robusta_share_series, monthly_type_mix, ytd_period_window,
                          month_options, month_label, crop_years_overlapping_months,
                          DATA_PATH, TOTAL, ALL_TYPES, EUROPE_LABEL)
from charts import (monthly_comparison, cumulative_forecast, min_max_avg, summary_table,
                     ytd_comparison, compare_series, pie_breakdown, ranking_bar,
                     destination_heatmap, long_run_line, rolling_12m_line, share_line, monthly_mix_bars,
                     scatter_with_trend, price_share_combined,
                     price_volume_combined, granger_pvalue_bar, stacked_bars, dual_line,
                     dual_axis_two_series, SERIES)
from table_html import seasonal_table_html, summary_table_html, overview_table_html
import luis_loader as pi
import economics_loader as econ

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
.card-desc {
    font-size: 12px;
    color: #898781;
    margin: -4px 0 10px;
    line-height: 1.4;
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

tab_detail, tab_insights, tab_price_impact, tab_economics = st.tabs(
    ["Detail", "Insights", "Price vs Exports", "Brazil Economics"])

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

    long_run = long_run_series(df, type_, destination)
    window = st.radio("Rolling window", [1, 3, 6, 12], index=3, horizontal=True,
                       format_func=lambda m: f"{m} Month" if m == 1 else f"{m} Months",
                       key=f"rolling_window_{type_}_{destination}", label_visibility="collapsed")
    st.plotly_chart(
        rolling_12m_line(long_run["Date"], long_run["Bags (K)"],
                          title=f"Rolling {window}-Month Total", height=PANEL_H, window=window),
        use_container_width=True,
    )

    bottom_cols = st.columns([1, 3])
    with bottom_cols[0]:
        table, period_label = summary_table(df_wide, year_cols, "flow")
        st.markdown(summary_table_html(table, period_label, unit), unsafe_allow_html=True)
    with bottom_cols[1]:
        # Match the bar chart's height to the compact HTML table's rendered
        # height (~22px header + ~18px per crop-year row) instead of a fixed value.
        table_height = 24 + 18 * len(year_cols)
        st.plotly_chart(ytd_comparison(df_wide, year_cols, kind="flow", height=table_height),
                         use_container_width=True)

    ytd_periods, ytd_label = ytd_period_window(df_wide, year_cols)

    st.markdown(
        seasonal_table_html(df_wide, year_cols, title=f"{lbl} Exports to {destination}", unit=unit, kind="flow",
                             ytd_label=ytd_label),
        unsafe_allow_html=True,
    )

    if destination != TOTAL:
        prop_wide = proportion_wide(df, type_, destination)
        prop_year_cols = year_columns(prop_wide)
        total_wide = flow_wide(df, type_, TOTAL)

        def _weighted_ratio(periods):
            # Properly volume-weighted % (sum of dest / sum of total over the
            # given periods), not an average of the monthly percentages.
            d = df_wide.set_index("Period").loc[periods]
            t = total_wide.set_index("Period").loc[periods]
            return pd.Series({
                y: (d[y].sum(skipna=True) / t[y].sum(skipna=True) * 100)
                for y in prop_year_cols if t[y].sum(skipna=True)
            })

        weighted_ytd = _weighted_ratio(ytd_periods)
        weighted_full = _weighted_ratio(df_wide["Period"].tolist())
        st.markdown(
            seasonal_table_html(prop_wide, prop_year_cols,
                                 title=f"{destination} — Share of Total {lbl} Exports", unit="%", kind="ratio",
                                 ytd_series=weighted_ytd, ytd_label=f"{ytd_label} %",
                                 full_series=weighted_full, full_label="Full Year %"),
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
    col_type, col_range, _ = st.columns([1, 2, 2])
    with col_type:
        type_ins = st.selectbox("Type", TYPES, key="insights_type")
    months = month_options(df)
    month_labels = [month_label(m) for m in months]
    default_start_idx = max(0, len(months) - 12)
    with col_range:
        start_lbl, end_lbl = st.select_slider(
            "Month Range", options=month_labels,
            value=(month_labels[default_start_idx], month_labels[-1]),
            key=f"insights_month_range_{type_ins}",
        )
    i0, i1 = month_labels.index(start_lbl), month_labels.index(end_lbl)
    start_ym, end_ym = months[i0], months[i1]
    range_years = crop_years_overlapping_months(df, start_ym, end_ym)
    lbl_ins = type_label(type_ins)
    range_caption = start_lbl if start_lbl == end_lbl else f"{start_lbl}–{end_lbl}"

    mix = destination_mix(df, type_ins, start_ym, end_ym)

    with st.expander(f"Share of Exports — {lbl_ins} ({range_caption})", expanded=True):
        if mix:
            labels = [d for d, _ in mix]
            values = [v for _, v in mix]
            st.plotly_chart(pie_breakdown(labels, values, "Share of Exports", height=PANEL_H),
                             use_container_width=True)
        else:
            st.info("No data for this Type / Month range.")

    with st.expander(f"Top Destinations — {lbl_ins} ({range_caption})", expanded=True):
        if mix:
            st.plotly_chart(
                ranking_bar(labels, values, "Top Destinations", top_n=len(labels),
                            height=max(PANEL_H, 30 * len(labels) + 80)),
                use_container_width=True,
            )
        else:
            st.info("No data for this Type / Month range.")

    matrix = destination_month_matrix(df, type_ins, start_ym, end_ym)
    with st.expander(f"Destination × Month — {lbl_ins} ({range_caption})", expanded=True):
        if not matrix.empty:
            st.plotly_chart(
                destination_heatmap(matrix, f"{lbl_ins} Exports by Destination & Month (K bags)",
                                     height=max(280, 40 * len(matrix) + 100)),
                use_container_width=True,
            )
        else:
            st.info("No data for this Type / Month range.")

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
    st.markdown(
        '<div class="card-desc">Robusta bags &divide; (Arabica bags + Robusta bags) &times; 100, '
        'summing full crop-year (Jul&ndash;Jun) totals for the selected destination — i.e. what share '
        'of that destination\'s combined coffee imports from Brazil was Robusta rather than Arabica.</div>',
        unsafe_allow_html=True,
    )
    mix_dest_options = destinations_for_type(df, ALL_TYPES) + [EUROPE_LABEL, TOTAL]
    mix_dest = st.selectbox("Destination", mix_dest_options, key="insights_mix_dest")
    traded = types_traded(df, mix_dest)
    if len(traded) < 2:
        only = traded[0] if traded else "no"
        st.info(f"{mix_dest} only receives {only} exports in this dataset — "
                f"there's no Arabica/Robusta mix to show here.")
    else:
        share = robusta_share_series(df, mix_dest)
        share_windowed = [(y, v) for y, v in share if y in range_years]
        st.plotly_chart(
            share_line([y for y, _ in share_windowed], [v for _, v in share_windowed],
                       f"Robusta Share of Combined Exports to {mix_dest} ({range_caption})", height=PANEL_H),
            use_container_width=True,
        )

        monthly_mix = monthly_type_mix(df, mix_dest, range_years)
        st.plotly_chart(
            monthly_mix_bars(monthly_mix["Date"], monthly_mix["Arabica"], monthly_mix["Robusta"],
                              monthly_mix["RobustaSharePct"],
                              f"Monthly Arabica vs Robusta Exports to {mix_dest} ({range_caption})",
                              height=PANEL_H),
            use_container_width=True,
        )

with tab_price_impact:
    st.markdown('<div class="section-label">Robusta Price &rarr; Robusta Export Share</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="card-desc">Brazil\'s total (world) coffee exports, Conillon (Robusta) vs Arabica, '
        '1999&ndash;present. Of everything tested &mdash; Arabica price, Robusta price, the '
        'Arabica-Robusta spread, and BRL/USD FX &mdash; only <b>Robusta\'s own price</b> passed a Granger '
        'causality test as a genuine leading indicator of Robusta\'s export share, at a 7&ndash;12 month lag.</div>',
        unsafe_allow_html=True,
    )

    granger = pi.granger_scan("Robusta", maxlag=pi.MAX_LAG)
    sig_lags = granger.loc[granger["PValue"] < 0.05, "Lag"]
    default_lag = int(sig_lags.max()) if not sig_lags.empty else pi.MAX_LAG

    lag = st.slider("Lag (months)", 1, pi.MAX_LAG, value=default_lag, key="pi_lag",
                     help="Months by which Robusta price leads Robusta export share.")

    merged = pi.lagged_merge(lag)
    robusta_unit = pi.PRICE_UNITS["Robusta"]
    st.plotly_chart(
        price_share_combined(merged["Date"], merged["Robusta"], merged["RobustaSharePct"],
                              f"Robusta Price ({robusta_unit})", "Robusta Share (%)",
                              f"Robusta Price (lag {lag}m) vs Robusta Export Share", height=PANEL_H + 60,
                              price_color=SERIES["orange"], price_unit=robusta_unit),
        use_container_width=True,
    )

    cols_pi = st.columns([1, 1])
    with cols_pi[0]:
        st.plotly_chart(
            scatter_with_trend(merged["Robusta"], merged["RobustaSharePct"],
                                f"Robusta Price ({robusta_unit})", "Robusta Share (%)",
                                f"Robusta Price (lag {lag}m) vs Share", height=PANEL_H, y_pct=True),
            use_container_width=True,
        )
    with cols_pi[1]:
        st.plotly_chart(
            granger_pvalue_bar(granger["Lag"], granger["PValue"],
                                "Granger Test: Robusta Price -> Share (p-value by lag)", height=PANEL_H),
            use_container_width=True,
        )

    st.markdown('<div class="section-label">Arabica Price &rarr; Arabica Export Share</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="card-desc">Same test, run on Arabica: does Arabica\'s own price help predict '
        'Arabica\'s own share of total exports? <b>It does not pass the Granger test at any lag</b> '
        '(best p &asymp; 0.10) &mdash; shown here in full, not summarized, so both commodities get the '
        'same transparent treatment.</div>',
        unsafe_allow_html=True,
    )

    granger_ar = pi.granger_scan("Arabica", maxlag=pi.MAX_LAG, share_col="ArabicaSharePct")
    sig_lags_ar = granger_ar.loc[granger_ar["PValue"] < 0.05, "Lag"]
    default_lag_ar = int(sig_lags_ar.max()) if not sig_lags_ar.empty else pi.MAX_LAG

    lag_ar = st.slider("Lag (months)", 1, pi.MAX_LAG, value=default_lag_ar, key="pi_lag_arabica",
                        help="Months by which Arabica price leads Arabica export share.")

    merged_ar = pi.lagged_merge(lag_ar, share_col="ArabicaSharePct")
    arabica_unit = pi.PRICE_UNITS["Arabica"]
    st.plotly_chart(
        price_share_combined(merged_ar["Date"], merged_ar["Arabica"], merged_ar["ArabicaSharePct"],
                              f"Arabica Price ({arabica_unit})", "Arabica Share (%)",
                              f"Arabica Price (lag {lag_ar}m) vs Arabica Export Share", height=PANEL_H + 60,
                              price_color=SERIES["blue"], price_unit=arabica_unit),
        use_container_width=True,
    )

    cols_ar = st.columns([1, 1])
    with cols_ar[0]:
        st.plotly_chart(
            scatter_with_trend(merged_ar["Arabica"], merged_ar["ArabicaSharePct"],
                                f"Arabica Price ({arabica_unit})", "Arabica Share (%)",
                                f"Arabica Price (lag {lag_ar}m) vs Share", height=PANEL_H, y_pct=True),
            use_container_width=True,
        )
    with cols_ar[1]:
        st.plotly_chart(
            granger_pvalue_bar(granger_ar["Lag"], granger_ar["PValue"],
                                "Granger Test: Arabica Price -> Share (p-value by lag)", height=PANEL_H),
            use_container_width=True,
        )

    st.markdown('<div class="section-label">Export Volume vs Own Price (Arabica &amp; Robusta)</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="card-desc">Each type\'s own export volume (K bags) against its own price, at a '
        'chosen lag &mdash; exploratory only. <b>Neither passes the Granger test at any lag</b> '
        '(best p &asymp; 0.07&ndash;0.09 for both Arabica and Robusta), so treat this as a chart to look '
        'at, not a validated relationship like the Robusta price/share one above.</div>',
        unsafe_allow_html=True,
    )
    vol_type = st.selectbox("Type", ["Arabica", "Robusta"], key="pi_vol_type")
    vol_lag = st.slider("Lag (months)", 0, pi.MAX_LAG, value=6, key=f"pi_vol_lag_{vol_type}",
                         help=f"Months by which {vol_type} price leads {vol_type} export volume.")

    vol_unit = pi.PRICE_UNITS[vol_type]
    vol_merged = pi.lagged_merge_volume(vol_type, vol_lag)
    st.plotly_chart(
        price_volume_combined(vol_merged["Date"], vol_merged["Price"], vol_merged["Volume"],
                               f"{vol_type} Price ({vol_unit})", f"{vol_type} Volume (K bags)",
                               f"{vol_type} Price (lag {vol_lag}m) vs {vol_type} Export Volume", height=PANEL_H + 60,
                               price_unit=vol_unit),
        use_container_width=True,
    )
    cols_vol = st.columns([1, 1])
    with cols_vol[0]:
        st.plotly_chart(
            scatter_with_trend(vol_merged["Price"], vol_merged["Volume"],
                                f"{vol_type} Price ({vol_unit})", f"{vol_type} Volume (K bags)",
                                f"{vol_type} Price (lag {vol_lag}m) vs Volume", height=PANEL_H),
            use_container_width=True,
        )
    with cols_vol[1]:
        granger_vol = pi.granger_scan_volume(vol_type, maxlag=pi.MAX_LAG)
        st.plotly_chart(
            granger_pvalue_bar(granger_vol["Lag"], granger_vol["PValue"],
                                f"Granger Test: {vol_type} Price -> {vol_type} Volume (p-value by lag)",
                                height=PANEL_H),
            use_container_width=True,
        )

with tab_economics:
    df_econ = econ.load_economics()
    year_cols_econ = econ.crop_year_order(df_econ)

    st.markdown(
        '<div class="card-desc">Brazil\'s coffee export <b>revenue</b> and <b>realized average export '
        'price</b> (Revenue &divide; Volume), from Cecafe Economics &mdash; distinct from the physical '
        'volumes in the Detail/Insights tabs and from the NY/London futures quotes in Price vs Exports. '
        f'Monthly, {df_econ["Date"].min():%b %Y}&ndash;{df_econ["Date"].max():%b %Y}, no gaps.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">Total Export Revenue</div>', unsafe_allow_html=True)
    cols_rev = st.columns([1, 1])
    with cols_rev[0]:
        st.plotly_chart(
            stacked_bars(df_econ["Date"],
                         [("Arabica", df_econ[econ.COLS["Arabica"]["revenue"]]),
                          ("Robusta", df_econ[econ.COLS["Robusta"]["revenue"]])],
                         "Monthly Export Revenue", height=PANEL_H, yaxis_title="k USD"),
            use_container_width=True,
        )
    with cols_rev[1]:
        st.plotly_chart(
            rolling_12m_line(df_econ["Date"], df_econ["Total Revenue"],
                              "Rolling 12-Month Total Revenue", height=PANEL_H, yaxis_title="k USD"),
            use_container_width=True,
        )

    st.markdown('<div class="section-label">Revenue Mix — Arabica vs Robusta</div>', unsafe_allow_html=True)
    st.plotly_chart(
        share_line(df_econ["Date"], df_econ["Robusta Revenue SharePct"],
                   "Robusta Share of Combined Export Revenue", height=PANEL_H),
        use_container_width=True,
    )

    st.markdown('<div class="section-label">Crop-Year Revenue (Jul&ndash;Jun)</div>', unsafe_allow_html=True)
    st.markdown(
        seasonal_table_html(econ.econ_wide(df_econ, "Total Revenue"), year_cols_econ,
                             title="Total Export Revenue", unit="k USD", kind="flow"),
        unsafe_allow_html=True,
    )
    cols_rev_split = st.columns([1, 1])
    with cols_rev_split[0]:
        st.markdown(
            seasonal_table_html(econ.econ_wide(df_econ, econ.COLS["Arabica"]["revenue"]), year_cols_econ,
                                 title="Arabica Export Revenue", unit="k USD", kind="flow"),
            unsafe_allow_html=True,
        )
    with cols_rev_split[1]:
        st.markdown(
            seasonal_table_html(econ.econ_wide(df_econ, econ.COLS["Robusta"]["revenue"]), year_cols_econ,
                                 title="Robusta Export Revenue", unit="k USD", kind="flow"),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-label">Realized Export Price per Bag</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-desc">Revenue &divide; Volume each month &mdash; Brazil\'s own blended '
        'realized price, not a market quote.</div>',
        unsafe_allow_html=True,
    )
    cols_price = st.columns([1, 1])
    with cols_price[0]:
        st.plotly_chart(
            dual_line(df_econ["Date"],
                      [("Arabica", df_econ[econ.COLS["Arabica"]["price"]]),
                       ("Robusta", df_econ[econ.COLS["Robusta"]["price"]])],
                      "Realized Price ($ per Bag) — Full History", height=PANEL_H, yaxis_title="$ per Bag"),
            use_container_width=True,
        )
    with cols_price[1]:
        vol_window = 12
        ar_vol = df_econ[econ.COLS["Arabica"]["price"]].rolling(vol_window, min_periods=vol_window).std()
        ro_vol = df_econ[econ.COLS["Robusta"]["price"]].rolling(vol_window, min_periods=vol_window).std()
        st.plotly_chart(
            dual_line(df_econ["Date"], [("Arabica", ar_vol), ("Robusta", ro_vol)],
                      f"Price Volatility — Rolling {vol_window}-Month Std Dev", height=PANEL_H,
                      yaxis_title="$ per Bag"),
            use_container_width=True,
        )

    st.markdown('<div class="section-label">Realized Price vs Futures Price</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card-desc">Brazil\'s realized $/bag export price against the matching NY (Arabica) '
        'or London (Robusta) futures quote for the same month &mdash; a level cross-check, not a lagged '
        'or causal test like the Price vs Exports tab.</div>',
        unsafe_allow_html=True,
    )
    for pi_type in ["Arabica", "Robusta"]:
        merged_px, futures_unit = econ.price_vs_futures(pi_type)
        cols_px = st.columns([1, 1])
        with cols_px[0]:
            st.plotly_chart(
                dual_axis_two_series(
                    merged_px["Date"], merged_px["Realized"], merged_px["Futures"],
                    "Realized ($/bag)", f"Futures ({futures_unit})",
                    f"{pi_type} — Realized vs Futures Price", height=PANEL_H,
                    unit1="$ per Bag", unit2=futures_unit,
                ),
                use_container_width=True,
            )
        with cols_px[1]:
            st.plotly_chart(
                scatter_with_trend(merged_px["Futures"], merged_px["Realized"],
                                    f"Futures ({futures_unit})", "Realized ($/bag)",
                                    f"{pi_type} — Futures vs Realized", height=PANEL_H),
                use_container_width=True,
            )
