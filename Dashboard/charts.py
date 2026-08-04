import numpy as np
import pandas as pd
import plotly.graph_objects as go

# Validated categorical slots (dark-mode steps) from the dataviz reference palette.
SERIES = {
    "blue": "#3987e5",
    "green": "#008300",
    "magenta": "#d55181",
    "yellow": "#c98500",
    "aqua": "#199e70",
    "orange": "#d95926",
    "violet": "#9085e9",
    "red": "#e66767",
}
GOOD = "#006300"
CRITICAL = "#d03b3b"
MUTED = "#898781"
GRID = "#e1e0d9"
INK = "#0b0b0b"
SURFACE = "#fcfcfb"
NAVY_SOFT = "#3d5d85"


def _layout(title, height=None):
    layout = dict(
        title=dict(text=title, x=0.01, xanchor="left", y=0.97, yanchor="top",
                   font=dict(size=15)),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=INK, family="system-ui, -apple-system, Segoe UI, sans-serif"),
        margin=dict(l=50, r=20, t=50, b=100),
        legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED),
                   tickformat=",.0f"),
    )
    if height:
        layout["height"] = height
    return layout


def _recent_year_cols(year_cols, n=6):
    return year_cols[-n:]


def _cumulative(df_wide, year_cols):
    cum = df_wide[year_cols].cumsum(skipna=True)
    return cum


def _projection_trace_xy(periods, actual_series, proj_vals, cumulative_base=None):
    """Builds the (x, y) for a dotted projection line that starts at the
    last actual data point and continues through proj_vals for whichever
    trailing periods it covers. If cumulative_base is given, y accumulates
    (running sum) instead of using proj_vals directly."""
    last_pos = actual_series.last_valid_index()
    if last_pos is None:
        return None, None
    x = [periods[last_pos]]
    running = cumulative_base[last_pos] if cumulative_base is not None else actual_series.iloc[last_pos]
    y = [running]
    for i in range(last_pos + 1, len(periods)):
        p = periods[i]
        if p not in proj_vals:
            break
        if cumulative_base is not None:
            running = running + proj_vals[p]
            y.append(running)
        else:
            y.append(proj_vals[p])
        x.append(p)
    if len(x) < 2:
        return None, None
    return x, y


def monthly_comparison(df_wide, year_cols, title="Monthly Comparison", height=None, proj_vals=None):
    periods = df_wide["Period"].tolist()
    shown_years = _recent_year_cols(year_cols, 6)
    palette_cycle = list(SERIES.values())
    fig = go.Figure()
    for i, yr in enumerate(shown_years):
        is_last = i == len(shown_years) - 1
        fig.add_trace(go.Scatter(
            x=periods, y=df_wide[yr],
            mode="lines+markers" if is_last else "lines",
            name=yr, connectgaps=True,
            line=dict(width=4 if is_last else 2,
                       color=INK if is_last else palette_cycle[i % len(palette_cycle)]),
            marker=dict(size=7, color=INK) if is_last else dict(size=0),
        ))
    if proj_vals:
        current_year = year_cols[-1]
        x, y = _projection_trace_xy(periods, df_wide[current_year], proj_vals)
        if x:
            fig.add_trace(go.Scatter(
                x=x, y=y, name=f"{current_year} (proj)", mode="lines+markers",
                line=dict(width=2, color=INK, dash="dot"),
                marker=dict(size=6, symbol="circle-open", color=INK),
            ))
    fig.update_layout(**_layout(title, height))
    return fig


def cumulative_forecast(df_wide, year_cols, title="Cumulative (to date)", height=None, proj_vals=None):
    periods = df_wide["Period"].tolist()
    cum = _cumulative(df_wide, year_cols)
    shown_years = _recent_year_cols(year_cols, 7)
    palette_cycle = list(SERIES.values())
    fig = go.Figure()
    for i, yr in enumerate(shown_years):
        is_last = i == len(shown_years) - 1
        fig.add_trace(go.Scatter(
            x=periods, y=cum[yr],
            mode="lines",
            name=yr, connectgaps=True,
            line=dict(width=4 if is_last else 2,
                       color=INK if is_last else palette_cycle[i % len(palette_cycle)]),
        ))
    if proj_vals:
        current_year = year_cols[-1]
        x, y = _projection_trace_xy(periods, df_wide[current_year], proj_vals,
                                     cumulative_base=cum[current_year])
        if x:
            fig.add_trace(go.Scatter(
                x=x, y=y, name=f"{current_year} (proj)", mode="lines+markers",
                line=dict(width=2, color=INK, dash="dot"),
                marker=dict(size=6, symbol="circle-open", color=INK),
            ))
    fig.update_layout(**_layout(title, height))
    return fig


def min_max_avg(df_wide, year_cols, title="Current vs Min / Max / Avg", height=None, proj_vals=None):
    periods = df_wide["Period"].tolist()
    current_year = year_cols[-1]
    history_years = [y for y in year_cols[:-1]]
    hist = df_wide[history_years]
    lo = hist.min(axis=1, skipna=True)
    hi = hist.max(axis=1, skipna=True)
    avg = hist.mean(axis=1, skipna=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=periods, y=lo, name="Min", mode="lines", connectgaps=True,
                              line=dict(width=2, color=SERIES["orange"], dash="dot")))
    fig.add_trace(go.Scatter(x=periods, y=hi, name="Max", mode="lines", connectgaps=True,
                              line=dict(width=2, color=SERIES["green"], dash="dot")))
    fig.add_trace(go.Scatter(x=periods, y=avg, name="Average", mode="lines", connectgaps=True,
                              line=dict(width=2, color=MUTED, dash="dash")))
    fig.add_trace(go.Scatter(x=periods, y=df_wide[current_year], name=current_year,
                              mode="lines+markers", connectgaps=True,
                              line=dict(width=3, color=INK),
                              marker=dict(size=7, symbol="diamond")))
    if proj_vals:
        x, y = _projection_trace_xy(periods, df_wide[current_year], proj_vals)
        if x:
            fig.add_trace(go.Scatter(
                x=x, y=y, name=f"{current_year} (proj)", mode="lines+markers",
                line=dict(width=2, color=INK, dash="dot"),
                marker=dict(size=6, symbol="circle-open", color=INK),
            ))
    fig.update_layout(**_layout(title, height))
    return fig


def _current_period_index(df_wide, year_cols):
    current_year = year_cols[-1]
    valid = df_wide[df_wide[current_year].notna()]
    if valid.empty:
        return 0
    return valid.index.max()


def summary_table(df_wide, year_cols, kind="flow"):
    idx = _current_period_index(df_wide, year_cols)
    period_label = df_wide.loc[idx, "Period"]
    if kind == "ratio":
        values = df_wide.loc[idx, year_cols]
        col_label = str(period_label)
    else:
        cum = _cumulative(df_wide, year_cols)
        values = cum.loc[idx, year_cols]
        col_label = f"Upto {period_label}"
    pct_change = values.pct_change(fill_method=None) * 100

    rows = []
    for yr in year_cols:
        rows.append({
            "Year": yr,
            col_label: values[yr],
            "% Change": pct_change[yr],
        })
    return pd.DataFrame(rows), period_label


def _pack_stats(series, current_year, prev_year, hist_years):
    latest = series[current_year]
    prev = series[prev_year]
    avg = series[hist_years].mean(skipna=True)
    yoy = (latest - prev) / prev * 100 if prev not in (0, None) and pd.notna(prev) else None
    vs_avg = (latest - avg) / avg * 100 if avg not in (0, None) and pd.notna(avg) else None
    return dict(latest=latest, prev=prev, yoy=yoy, vs_avg=vs_avg)


def overview_row(df_wide, year_cols, kind="flow", idx=None):
    """Returns both a standalone (single period reading) and a
    cumulative-to-date reading. For flow metrics, cumulative is a running
    sum. For ratio metrics — which have no meaningful sum — cumulative is
    the season-to-date average of the ratio (we don't store the underlying
    numerator/denominator needed for a true cumulative ratio).

    idx: explicit row position to read (e.g. a period the user picked via
    a slicer). Defaults to the latest period with current-year data."""
    if idx is None:
        idx = _current_period_index(df_wide, year_cols)
    period_label = df_wide.loc[idx, "Period"]
    current_year, prev_year = year_cols[-1], year_cols[-2]
    hist_years = year_cols[:-1]

    standalone = df_wide.loc[idx, year_cols]
    if kind == "flow":
        cum = _cumulative(df_wide, year_cols)
        cumulative = cum.loc[idx, year_cols]
    else:
        cumulative = df_wide.loc[:idx, year_cols].mean(skipna=True)

    return dict(
        period=period_label,
        standalone=_pack_stats(standalone, current_year, prev_year, hist_years),
        cumulative=_pack_stats(cumulative, current_year, prev_year, hist_years),
    )


def cumulative_ratio_stats(numerator_df, denominator_df, year_cols, idx, scale=1.0, denom_multiplier=1.0):
    """A properly volume-weighted cumulative ratio, derived from the
    underlying flow components (e.g. cumulative ATR / cumulative Cane),
    instead of averaging the ratio's own reported values period-to-period."""
    current_year, prev_year = year_cols[-1], year_cols[-2]
    hist_years = year_cols[:-1]

    num_cum = _cumulative(numerator_df, year_cols).loc[idx, year_cols]
    den_cum = _cumulative(denominator_df, year_cols).loc[idx, year_cols]
    ratio = num_cum / (den_cum * denom_multiplier) * scale

    return _pack_stats(ratio, current_year, prev_year, hist_years)


def remaining_periods(df_wide, year_cols):
    """Periods of the current (last) year column that haven't been
    reported yet — the trailing run of periods after the last actual value."""
    current_year = year_cols[-1]
    last_valid = df_wide[current_year].last_valid_index()
    if last_valid is None:
        return df_wide["Period"].tolist()
    return df_wide["Period"].iloc[last_valid + 1:].tolist()


def default_ytd_yoy(df_wide, year_cols):
    """Auto-suggested YoY% for the YTD Method: current YTD actual vs
    prior year's actual over the same periods reported so far."""
    current_year, prev_year = year_cols[-1], year_cols[-2]
    last_valid = df_wide[current_year].last_valid_index()
    if last_valid is None:
        return 0.0
    cy_ytd = df_wide[current_year].iloc[:last_valid + 1].sum(skipna=True)
    py_ytd = df_wide[prev_year].iloc[:last_valid + 1].sum(skipna=True)
    if py_ytd and py_ytd > 0:
        return round((cy_ytd / py_ytd - 1) * 100, 1)
    return 0.0


def _complete_years(df_wide, hist_years):
    return [y for y in hist_years if df_wide[y].notna().all()]


def _avg_seasonal_proportions(df_wide, ref_years):
    """For each period, its average share of that year's full-season
    total, averaged across ref_years."""
    ref_df = df_wide.set_index("Period")[ref_years].astype(float)
    ref_totals = ref_df.sum(axis=0)
    return ref_df.div(ref_totals, axis=1).mean(axis=1)


def project_ytd_method(df_wide, year_cols, yoy_pct, ref_years_n=5):
    """Scale each remaining period off last year's same-period value by
    yoy_pct. Falls back to the average of the last few years at that
    period if last year's value is missing/zero."""
    current_year, prev_year = year_cols[-1], year_cols[-2]
    hist_years = year_cols[:-1]
    rem = remaining_periods(df_wide, year_cols)
    by_period = df_wide.set_index("Period")
    proj = {}
    for p in rem:
        base = by_period.loc[p, prev_year]
        if pd.isna(base) or base <= 0:
            last_n = hist_years[-ref_years_n:]
            vals = by_period.loc[p, last_n].dropna()
            base = vals.mean() if not vals.empty else None
        if base is not None and pd.notna(base):
            proj[p] = float(base) * (1 + yoy_pct / 100)
    return proj


def project_proportions_method(df_wide, year_cols, ref_years_n=5):
    """Use the average seasonal shape of the last ref_years_n complete
    years plus actual YTD to imply a full-season total, then split the
    remainder across remaining periods by that same shape."""
    current_year = year_cols[-1]
    hist_years = year_cols[:-1]
    rem = remaining_periods(df_wide, year_cols)
    complete_years = _complete_years(df_wide, hist_years)
    ref_years = complete_years[-ref_years_n:]
    if not ref_years:
        return {}, None

    avg_props = _avg_seasonal_proportions(df_wide, ref_years)
    last_valid = df_wide[current_year].last_valid_index()
    actual_periods = df_wide["Period"].iloc[:last_valid + 1].tolist() if last_valid is not None else []
    act_prop_sum = avg_props[actual_periods].sum() if actual_periods else 0
    cy_ytd = df_wide[current_year].iloc[:last_valid + 1].sum(skipna=True) if last_valid is not None else 0

    ref_df = df_wide.set_index("Period")[ref_years].astype(float)
    implied_total = cy_ytd / act_prop_sum if act_prop_sum > 0 else ref_df.sum(axis=0).mean()

    proj = {p: float(implied_total * avg_props.get(p, 0)) for p in rem}
    return proj, implied_total


def project_manual_per_period(df_wide, year_cols, value):
    rem = remaining_periods(df_wide, year_cols)
    return {p: float(value) for p in rem}


def project_manual_yearly(df_wide, year_cols, target_total, ref_years_n=5):
    """Remaining budget = target - YTD actual, split across remaining
    periods by the average seasonal shape of recent complete years."""
    current_year = year_cols[-1]
    hist_years = year_cols[:-1]
    rem = remaining_periods(df_wide, year_cols)
    last_valid = df_wide[current_year].last_valid_index()
    cy_ytd = df_wide[current_year].iloc[:last_valid + 1].sum(skipna=True) if last_valid is not None else 0
    remaining_budget = max(0.0, float(target_total) - cy_ytd)

    complete_years = _complete_years(df_wide, hist_years)
    ref_years = complete_years[-ref_years_n:]
    if not ref_years or not rem:
        return {}, remaining_budget

    avg_props = _avg_seasonal_proportions(df_wide, ref_years)
    rem_prop_sum = avg_props[rem].sum()
    proj = {}
    if rem_prop_sum > 0:
        for p in rem:
            proj[p] = float(remaining_budget * avg_props.get(p, 0) / rem_prop_sum)
    return proj, remaining_budget


def ytd_comparison(df_wide, year_cols, kind="flow", title=None, height=None):
    table, period_label = summary_table(df_wide, year_cols, kind)
    value_col = table.columns[1]
    colors = [CRITICAL if v < 0 else GOOD if pd.notna(v) else MUTED for v in table["% Change"]]
    text = [f"{v:+.0f}%" if pd.notna(v) else "" for v in table["% Change"]]

    n = len(table)
    bar_colors = [NAVY_SOFT] * (n - 1) + [INK] if n else []

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=table["Year"], y=table[value_col],
        marker=dict(color=bar_colors, line=dict(color=SURFACE, width=1.5)),
        text=text, textposition="outside",
        textfont=dict(color=colors),
        name=value_col,
    ))
    base_title = title or ("YTD Comparison" if kind == "flow" else "Period Comparison")
    layout = _layout(f"{base_title} ({value_col})", height)
    fig.update_layout(showlegend=False, **layout)
    return fig
