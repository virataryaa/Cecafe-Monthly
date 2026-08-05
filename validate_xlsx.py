"""Sanity-checks Database/Cecafe Monthly.xlsx before it gets pushed.

Run standalone: python validate_xlsx.py
Exit code 0 = safe to push. Exit code 1 = problems found, do not push.
"""
import sys
from pathlib import Path

import pandas as pd

XLSX_PATH = Path(__file__).resolve().parent / "Database" / "Cecafe Monthly.xlsx"
SHEET_NAME = "Database"

REQUIRED_COLS = ["Year", "Month", "Type", "Destination", "Bags (K)"]
KNOWN_TYPES = {"Arabica", "Robusta"}
KNOWN_DESTINATIONS = {
    "Belgium", "China", "Colombia", "Germany", "Italy", "Japan", "Mexico",
    "Netherlands", "Spain", "Total", "UK", "USA", "Vietnam",
}
YEAR_MIN, YEAR_MAX = 2000, 2035

# Small rounding slack before a Total-too-small violation is flagged.
TOTAL_TOLERANCE_ABS = 1.0    # K bags


def main():
    errors = []
    warnings = []

    if not XLSX_PATH.exists():
        print(f"FAIL: {XLSX_PATH} does not exist.")
        return 1

    try:
        df = pd.read_excel(XLSX_PATH, sheet_name=SHEET_NAME)
    except Exception as e:
        print(f"FAIL: could not parse '{SHEET_NAME}' sheet - {e}")
        return 1

    for col in REQUIRED_COLS:
        if col not in df.columns:
            errors.append(f"Missing required column '{col}'.")
    if errors:
        _report(errors, warnings)
        return 1

    # Year / Month sanity
    bad_year = df[~df["Year"].apply(lambda v: pd.notna(v) and float(v).is_integer()
                                     and YEAR_MIN <= int(v) <= YEAR_MAX)]
    for _, r in bad_year.iterrows():
        errors.append(f"Row with bad Year value: {r['Year']!r} "
                       f"(Type={r.get('Type')}, Destination={r.get('Destination')}).")

    bad_month = df[~df["Month"].apply(lambda v: pd.notna(v) and float(v).is_integer()
                                       and 1 <= int(v) <= 12)]
    for _, r in bad_month.iterrows():
        errors.append(f"Row with bad Month value: {r['Month']!r} "
                       f"(Year={r.get('Year')}, Type={r.get('Type')}, Destination={r.get('Destination')}).")

    # Type / Destination vocabulary
    bad_types = set(df["Type"].dropna().unique()) - KNOWN_TYPES
    if bad_types:
        errors.append(f"Unexpected Type value(s): {sorted(bad_types)} — typo? Expected only {sorted(KNOWN_TYPES)}.")

    unknown_dests = set(df["Destination"].dropna().unique()) - KNOWN_DESTINATIONS
    if unknown_dests:
        warnings.append(f"Destination(s) not in the known list (new destination? fine if intentional, "
                         f"typo otherwise): {sorted(unknown_dests)}")

    # Duplicate (Year, Month, Type, Destination) rows
    dupes = df[df.duplicated(subset=["Year", "Month", "Type", "Destination"], keep=False)]
    if not dupes.empty:
        for _, row in dupes.iterrows():
            errors.append(f"Duplicate row: Year={row['Year']}, Month={row['Month']}, "
                           f"Type='{row['Type']}', Destination='{row['Destination']}'.")

    # Numeric parseability of Bags (K)
    non_blank = df["Bags (K)"].dropna()
    non_numeric = non_blank[pd.to_numeric(non_blank, errors="coerce").isna()]
    if not non_numeric.empty:
        bad_rows = df.loc[non_numeric.index, ["Year", "Month", "Type", "Destination"]]
        for _, r in bad_rows.iterrows():
            errors.append(f"Non-numeric Bags (K) value for Year={r['Year']}, Month={r['Month']}, "
                           f"Type='{r['Type']}', Destination='{r['Destination']}'.")

    if errors:
        # Reconciliation and blank-period checks assume clean types/rows —
        # skip them until the errors above are fixed.
        _report(errors, warnings)
        return 1

    # Reconciliation: the named destinations are a curated subset of buyers
    # (not every country Brazil exports to), so Total is expected to exceed
    # their sum — but it should never be LESS than their sum, since that's a
    # subset relationship. If it is, a value was very likely fat-fingered.
    for (year, month, type_), group in df.groupby(["Year", "Month", "Type"]):
        total_rows = group[group["Destination"] == "Total"]
        if total_rows.empty:
            continue
        total_val = total_rows["Bags (K)"].iloc[0]
        parts_sum = group.loc[group["Destination"] != "Total", "Bags (K)"].sum(skipna=True)
        if pd.isna(total_val):
            continue
        if parts_sum > total_val + TOTAL_TOLERANCE_ABS:
            errors.append(
                f"Total too small: Year={year}, Month={month}, Type='{type_}' — "
                f"named destinations sum to {parts_sum:,.1f} but Total row = {total_val:,.1f} "
                f"(Total should be >= the sum of its named destinations)."
            )

    # Flag a Type whose most recent (Year, Month) has zero data at all
    # (possible accidental clear when adding a new month's row).
    for type_, group in df.groupby("Type"):
        latest = group[["Year", "Month"]].drop_duplicates().sort_values(["Year", "Month"]).iloc[-1]
        latest_rows = group[(group["Year"] == latest["Year"]) & (group["Month"] == latest["Month"])]
        if latest_rows["Bags (K)"].notna().sum() == 0:
            warnings.append(f"'{type_}' has zero values for its most recent period "
                             f"({int(latest['Year'])}-{int(latest['Month']):02d}) — "
                             f"fine if that month genuinely hasn't been reported yet, worth a second look otherwise.")

    return _report(errors, warnings)


def _report(errors, warnings):
    if warnings:
        print("Warnings (won't block the push):")
        for w in warnings:
            print(f"  - {w}")
        print()
    if errors:
        print("FAIL - fix these before pushing:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASS - Cecafe Monthly.xlsx looks good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
