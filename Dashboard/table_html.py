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
.unica-table th {{ background: #0f766e; color: white; padding: 3px 8px;
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


def seasonal_table_html(df_wide, year_cols, title, unit="", kind="flow",
                         summary_series=None, summary_label="YTD"):
    """Crop-year x month heatmap table (crop years as rows, Jul->Jun as columns) —
    matches the original Excel seasonal layout. df_wide is Period-rows/CropYear-columns
    (as produced by flow_wide/proportion_wide); this transposes it for display.

    summary_series, if given, is a Series indexed by crop year supplying the right-hand
    summary column (e.g. a properly volume-weighted proportion); otherwise it defaults
    to a row sum (kind="flow") or row mean (kind="ratio")."""
    periods = df_wide["Period"].tolist()
    mat = df_wide.set_index("Period")[year_cols].T  # rows=crop year, columns=Period

    if summary_series is None:
        summary_series = mat.sum(axis=1, skipna=True) if kind == "flow" else mat.mean(axis=1, skipna=True)
    summary_yoy = summary_series.pct_change(fill_method=None) * 100

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
        s = summary_series.get(yr)
        s_cell = f'<td style="font-weight:600;">{_fmt(s, unit)}</td>' if pd.notna(s) else '<td></td>'
        yoy_cell = f'<td class="bar-cell">{_bar_cell(summary_yoy.get(yr))}</td>'
        rows_html.append("<tr>" + "".join(cells) + s_cell + yoy_cell + "</tr>")

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
      <thead><tr><th class="period-col">Crop Year</th>{header_cells}<th>{summary_label}</th><th>YoY</th></tr></thead>
      <tbody>
        {''.join(rows_html)}
        <tr class="total-row"><td class="period-col">YoY</td>{yoy_row_cells}<td></td><td></td></tr>
        <tr class="total-row"><td class="period-col">LTA Avg</td>{lta_row_cells}<td></td><td></td></tr>
      </tbody>
    </table>
    </div>
    """
    return _flatten(html)
