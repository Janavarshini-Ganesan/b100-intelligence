
import pandas as pd
import os
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent   # project root
RAW_DIR    = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── Excel file config ─────────────────────────────────────────────────────────
# Format: (excel_filename, sheet_name, skiprows, rename_map)
# skiprows=1 → skips the "Bluestock Fintech..." branding title row
# rename_map → renames messy column names to clean snake_case

FILES = {
    "companies": {
        "file":     "companies.xlsx",
        "sheet":    "Companies",
        "skiprows": 1,
        "rename": {
            "Unnamed: 0":   "symbol",
            "company_logo": "company_logo",
            "company_name": "company_name",
            "chart_link":   "chart_link",
            "about_company":"about_company",
            "website":      "website",
            "nse_profile":  "nse_url",
            "bse_profile":  "bse_url",
            "face_value":   "face_value",
            "book_value":   "book_value",
            "roce_percentage": "roce_pct",
            "roe_percentage":  "roe_pct",
        }
    },
    "analysis": {
        "file":     "analysis.xlsx",
        "sheet":    "Analysis",
        "skiprows": 1,
        "rename": {
            "id":                       "id",
            "company_id":               "symbol",
            "compounded_sales_growth":  "compounded_sales_growth_raw",
            "compounded_profit_growth": "compounded_profit_growth_raw",
            "stock_price_cagr":         "stock_price_cagr_raw",
            "roe":                      "roe_raw",
        }
    },
    "balancesheet": {
        "file":     "balancesheet.xlsx",
        "sheet":    "Balance Sheet",
        "skiprows": 1,
        "rename": {
            "id":               "id",
            "company_id":       "symbol",
            "year":             "year_raw",
            "equity_capital":   "equity_capital",
            "reserves":         "reserves",
            "borrowings":       "borrowings",
            "other_liabilities":"other_liabilities",
            "total_liabilities":"total_liabilities",
            "fixed_assets":     "fixed_assets",
            "cwip":             "cwip",
            "investments":      "investments",
            "other_asset":      "other_assets",
            "total_assets":     "total_assets",
        }
    },
    "profitandloss": {
        "file":     "profitandloss.xlsx",
        "sheet":    "Profit & Loss",
        "skiprows": 1,
        "rename": {
            "id":                 "id",
            "company_id":         "symbol",
            "year":               "year_raw",
            "sales":              "sales",
            "expenses":           "expenses",
            "operating_profit":   "operating_profit",
            "opm_percentage":     "opm_pct",
            "other_income":       "other_income",
            "interest":           "interest",
            "depreciation":       "depreciation",
            "profit_before_tax":  "profit_before_tax",
            "tax_percentage":     "tax_pct",
            "net_profit":         "net_profit",
            "eps":                "eps",
            "dividend_payout":    "dividend_payout_pct",
        }
    },
    "cashflow": {
        "file":     "cashflow.xlsx",
        "sheet":    "Cash Flow",
        "skiprows": 1,
        "rename": {
            "id":                  "id",
            "company_id":          "symbol",
            "year":                "year_raw",
            "operating_activity":  "operating_activity",
            "investing_activity":  "investing_activity",
            "financing_activity":  "financing_activity",
            "net_cash_flow":       "net_cash_flow",
        }
    },
    "prosandcons": {
        "file":     "prosandcons.xlsx",
        "sheet":    "Pros & Cons",
        "skiprows": 1,
        "rename": {
            "id":         "id",
            "company_id": "symbol",
            "pros":       "pros",
            "cons":       "cons",
        }
    },
    "documents": {
        "file":     "documents.xlsx",
        "sheet":    "Documents",
        "skiprows": 1,
        "rename": {}   # will auto-lowercase all columns
    },
}

# ── Helper functions ──────────────────────────────────────────────────────────

def clean_column_names(df):
    """Lowercase all column names, replace spaces/special chars with underscore."""
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[\s\-\.]+", "_", regex=True)
        .str.replace(r"[^a-z0-9_]", "", regex=True)
    )
    return df


def extract_table(name, config):
    """Read one Excel file, clean columns, return DataFrame."""
    excel_path = RAW_DIR / config["file"]

    if not excel_path.exists():
        print(f"  ❌  File not found: {excel_path}")
        print(f"      Make sure {config['file']} is inside data\\raw\\")
        return None

    try:
        df = pd.read_excel(
            excel_path,
            sheet_name=config["sheet"],
            skiprows=config["skiprows"],
            dtype=str,          # read everything as string first (safe)
        )
    except Exception as e:
        print(f"  ❌  Could not read {config['file']} → {e}")
        return None

    # Drop completely empty rows and columns
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)

    # Auto-clean column names first
    df = clean_column_names(df)

    # Apply specific rename map (after auto-clean)
    rename = {k.lower(): v for k, v in config["rename"].items()}
    df.rename(columns=rename, inplace=True)

    # Replace string "NULL", "Null", "null", "nan", "None", "NaN" → actual NaN
    df.replace(
        to_replace=["NULL", "Null", "null", "NaN", "nan", "None", "none", ""],
        value=pd.NA,
        inplace=True
    )

    # Strip whitespace from all string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    return df


def print_summary(name, df):
    """Print a clean summary table for one extracted table."""
    print(f"\n  ✅  {name.upper()}")
    print(f"      Rows    : {len(df):,}")
    print(f"      Columns : {len(df.columns)}")
    print(f"      Names   : {list(df.columns)}")
    nulls = df.isnull().sum()
    high_null = nulls[nulls > 0]
    if not high_null.empty:
        top = high_null.nlargest(3)
        print(f"      Nulls   : {dict(top)} (showing top 3 columns)")


# ── Main extraction loop ──────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  B100 Intelligence — ETL Script 01: Extract")
    print("  Reading 7 Excel files → saving to data/raw/*.csv")
    print("=" * 60)

    results = {}
    success_count = 0

    for name, config in FILES.items():
        print(f"\n📂 Extracting: {config['file']}  (sheet: {config['sheet']})")

        df = extract_table(name, config)

        if df is None:
            results[name] = False
            continue

        # Save to CSV
        out_path = RAW_DIR / f"{name}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8")

        print_summary(name, df)
        print(f"      Saved → {out_path}")

        results[name] = True
        success_count += 1

    # Final report
    print("\n" + "=" * 60)
    print(f"  DONE — {success_count}/7 tables extracted successfully")
    print("=" * 60)

    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\n  ⚠️  Failed tables: {failed}")
        print("  Check that Excel files are in data\\raw\\ folder.")
        sys.exit(1)
    else:
        print("\n  ✅ All 7 CSVs saved to data/raw/")
        


if __name__ == "__main__":
    main()
