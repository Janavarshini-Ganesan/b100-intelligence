#!/usr/bin/env python3
"""
etl/03_load_to_warehouse.py
B100 Intelligence — Step 3: Load clean CSVs → Neon PostgreSQL

HOW TO RUN:
    (venv) PS> python etl\03_load_to_warehouse.py

This script:
  1. Fixes missing company symbols (adds stub records to dim_company)
  2. Creates all 9 tables in Neon PostgreSQL
  3. Loads dim tables first, then fact tables (correct order)
  4. Runs row-count verification after load
  5. Safe to re-run — uses DROP + RECREATE (idempotent)
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ── Load environment variables ─────────────────────────────────────────────────
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env file!")
    print("   Open .env and make sure DATABASE_URL is set correctly.")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent
CLEAN_DIR = BASE_DIR / "data" / "clean"

# ── Sector fallback for any symbol not in companies.xlsx ──────────────────────
EXTRA_SECTORS = {
    "WIPRO":      "IT",
    "ULTRACEMCO": "Cement",
    "VEDL":       "Metals",
    "ZOMATO":     "Consumer",
    "VBL":        "FMCG",
    "ZYDUSLIFE":  "Pharma",
    "AGTL":       "Energy",
    "TATASTEEL":  "Metals",
    "JSWSTEEL":   "Metals",
    "HINDALCO":   "Metals",
    "BHARTIARTL": "Telecom",
    "ADANIPOWER": "Energy",
    "TATAPOWER":  "Energy",
    "POWERGRID":  "Energy",
    "NTPC":       "Energy",
    "IOC":        "Energy",
    "ONGC":       "Energy",
    "BPCL":       "Energy",
    "GAIL":       "Energy",
    "COALINDIA":  "Energy",
    "SBIN":       "Banking",
    "ICICIBANK":  "Banking",
    "INDUSINDBK": "Banking",
    "KOTAKBANK":  "Banking",
    "CANBK":      "Banking",
    "PNB":        "Banking",
    "BANKBARODA": "Banking",
    "UNIONBANK":  "Banking",
    "HDFCLIFE":   "Insurance",
    "ICICIGI":    "Insurance",
    "M&M":        "Auto",
    "MARUTI":     "Auto",
    "TATAMOTORS": "Auto",
    "HEROMOTOCO": "Auto",
    "TVSMOTOR":   "Auto",
    "EICHERMOT":  "Auto",
    "SUNPHARMA":  "Pharma",
    "DRREDDY":    "Pharma",
    "CIPLA":      "Pharma",
    "DIVISLAB":   "Pharma",
    "TORNTPHARM": "Pharma",
    "HINDUNILVR": "FMCG",
    "ITC":        "FMCG",
    "NESTLEIND":  "FMCG",
    "BRITANNIA":  "FMCG",
    "DABUR":      "FMCG",
    "MARICO":     "FMCG",
    "GODREJCP":   "FMCG",
    "COLPAL":     "FMCG",
    "UNITDSPR":   "FMCG",
    "ASIANPAINT": "Paints",
    "DLF":        "Infrastructure",
    "LT":         "Infrastructure",
    "ADANIPORTS": "Infrastructure",
    "ADANIENT":   "Infrastructure",
    "TITAN":      "Consumer",
    "TRENT":      "Retail",
    "DMART":      "Retail",
    "APOLLOHOSP": "Healthcare",
    "AMBUJACEM":  "Cement",
    "GRASIM":     "Cement",
    "ABB":        "Capital Goods",
    "SIEMENS":    "Capital Goods",
    "ADANIGREEN": "Energy",
    "ADANIENSOL": "Energy",
    "ATGL":       "Energy",
    "BAJFINANCE": "NBFC",
    "BAJAJFINSV": "NBFC",
    "CHOLAFIN":   "NBFC",
    "MUTHOOTFIN": "NBFC",
    "SHRIRAMFIN": "NBFC",
    "HCLTECH":    "IT",
    "TECHM":      "IT",
    "LTIM":       "IT",
    "PERSISTENT": "IT",
    "TCS":        "IT",
    "INFY":       "IT",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: read all clean CSVs
# ─────────────────────────────────────────────────────────────────────────────

def read_csv(name):
    path = CLEAN_DIR / f"{name}.csv"
    if not path.exists():
        print(f"  ❌ Missing: {path} — did Script 02 run successfully?")
        sys.exit(1)
    return pd.read_csv(path)


def fix_missing_symbols(dim_company, fact_dfs):
    """
    If any symbol in fact tables is missing from dim_company,
    create a stub row so foreign keys work in PostgreSQL.
    Returns updated dim_company DataFrame.
    """
    known = set(dim_company["symbol"].dropna())
    all_fact_symbols = set()
    for df in fact_dfs:
        if "symbol" in df.columns:
            all_fact_symbols.update(df["symbol"].dropna().unique())

    missing = all_fact_symbols - known
    if not missing:
        print("  ✅  All symbols are consistent — no stubs needed")
        return dim_company

    print(f"  ⚠️  Adding {len(missing)} stub records to dim_company: {sorted(missing)}")
    stubs = []
    for sym in sorted(missing):
        stubs.append({
            "symbol":       sym,
            "company_name": sym,          # use symbol as name placeholder
            "sector":       EXTRA_SECTORS.get(sym, "Other"),
            "company_logo": None,
            "website":      None,
            "nse_url":      None,
            "bse_url":      None,
            "face_value":   None,
            "book_value":   None,
            "roce_pct":     None,
            "roe_pct":      None,
            "about_company":None,
        })
    stub_df = pd.DataFrame(stubs)
    result = pd.concat([dim_company, stub_df], ignore_index=True)

    # Save the fixed dim_company back to CSV
    result.to_csv(CLEAN_DIR / "dim_company.csv", index=False)
    print(f"  ✅  dim_company now has {len(result)} total records")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# LOAD TABLES
# ─────────────────────────────────────────────────────────────────────────────

def load_table(df, table_name, engine, chunksize=500):
    """Drop existing table and load fresh data. Returns row count."""
    # Replace NaN with None so PostgreSQL stores NULL (not NaN string)
    df = df.replace({np.nan: None})

    before_count = 0
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            before_count = result.scalar()
    except Exception:
        pass  # Table doesn't exist yet — that's fine

    df.to_sql(
        table_name,
        engine,
        if_exists="replace",  # drop & recreate — safe & simple
        index=False,
        chunksize=chunksize,
        method="multi",       # faster batch insert
    )

    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        after_count = result.scalar()

    return before_count, after_count


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  B100 Intelligence — ETL Script 03: Load to Warehouse")
    print("  Loading clean CSVs → Neon PostgreSQL (bluestock_dw)")
    print("=" * 60)

    # ── Connect to Neon ────────────────────────────────────────────────────────
    print("\nConnecting to Neon PostgreSQL...")
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version()")).scalar()
        print(f"  ✅  Connected! {ver[:45]}")
    except Exception as e:
        print(f"  ❌  Connection failed: {e}")
        sys.exit(1)

    # ── Read all clean CSVs ───────────────────────────────────────────────────
    print("\nReading clean CSVs from data/clean/...")
    dim_company     = read_csv("dim_company")
    dim_sector      = read_csv("dim_sector")
    dim_year        = read_csv("dim_year")
    dim_health      = read_csv("dim_health_label")
    fact_pl         = read_csv("fact_profit_loss")
    fact_bs         = read_csv("fact_balance_sheet")
    fact_cf         = read_csv("fact_cash_flow")
    fact_analysis   = read_csv("fact_analysis")
    fact_pros_cons  = read_csv("fact_pros_cons")
    print("  ✅  All CSVs loaded into memory")

    # ── Fix missing symbols BEFORE loading ────────────────────────────────────
    print("\nChecking symbol consistency...")
    dim_company = fix_missing_symbols(
        dim_company,
        [fact_pl, fact_bs, fact_cf, fact_analysis, fact_pros_cons]
    )

    # Also fix dim_sector to include any new sectors from stubs
    all_sectors = sorted(dim_company["sector"].dropna().unique())
    existing_sectors = set(dim_sector["sector_name"])
    new_sectors = [s for s in all_sectors if s not in existing_sectors]
    if new_sectors:
        next_id = dim_sector["sector_id"].max() + 1
        extras = pd.DataFrame({
            "sector_id":   range(next_id, next_id + len(new_sectors)),
            "sector_name": new_sectors,
            "sector_code": [s[:4].upper() for s in new_sectors],
        })
        dim_sector = pd.concat([dim_sector, extras], ignore_index=True)
        dim_sector.to_csv(CLEAN_DIR / "dim_sector.csv", index=False)

    # ── Load tables in correct order (dim first, then fact) ───────────────────
    # Order matters because fact tables reference dim tables.
    LOAD_ORDER = [
        ("dim_sector",        dim_sector),
        ("dim_health_label",  dim_health),
        ("dim_company",       dim_company),
        ("dim_year",          dim_year),
        ("fact_profit_loss",  fact_pl),
        ("fact_balance_sheet",fact_bs),
        ("fact_cash_flow",    fact_cf),
        ("fact_analysis",     fact_analysis),
        ("fact_pros_cons",    fact_pros_cons),
    ]

    print("\nLoading tables into Neon PostgreSQL...")
    print(f"  {'Table':<25} {'Before':>7} → {'After':>7}  Status")
    print(f"  {'-'*25} {'-'*7}   {'-'*7}  {'-'*10}")

    all_ok = True
    for table_name, df in LOAD_ORDER:
        try:
            before, after = load_table(df, table_name, engine)
            status = "✅ OK" if after == len(df) else "⚠️ MISMATCH"
            if after != len(df):
                all_ok = False
            print(f"  {table_name:<25} {before:>7,} → {after:>7,}  {status}")
        except Exception as e:
            print(f"  {table_name:<25} FAILED: {e}")
            all_ok = False

    # ── Post-load verification ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  POST-LOAD VERIFICATION")
    print("=" * 60)

    checks = [
        ("Total companies",    "SELECT COUNT(*) FROM dim_company"),
        ("Total sectors",      "SELECT COUNT(*) FROM dim_sector"),
        ("P&L rows",           "SELECT COUNT(*) FROM fact_profit_loss"),
        ("Balance Sheet rows", "SELECT COUNT(*) FROM fact_balance_sheet"),
        ("Cash Flow rows",     "SELECT COUNT(*) FROM fact_cash_flow"),
        ("Year periods",       "SELECT COUNT(*) FROM dim_year"),
        ("Companies with TTM data",
         "SELECT COUNT(DISTINCT symbol) FROM fact_profit_loss WHERE year_label = \'TTM\'"),
        ("Avg OPM (all companies)",
         "SELECT ROUND(AVG(opm_pct::numeric), 2) FROM fact_profit_loss WHERE opm_pct IS NOT NULL"),
    ]

    with engine.connect() as conn:
        for label, query in checks:
            try:
                val = conn.execute(text(query)).scalar()
                print(f"  {label:<30} : {val}")
            except Exception as e:
                print(f"  {label:<30} : ERROR — {e}")

    # ── Final summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if all_ok:
        print("  ✅ ALL 9 TABLES LOADED SUCCESSFULLY!")
        print("  Your Neon PostgreSQL warehouse is ready.")
        print()
        
    else:
        print("  ⚠️  Some tables had issues. Check errors above.")
    print("=" * 60)


if __name__ == "__main__":
    main()
