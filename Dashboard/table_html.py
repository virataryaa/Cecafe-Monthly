import pandas as pd

from charts import GOOD, CRITICAL, GRID, INK, MUTED

LIGHT_GREEN = (234, 250, 240)
DARK_GREEN = (10, 110, 66)


def _green_shade(t):
    t = max(0.0, min(1.0, t))
    r = LIGHT_GREEN[0] + (DARK_GREEN[0] - LIGHT_GREEN[0]) * t
    g = LIGHT_GREEN[1] + (DARK_GREEN[1] - LIGHT_GREEN[1]) * t
    b = LIGHT_GREEN[2] + (DARK_GREEN[2] - LIGHT_GREEN[2]) * t
    return f"rgb({int(r)},{int(g)},{int(b)})", "#0b0b0b"


def _bar_cell(pct, scale=50, height=16, font_size=10):
    if pd.isna(pct):
        return ""
    color = CRITICAL if pct < 0 else GOOD
    width = max(4, min(abs(pct) / scale * 100, 100))
    return (
        f'<div style="position:relative;height:{height}px;background:#f2f1ee;'
        'border-radius:4px;overflow:hidden;">'
        f'<div style="position:absolute;top:0;left:0;height:100%;width:{width:.0f}%;'
        f'background:{color};opacity:0.28;"></div>'
        f'<div style="position:relative;z-index:1;text-align:center;font-size:{font_size}px;'
        f'line-height:{height}px;font-weight:700;color:{color};">{pct:+.2f}%</div>'
        '</div>'
    )


def _flatten(html):
    # st.markdown treats 4+ space indented lines as a code block, not HTML —
    # strip leading whitespace per line so the tags actually render.
    return "\n".join(line.strip() for line in html.strip().split("\n"))


_STYLE = f"""
<style>
.unica-table-wrap {{ overflow-x: auto; margin: 16px 0; border: 1px solid {GRID}; border-radius: 6px; }}
.unica-table {{ border-collapse: collapse; width: 100%; font-size: 11px;
                font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
.unica-table caption {{ text-align: left; font-weight: 700; font-size: 13px;
                         padding: 6px 10px; color: {INK}; }}
.unica-table th {{ background: #1e3a5f; color: white; padding: 3px 8px;
                    text-align: right; position: sticky; top: 0; white-space: nowrap; }}
.unica-table th.period-col, .unica-table td.period-col {{ text-align: left; font-style: italic;
                    color: {MUTED}; white-space: nowrap; }}
.unica-table td {{ padding: 2px 8px; line-height: 14px; text-align: right; white-space: nowrap; }}
.unica-table td.bar-cell {{ min-width: 70px; padding: 2px 6px; }}
.unica-table tr.total-row td {{ font-weight: 700; border-top: 2px solid {INK}; }}
</style>
"""


def _fmt(v, unit):
    if unit == "%":
        return f"{v:.1f}%"
    if unit == "kg/ton":
        return f"{v:.1f}"
    return f"{v:,.0f}"


def summary_table_html(table, period_label, unit=""):
    value_col = table.columns[1]
    values = table[value_col]
    vmin, vmax = values.min(), values.max()
    span = (vmax - vmin) or 1

    rows_html = []
    for _, row in table.iterrows():
        v = row[value_col]
        if pd.isna(v):
            val_cell = "<td></td>"
        else:
            t = (v - vmin) / span
            bg, txt = _green_shade(t)
            val_cell = f'<td style="background:{bg};color:{txt};">{_fmt(v, unit)}</td>'
        bar = _bar_cell(row["% Change"], height=14, font_size=9)
        rows_html.append(
            f'<tr><td class="period-col">{row["Year"]}</td>{val_cell}'
            f'<td class="bar-cell">{bar}</td></tr>'
        )

    return _flatten(f"""
    {_STYLE}
    <div class="unica-table-wrap">
    <table class="unica-table">
      <thead><tr><th class="period-col">Year</th><th>{value_col}</th><th>% Change</th></tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """)


_OVERVIEW_STYLE = f"""
<style>
.unica-overview-wrap {{ margin: 16px 0; border: 1px solid {GRID}; border-radius: 12px;
                         overflow-x: auto; box-shadow: 0 1px 4px rgba(11,11,11,0.05); }}
.unica-overview-title {{ font-size: 14px; font-weight: 700; color: {INK};
                          padding: 14px 16px 10px; }}
.unica-overview-table {{ border-collapse: collapse; width: 100%; font-size: 11px;
                          font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
.unica-overview-table th {{ background: #1e3a5f; color: white; padding: 8px 12px;
                             text-align: right; font-weight: 600; font-size: 10px;
                             text-transform: uppercase; letter-spacing: 0.02em; white-space: nowrap; }}
.unica-overview-table th.product-col {{ text-align: left; }}
.unica-overview-table td.product-col {{
    text-align: left; font-weight: 600; color: {INK}; }}
.unica-overview-table td {{ padding: 9px 12px; text-align: right;
                             border-top: 1px solid #f1f0ed; white-space: nowrap; }}
.unica-overview-table td.period-col {{ text-align: left; color: {MUTED};
                                        font-style: italic; font-size: 10.5px; }}
.unica-overview-table td.prev-col {{ color: {MUTED}; font-size: 11px; }}
.unica-overview-table td.latest-col {{ color: {INK}; font-weight: 700; font-size: 12px; }}
.unica-overview-table td.bar-cell {{ min-width: 90px; padding: 6px 12px; }}
.unica-overview-table tbody tr:hover td {{ background: #fafaf8; }}
</style>
"""


def overview_table_html(rows, title, prev_year, current_year):
    header = (
        '<th class="product-col">Product</th><th class="period-col">Period</th>'
        f'<th>{prev_year}</th><th>{current_year}</th><th>YoY</th><th>vs 10yr Avg</th>'
    )
    rows_html = []
    for r in rows:
        unit = r.get("unit", "")
        prev_cell = f'{_fmt(r["prev"], unit)}' if pd.notna(r["prev"]) else ""
        latest_cell = f'{_fmt(r["latest"], unit)}' if pd.notna(r["latest"]) else ""
        rows_html.append(
            f'<tr><td class="product-col">{r["name"]}</td>'
            f'<td class="period-col">{r["period"]}</td>'
            f'<td class="prev-col">{prev_cell}</td><td class="latest-col">{latest_cell}</td>'
            f'<td class="bar-cell">{_bar_cell(r["yoy"], height=16, font_size=9) if r["yoy"] is not None else ""}</td>'
            f'<td class="bar-cell">{_bar_cell(r["vs_avg"], height=16, font_size=9) if r["vs_avg"] is not None else ""}</td>'
            '</tr>'
        )

    return _flatten(f"""
    {_OVERVIEW_STYLE}
    <div class="unica-overview-wrap">
    <div class="unica-overview-title">{title}</div>
    <table class="unica-overview-table">
      <thead><tr>{header}</tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """)


_READ_CARD_STYLE = f"""
<style>
.read-card {{ display: flex; gap: 28px; align-items: center; margin: 12px 0 20px;
              padding: 18px 22px; border: 1px solid {GRID}; border-radius: 12px;
              background: #fafaf8; box-shadow: 0 1px 4px rgba(11,11,11,0.05); }}
.read-card-block {{ display: flex; flex-direction: column; }}
.read-card-label {{ font-size: 10px; font-weight: 700; color: {MUTED};
                     text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }}
.read-card-value {{ font-size: 22px; font-weight: 800; color: {INK}; white-space: nowrap; }}
.read-card-sub {{ font-size: 11px; color: {MUTED}; margin-top: 2px; }}
.read-card-arrow {{ font-size: 20px; color: {MUTED}; }}
</style>
"""


def current_read_card_html(read):
    """A single headline stat card: today's Robusta price -> the historically
    implied Robusta export share ~lag months out, with a rough +/- band."""
    lo = read["projected_share"] - read["resid_std"]
    hi = read["projected_share"] + read["resid_std"]
    return _flatten(f"""
    {_READ_CARD_STYLE}
    <div class="read-card">
      <div class="read-card-block">
        <div class="read-card-label">Robusta Price ({read['latest_date'].strftime('%b %Y')})</div>
        <div class="read-card-value">${read['latest_price']:,.0f}/bag</div>
      </div>
      <div class="read-card-arrow">&rarr;</div>
      <div class="read-card-block">
        <div class="read-card-label">Implied Robusta Share ({read['target_date'].strftime('%b %Y')})</div>
        <div class="read-card-value">{read['projected_share']:.1f}%</div>
        <div class="read-card-sub">Historical range: {lo:.1f}%&ndash;{hi:.1f}% &middot; based on {read['lag']}-month lag, n={read['n']} months</div>
      </div>
    </div>
    """)


def seasonal_table_html(df_wide, year_cols, title, unit="", kind="flow",
                         ytd_series=None, ytd_label="YTD",
                         full_series=None, full_label="Full Year"):
    """Crop-year x month heatmap table (crop years as rows, Jul->Jun as columns) —
    matches the original Excel seasonal layout. df_wide is Period-rows/CropYear-columns
    (as produced by flow_wide/proportion_wide); this transposes it for display.

    Two separate right-hand summaries, so old (complete) crop years and the
    current (partial) one are never conflated:
    - ytd_series / ytd_label: value restricted to the periods actually reported
      so far for the current crop year (e.g. "Jul", or "Jul-Aug"), for every
      crop year — an apples-to-apples comparison. Pass a Series indexed by
      crop year (e.g. a properly volume-weighted proportion) or leave None to
      default to a plain sum (kind="flow") / mean (kind="ratio") over just
      the first reported period.
    - full_series / full_label: the row's full-season value, same defaulting
      rules but over every period in that crop year."""
    periods = df_wide["Period"].tolist()
    mat = df_wide.set_index("Period")[year_cols].T  # rows=crop year, columns=Period

    if ytd_series is None:
        last_row = mat.iloc[-1]
        n_ytd = 0
        for p in periods:
            if pd.isna(last_row.get(p)):
                break
            n_ytd += 1
        ytd_periods = periods[:n_ytd] or periods[:1]
        ytd_series = (mat[ytd_periods].sum(axis=1, skipna=True) if kind == "flow"
                      else mat[ytd_periods].mean(axis=1, skipna=True))
    if full_series is None:
        full_series = mat.sum(axis=1, skipna=True) if kind == "flow" else mat.mean(axis=1, skipna=True)
    # A crop year missing any month isn't a real "full year" total yet (this is
    # always true of the current, still-in-progress crop year) — blank it out
    # rather than showing a misleadingly low total and a misleadingly bad YoY.
    incomplete = mat.isna().any(axis=1)
    full_series = full_series.where(~incomplete)

    ytd_yoy = ytd_series.pct_change(fill_method=None) * 100
    full_yoy = full_series.pct_change(fill_method=None) * 100

    vmin = mat.min(numeric_only=True).min()
    vmax = mat.max(numeric_only=True).max()
    span = (vmax - vmin) or 1

    heading = f"{title} (in {unit})" if unit else title
    header_cells = "".join(f"<th>{p}</th>" for p in periods)

    rows_html = []
    for yr in mat.index:
        cells = [f'<td class="period-col">{yr}</td>']
        for p in periods:
            v = mat.loc[yr, p]
            if pd.isna(v):
                cells.append('<td></td>')
                continue
            t = (v - vmin) / span
            bg, txt = _green_shade(t)
            cells.append(f'<td style="background:{bg};color:{txt};">{_fmt(v, unit)}</td>')
        ytd_v = ytd_series.get(yr)
        ytd_cell = f'<td style="font-weight:600;">{_fmt(ytd_v, unit)}</td>' if pd.notna(ytd_v) else '<td></td>'
        ytd_yoy_cell = f'<td class="bar-cell">{_bar_cell(ytd_yoy.get(yr))}</td>'
        full_v = full_series.get(yr)
        full_cell = f'<td style="font-weight:600;">{_fmt(full_v, unit)}</td>' if pd.notna(full_v) else '<td></td>'
        full_yoy_cell = f'<td class="bar-cell">{_bar_cell(full_yoy.get(yr))}</td>'
        rows_html.append(
            "<tr>" + "".join(cells) + ytd_cell + ytd_yoy_cell + full_cell + full_yoy_cell + "</tr>"
        )

    if len(mat) >= 2:
        yoy_row = (mat.iloc[-1] - mat.iloc[-2]) / mat.iloc[-2] * 100
    else:
        yoy_row = pd.Series(index=periods, dtype=float)
    lta_avg_row = mat.mean(axis=0, skipna=True)

    yoy_row_cells = "".join(
        f'<td>{yoy_row[p]:+.0f}%</td>' if pd.notna(yoy_row.get(p)) else '<td></td>' for p in periods
    )
    lta_row_cells = "".join(
        f'<td>{_fmt(lta_avg_row[p], unit)}</td>' if pd.notna(lta_avg_row.get(p)) else '<td></td>' for p in periods
    )

    html = f"""
    {_STYLE}
    <div class="unica-table-wrap">
    <table class="unica-table">
      <caption>{heading}</caption>
      <thead><tr><th class="period-col">Crop Year</th>{header_cells}
        <th>{ytd_label}</th><th>YoY</th><th>{full_label}</th><th>YoY</th></tr></thead>
      <tbody>
        {''.join(rows_html)}
        <tr class="total-row"><td class="period-col">YoY</td>{yoy_row_cells}<td></td><td></td><td></td><td></td></tr>
        <tr class="total-row"><td class="period-col">LTA Avg</td>{lta_row_cells}<td></td><td></td><td></td><td></td></tr>
      </tbody>
    </table>
    </div>
    """
    return _flatten(html)
