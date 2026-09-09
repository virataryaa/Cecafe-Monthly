"""Refresh the Comexstat green-coffee export parquet from the MDIC bulk files.

Comexstat publishes one CSV per year (EXP_<year>.csv) holding every export
line for that year: NCM x state x destination x port x transport mode. We
download the years asked for, keep only the green-coffee NCM codes, join the
country and NCM name lookups, and merge the result into the existing parquet.

Whole years are replaced rather than only the new month, because Comexstat
revises previously published months as late customs declarations land. Taking
the year wholesale keeps us consistent with the source instead of freezing
whatever a month looked like on the day we first pulled it.

Usage:
    python ingest_comexstat.py            # current year only (the routine case)
    python ingest_comexstat.py 2024 2025  # named years
    python ingest_comexstat.py --all      # full rebuild from 1997
"""

import io
import ssl
import sys
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

BASE_URL = "https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/EXP_{year}.csv"
OUT_DIR = Path(__file__).resolve().parent.parent / "Database" / "Comexstat"
PARQUET_PATH = OUT_DIR / "comexstat_coffee_exports.parquet"
CSV_PATH = OUT_DIR / "comexstat_coffee_exports.csv"

# Green coffee only: 0901.11.10 (in grain), 0901.11.90 (other), 0901.12.00
# (decaffeinated). Roasted (0901.2x) and soluble (2101.11) are deliberately
# excluded -- the dashboard treats every row in this file as green coffee and
# sums it as such, so widening the filter here would silently inflate it.
COFFEE_NCM = [9011110, 9011190, 9011200]

FIRST_YEAR = 1997
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def fetch_year(year):
    """Download one year's export file and return just the coffee rows."""
    url = BASE_URL.format(year=year)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600, context=_CTX) as resp:
        raw = resp.read()
    print(f"  downloaded {len(raw) / 1e6:6.1f} MB", end="", flush=True)

    keep = []
    reader = pd.read_csv(io.BytesIO(raw), sep=";", encoding="latin1",
                         chunksize=500_000, low_memory=False)
    for chunk in reader:
        keep.append(chunk[chunk["CO_NCM"].isin(COFFEE_NCM)])
    df = pd.concat(keep, ignore_index=True)
    print(f"  ->{len(df):7,} coffee rows")
    return df


def add_labels(df):
    """Attach the country and NCM description columns the dashboard reads."""
    pais = pd.read_csv(OUT_DIR / "ref_pais.csv", sep=";", encoding="latin1")
    ncm = pd.read_csv(OUT_DIR / "ref_ncm.csv", sep=";", encoding="latin1")
    df = df.merge(pais[["CO_PAIS", "NO_PAIS", "NO_PAIS_ING"]], on="CO_PAIS", how="left")
    df = df.merge(ncm[["CO_NCM", "NO_NCM_ING"]], on="CO_NCM", how="left")
    return df


def main(argv):
    if "--all" in argv:
        years = list(range(FIRST_YEAR, date.today().year + 1))
    elif argv:
        years = [int(a) for a in argv]
    else:
        years = [date.today().year]

    print(f"Comexstat refresh -> years {years[0]}"
          f"{'-' + str(years[-1]) if len(years) > 1 else ''}")

    fresh = []
    for year in years:
        print(f"{year}:", end=" ", flush=True)
        try:
            fresh.append(fetch_year(year))
        except Exception as exc:
            # A year that fails should not discard the years that worked; the
            # merge below simply leaves that year's existing rows in place.
            print(f"  FAILED ({type(exc).__name__}: {exc}) - keeping existing rows")
    if not fresh:
        print("Nothing downloaded, parquet left untouched.")
        return 1

    new = add_labels(pd.concat(fresh, ignore_index=True))

    if PARQUET_PATH.exists():
        old = pd.read_parquet(PARQUET_PATH)
        refreshed = sorted(new["CO_ANO"].unique())
        combined = pd.concat([old[~old["CO_ANO"].isin(refreshed)], new], ignore_index=True)
    else:
        combined = new

    combined = (combined.sort_values(["CO_ANO", "CO_MES", "CO_NCM"])
                        .reset_index(drop=True))
    combined.to_parquet(PARQUET_PATH, index=False)
    combined.to_csv(CSV_PATH, sep=";", index=False, encoding="latin1")

    last = combined[combined["CO_ANO"] == combined["CO_ANO"].max()]
    print(f"\nWrote {len(combined):,} rows covering "
          f"{combined['CO_ANO'].min()}-{combined['CO_ANO'].max()}; "
          f"latest month {combined['CO_ANO'].max()}-{last['CO_MES'].max():02d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
