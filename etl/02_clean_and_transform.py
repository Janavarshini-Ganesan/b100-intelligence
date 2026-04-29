#!/usr/bin/env python3
"""
etl/02_clean_and_transform.py
B100 Intelligence — Step 2: Clean, standardize, compute derived columns

HOW TO RUN:
    (venv) PS> python etl\02_clean_and_transform.py

INPUT  : data/raw/*.csv          (from Script 01)
OUTPUT : data/clean/*.csv        (dim_ and fact_ tables ready for warehouse)

Creates these clean files:
    dim_company.csv       dim_year.csv
    dim_sector.csv        dim_health_label.csv
    fact_profit_loss.csv  fact_balance_sheet.csv
    fact_cash_flow.csv    fact_analysis.csv
    fact_pros_cons.csv
"""

import pandas as pd
import numpy as np
import re
import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent
RAW_DIR   = BASE_DIR / "data" / "raw"
CLEAN_DIR = BASE_DIR / "data" / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# ── Sector mapping for all 92 Nifty 100 companies ─────────────────────────────
SECTOR_MAP = {
    # IT Services
    "TCS":        "IT",     "INFY":       "IT",     "WIPRO":      "IT",
    "HCLTECH":    "IT",     "TECHM":      "IT",     "LTIM":       "IT",
    "PERSISTENT": "IT",     "MPHASIS":    "IT",

    # Banking — Private
    "HDFCBANK":   "Banking","ICICIBANK":  "Banking","KOTAKBANK":  "Banking",
    "AXISBANK":   "Banking","INDUSINDBK": "Banking","FEDERALBNK": "Banking",
    "BANDHANBNK": "Banking",

    # Banking — PSU
    "SBIN":       "Banking","BANKBARODA": "Banking","PNB":        "Banking",
    "CANBK":      "Banking","UNIONBANK":  "Banking",

    # NBFC / Finance
    "BAJFINANCE": "NBFC",   "BAJAJFINSV": "NBFC",   "CHOLAFIN":   "NBFC",
    "MUTHOOTFIN": "NBFC",   "SHRIRAMFIN": "NBFC",

    # Insurance
    "HDFCLIFE":   "Insurance","SBILIFE":  "Insurance","ICICIGI":   "Insurance",

    # Energy — Oil & Gas
    "ONGC":       "Energy", "BPCL":       "Energy", "IOC":        "Energy",
    "GAIL":       "Energy", "COALINDIA":  "Energy",

    # Energy — Power & Renewables
    "ADANIGREEN": "Energy", "ADANIPOWER": "Energy", "ADANIENSOL": "Energy",
    "ATGL":       "Energy", "TATAPOWER":  "Energy", "NTPC":       "Energy",
    "POWERGRID":  "Energy",

    # Infrastructure / Ports / Conglomerate
    "ADANIPORTS": "Infrastructure","ADANIENT":  "Infrastructure",
    "LT":         "Infrastructure","DLF":       "Infrastructure",

    # Metals & Mining
    "JSWSTEEL":   "Metals", "TATASTEEL":  "Metals", "HINDALCO":   "Metals",
    "VEDL":       "Metals",

    # Cement
    "AMBUJACEM":  "Cement", "ULTRACEMCO": "Cement", "GRASIM":     "Cement",
    "ACC":        "Cement",

    # Healthcare / Hospitals
    "APOLLOHOSP": "Healthcare",

    # Pharma
    "SUNPHARMA":  "Pharma", "DRREDDY":    "Pharma", "CIPLA":      "Pharma",
    "DIVISLAB":   "Pharma", "TORNTPHARM": "Pharma",

    # FMCG / Consumer Staples
    "HINDUNILVR": "FMCG",   "ITC":        "FMCG",   "NESTLEIND":  "FMCG",
    "BRITANNIA":  "FMCG",   "DABUR":      "FMCG",   "MARICO":     "FMCG",
    "GODREJCP":   "FMCG",   "COLPAL":     "FMCG",   "UNITDSPR":   "FMCG",

    # Consumer Discretionary / Retail
    "TITAN":      "Consumer","TRENT":     "Retail",  "DMART":      "Retail",
    "VMART":      "Retail",

    # Auto & Auto Components
    "MARUTI":     "Auto",   "TATAMOTORS": "Auto",   "M&M":        "Auto",
    "BAJAJ-AUTO": "Auto",   "HEROMOTOCO": "Auto",   "EICHERMOT":  "Auto",
    "TVSMOTOR":   "Auto",

    # Paints
    "ASIANPAINT": "Paints",

    # Capital Goods / Industrials
    "ABB":        "Capital Goods","SIEMENS": "Capital Goods",

    # Telecom
    "BHARTIARTL": "Telecom",

    # Others / Holding Companies
    "ADANIGREEN": "Energy",
}

# ── Month order for sort_order calculation ─────────────────────────────────────
MONTH_ORDER = {
    "Jan": 1,  "Feb": 2,  "Mar": 3,  "Apr": 4,
    "May": 5,  "Jun": 6,  "Jul": 7,  "Aug": 8,
    "Sep": 9,  "Oct": 10, "Nov": 11, "Dec": 12,
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def standardize_year(raw):
    """
    Convert any year format to clean 'Mon YYYY' or 'TTM'.

    Examples:
        'Mar 2024'  → 'Mar 2024'   (already clean)
        'Mar-24'    → 'Mar 2024'
        'Mar-2024'  → 'Mar 2024'
        'Sep 2024'  → 'Sep 2024'
        'Dec 2012'  → 'Dec 2012'
        'TTM'       → 'TTM'
    """
    if pd.isna(raw):
        return None
    s = str(raw).strip()
    if s.upper() == "TTM":
        return "TTM"
    # Already in "Mon YYYY" format
    if re.match(r"^[A-Za-z]{3}\s+\d{4}$", s):
        return s
    # "Mon-YY" format  e.g. Mar-24
    m = re.match(r"^([A-Za-z]{3})-(\d{2})$", s)
    if m:
        mon, yr = m.group(1), m.group(2)
        year = 2000 + int(yr)
        return f"{mon.capitalize()} {year}"
    # "Mon-YYYY" format  e.g. Mar-2024
    m = re.match(r"^([A-Za-z]{3})-(\d{4})$", s)
    if m:
        mon, yr = m.group(1), m.group(2)
        return f"{mon.capitalize()} {yr}"
    return s   # return as-is if unknown


def get_fiscal_year(year_label):
    """'Mar 2024' → 2024,  'Dec 2012' → 2012,  'TTM' → 9999"""
    if year_label == "TTM":
        return 9999
    m = re.search(r"\d{4}", str(year_label))
    return int(m.group()) if m else None


def get_sort_order(year_label):
    """
    Returns integer for correct chronological sorting.
    'Mar 2013' → 201303, 'Dec 2024' → 202412, 'TTM' → 999999
    """
    if year_label == "TTM":
        return 999999
    parts = str(year_label).strip().split()
    if len(parts) == 2:
        mon = MONTH_ORDER.get(parts[0], 3)
        yr  = int(parts[1])
        return yr * 100 + mon
    return 999998


def to_float(val):
    """Safely convert a value to float; return NaN if not possible."""
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return np.nan


def parse_analysis_value(raw_text):
    """
    Parse strings like:
        '10 Years: 21%'  → ('10Y', 21.0)
        '5 Years: 22%'   → ('5Y', 22.0)
        '3 Years: 30%'   → ('3Y', 30.0)
        'TTM:      47%'  → ('TTM', 47.0)
        '1 Year:   13%'  → ('TTM', 13.0)
        'Last Year: 17%' → ('TTM', 17.0)
    Returns (period_label, value_float)
    """
    if pd.isna(raw_text):
        return (None, np.nan)
    s = str(raw_text).strip()

    PERIOD_MAP = {
        "10 Years": "10Y", "10Y": "10Y",
        "5 Years":  "5Y",  "5Y":  "5Y",
        "3 Years":  "3Y",  "3Y":  "3Y",
        "TTM":      "TTM",
        "1 Year":   "TTM",
        "Last Year":"TTM",
    }

    period_label = None
    for key, label in PERIOD_MAP.items():
        if key.lower() in s.lower():
            period_label = label
            break

    # Extract the numeric part (handles negatives and decimals)
    m = re.search(r"(-?\d+\.?\d*)", s.replace(",", ""))
    value = float(m.group(1)) if m else np.nan

    return (period_label, value)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE PROCESSORS
# ─────────────────────────────────────────────────────────────────────────────

def process_companies():
    print("\n[1/9] Processing companies → dim_company")
    df = pd.read_csv(RAW_DIR / "companies.csv", dtype=str)

    # The first column 'id' IS the company symbol (ABB, TCS, etc.)
    df.rename(columns={"id": "symbol"}, inplace=True)

    # Clean company_name: strip \r\n and extra whitespace
    df["company_name"] = df["company_name"].str.replace(r"[\r\n]+", " ", regex=True).str.strip()

    # Add sector from mapping
    df["sector"] = df["symbol"].map(SECTOR_MAP).fillna("Other")

    # Convert numeric columns
    df["face_value"] = df["face_value"].apply(to_float)
    df["book_value"]  = df["book_value"].apply(to_float)
    df["roce_pct"]    = df["roce_pct"].apply(to_float)
    df["roe_pct"]     = df["roe_pct"].apply(to_float)

    # Select and order final columns for dim_company
    dim_company = df[[
        "symbol", "company_name", "sector",
        "company_logo", "website", "nse_url", "bse_url",
        "face_value", "book_value", "roce_pct", "roe_pct",
        "about_company",
    ]].copy()

    dim_company.to_csv(CLEAN_DIR / "dim_company.csv", index=False)
    print(f"    ✅ dim_company.csv  → {len(dim_company)} companies")
    print(f"    Sectors: {sorted(dim_company['sector'].unique())}")
    return dim_company


def build_dim_sector(dim_company):
    print("\n[2/9] Building dim_sector")
    sectors = sorted(dim_company["sector"].unique())
    dim_sector = pd.DataFrame({
        "sector_id":   range(1, len(sectors) + 1),
        "sector_name": sectors,
        "sector_code": [s[:4].upper() for s in sectors],
    })
    dim_sector.to_csv(CLEAN_DIR / "dim_sector.csv", index=False)
    print(f"    ✅ dim_sector.csv  → {len(dim_sector)} sectors")
    return dim_sector


def build_dim_health_label():
    print("\n[3/9] Building dim_health_label")
    rows = [
        (1, "EXCELLENT", 85, 100, "#22c55e"),
        (2, "GOOD",      70,  84, "#86efac"),
        (3, "AVERAGE",   50,  69, "#facc15"),
        (4, "WEAK",      35,  49, "#fb923c"),
        (5, "POOR",       0,  34, "#ef4444"),
    ]
    dim_health = pd.DataFrame(rows, columns=[
        "label_id","label_name","min_score","max_score","color_hex"
    ])
    dim_health.to_csv(CLEAN_DIR / "dim_health_label.csv", index=False)
    print(f"    ✅ dim_health_label.csv  → {len(dim_health)} labels")
    return dim_health


def process_year_dimension(tables_with_years):
    """Collect all unique year labels, build dim_year."""
    print("\n[4/9] Building dim_year from all year columns")
    all_years = set()
    for df in tables_with_years:
        all_years.update(df["year_label"].dropna().unique())

    records = []
    for y in sorted(all_years):
        fy  = get_fiscal_year(y)
        so  = get_sort_order(y)
        is_ttm      = y == "TTM"
        is_half_year= any(mon in y for mon in ["Sep ", "Jun ", "Dec "]) and not is_ttm
        records.append({
            "year_label":   y,
            "fiscal_year":  fy,
            "is_ttm":       is_ttm,
            "is_half_year": is_half_year,
            "sort_order":   so,
        })

    dim_year = pd.DataFrame(records).sort_values("sort_order").reset_index(drop=True)
    dim_year.insert(0, "year_id", range(1, len(dim_year) + 1))
    dim_year.to_csv(CLEAN_DIR / "dim_year.csv", index=False)
    print(f"    ✅ dim_year.csv  → {len(dim_year)} unique year periods")
    return dim_year


def process_profitloss():
    print("\n[5/9] Processing profitandloss → fact_profit_loss")
    df = pd.read_csv(RAW_DIR / "profitandloss.csv", dtype=str)

    # Standardize year
    df["year_label"] = df["year_raw"].apply(standardize_year)

    # Convert all numeric cols
    num_cols = [
        "sales","expenses","operating_profit","opm_pct","other_income",
        "interest","depreciation","profit_before_tax","tax_pct",
        "net_profit","eps","dividend_payout_pct"
    ]
    for col in num_cols:
        df[col] = df[col].apply(to_float)

    # ── Computed columns ──────────────────────────────────────────────────────
    df["net_profit_margin_pct"] = (df["net_profit"] / df["sales"]) * 100
    df["expense_ratio_pct"]     = (df["expenses"]   / df["sales"]) * 100
    # Avoid divide-by-zero: replace 0 interest with NaN before dividing
    interest_safe = df["interest"].replace(0, np.nan)
    df["interest_coverage"] = df["operating_profit"] / interest_safe

    fact_pl = df[[
        "symbol","year_label",
        "sales","expenses","operating_profit","opm_pct","other_income",
        "interest","depreciation","profit_before_tax","tax_pct",
        "net_profit","eps","dividend_payout_pct",
        "net_profit_margin_pct","expense_ratio_pct","interest_coverage",
    ]].copy()

    fact_pl.to_csv(CLEAN_DIR / "fact_profit_loss.csv", index=False)
    print(f"    ✅ fact_profit_loss.csv  → {len(fact_pl):,} rows")
    print(f"    Computed: net_profit_margin_pct, expense_ratio_pct, interest_coverage")
    return fact_pl


def process_balancesheet():
    print("\n[6/9] Processing balancesheet → fact_balance_sheet")
    df = pd.read_csv(RAW_DIR / "balancesheet.csv", dtype=str)

    df["year_label"] = df["year_raw"].apply(standardize_year)

    num_cols = [
        "equity_capital","reserves","borrowings","other_liabilities",
        "total_liabilities","fixed_assets","cwip","investments",
        "other_assets","total_assets"
    ]
    for col in num_cols:
        df[col] = df[col].apply(to_float)

    # ── Computed columns ──────────────────────────────────────────────────────
    equity_total = df["equity_capital"] + df["reserves"]
    df["debt_to_equity"]  = df["borrowings"] / equity_total.replace(0, np.nan)
    df["equity_ratio"]    = equity_total / df["total_assets"].replace(0, np.nan)

    fact_bs = df[[
        "symbol","year_label",
        "equity_capital","reserves","borrowings","other_liabilities",
        "total_liabilities","fixed_assets","cwip","investments",
        "other_assets","total_assets",
        "debt_to_equity","equity_ratio",
    ]].copy()

    fact_bs.to_csv(CLEAN_DIR / "fact_balance_sheet.csv", index=False)
    print(f"    ✅ fact_balance_sheet.csv  → {len(fact_bs):,} rows")
    print(f"    Computed: debt_to_equity, equity_ratio")
    return fact_bs


def process_cashflow():
    print("\n[7/9] Processing cashflow → fact_cash_flow")
    df = pd.read_csv(RAW_DIR / "cashflow.csv", dtype=str)

    df["year_label"] = df["year_raw"].apply(standardize_year)

    num_cols = [
        "operating_activity","investing_activity",
        "financing_activity","net_cash_flow"
    ]
    for col in num_cols:
        df[col] = df[col].apply(to_float)

    # ── Computed columns ──────────────────────────────────────────────────────
    df["free_cash_flow"] = df["operating_activity"] + df["investing_activity"]

    fact_cf = df[[
        "symbol","year_label",
        "operating_activity","investing_activity",
        "financing_activity","net_cash_flow","free_cash_flow",
    ]].copy()

    fact_cf.to_csv(CLEAN_DIR / "fact_cash_flow.csv", index=False)
    print(f"    ✅ fact_cash_flow.csv  → {len(fact_cf):,} rows")
    print(f"    Computed: free_cash_flow")
    return fact_cf


def process_analysis():
    print("\n[8/9] Processing analysis → fact_analysis")
    df = pd.read_csv(RAW_DIR / "analysis.csv", dtype=str)

    records = []
    for _, row in df.iterrows():
        symbol = row["symbol"]

        # Parse each of the 4 CAGR columns
        p_sales,   v_sales   = parse_analysis_value(row.get("compounded_sales_growth_raw"))
        p_profit,  v_profit  = parse_analysis_value(row.get("compounded_profit_growth_raw"))
        p_stock,   v_stock   = parse_analysis_value(row.get("stock_price_cagr_raw"))
        p_roe,     v_roe     = parse_analysis_value(row.get("roe_raw"))

        # All 4 columns should have the same period label per row
        period = p_sales or p_profit or p_stock or p_roe

        if period:
            records.append({
                "symbol":                     symbol,
                "period_label":               period,
                "compounded_sales_growth_pct": v_sales,
                "compounded_profit_growth_pct":v_profit,
                "stock_price_cagr_pct":        v_stock,
                "roe_pct":                     v_roe,
            })

    fact_analysis = pd.DataFrame(records)
    fact_analysis.to_csv(CLEAN_DIR / "fact_analysis.csv", index=False)
    print(f"    ✅ fact_analysis.csv  → {len(fact_analysis)} rows")
    print(f"    Periods found: {sorted(fact_analysis['period_label'].unique())}")
    return fact_analysis


def process_prosandcons():
    print("\n[9/9] Processing prosandcons → fact_pros_cons")
    df = pd.read_csv(RAW_DIR / "prosandcons.csv", dtype=str)

    records = []
    for _, row in df.iterrows():
        symbol = row["symbol"]

        if pd.notna(row.get("pros")) and str(row["pros"]).strip():
            records.append({
                "symbol":   symbol,
                "is_pro":   True,
                "text":     str(row["pros"]).strip(),
                "source":   "MANUAL",
            })
        if pd.notna(row.get("cons")) and str(row["cons"]).strip():
            records.append({
                "symbol":   symbol,
                "is_pro":   False,
                "text":     str(row["cons"]).strip(),
                "source":   "MANUAL",
            })

    fact_pc = pd.DataFrame(records)
    fact_pc.to_csv(CLEAN_DIR / "fact_pros_cons.csv", index=False)
    print(f"    ✅ fact_pros_cons.csv  → {len(fact_pc)} rows")
    return fact_pc


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  B100 Intelligence — ETL Script 02: Clean & Transform")
    print("  Building dimension + fact tables for star schema")
    print("=" * 60)

    # Process each table
    dim_company  = process_companies()
    dim_sector   = build_dim_sector(dim_company)
    dim_health   = build_dim_health_label()
    fact_pl      = process_profitloss()
    fact_bs      = process_balancesheet()
    fact_cf      = process_cashflow()
    fact_analysis= process_analysis()
    fact_pc      = process_prosandcons()

    # Build dim_year from all tables that have year columns
    dim_year = process_year_dimension([fact_pl, fact_bs, fact_cf])

    # ── Quick data quality checks ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  DATA QUALITY CHECKS")
    print("=" * 60)

    # Check 1: All symbols in fact tables exist in dim_company
    known_symbols = set(dim_company["symbol"])
    for tname, tdf in [
        ("fact_profit_loss",  fact_pl),
        ("fact_balance_sheet",fact_bs),
        ("fact_cash_flow",    fact_cf),
    ]:
        unknown = set(tdf["symbol"]) - known_symbols
        if unknown:
            print(f"  ⚠️  {tname}: {len(unknown)} symbols not in dim_company: {list(unknown)[:5]}")
        else:
            print(f"  ✅  {tname}: all symbols match dim_company")

    # Check 2: Show year range
    non_ttm = fact_pl[fact_pl["year_label"] != "TTM"]["year_label"]
    years   = non_ttm.apply(get_fiscal_year).dropna()
    print(f"  ✅  Year range in data: {int(years.min())} → {int(years.max())}")

    # Check 3: Row count summary
    print("\n  CLEAN FILE SUMMARY:")
    clean_files = {
        "dim_company":      dim_company,
        "dim_sector":       dim_sector,
        "dim_year":         dim_year,
        "dim_health_label": dim_health,
        "fact_profit_loss": fact_pl,
        "fact_balance_sheet":fact_bs,
        "fact_cash_flow":   fact_cf,
        "fact_analysis":    fact_analysis,
        "fact_pros_cons":   fact_pc,
    }
    for name, df in clean_files.items():
        print(f"    {name:<25} {len(df):>6,} rows   → data/clean/{name}.csv")

    print("\n  ✅ All clean files saved to data/clean/")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
