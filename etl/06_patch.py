"""
etl/06_patch.py — Targeted patch for remaining gaps
"""
import os, re
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def run_sql(q, p=None):
    with engine.begin() as conn:
        conn.execute(text(q), p or {})

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("=" * 55)
print("B100 INTELLIGENCE — PATCH SCRIPT")
print("=" * 55)

# ─── PATCH 1: fact_analysis ───────────────────────────────────
print("\n[1/3] fact_analysis from analysis.xlsx...")

ANALYSIS_PATH = os.path.join(BASE, "data", "raw", "analysis.xlsx")

def parse_period(text):
    """Extract period label from value string like '10 Years: 21%'"""
    t = str(text).lower()
    if "10" in t:   return "10Y"
    if "5" in t:    return "5Y"
    if "3" in t:    return "3Y"
    if "ttm" in t or "last year" in t or "1 year" in t: return "TTM"
    return None

def parse_value(text):
    """Extract numeric value from '10 Years: 21%' → 21.0"""
    try:
        nums = re.findall(r"-?\d+\.?\d*", str(text))
        # Skip the year number (10, 5, 3, 1) and take the last number
        candidates = [float(n) for n in nums if abs(float(n)) < 1000]
        # Remove period numbers (10, 5, 3, 1) from candidates
        candidates = [v for v in candidates if v not in (10.0, 5.0, 3.0, 1.0)]
        return candidates[-1] if candidates else None
    except:
        return None

df = pd.read_excel(ANALYSIS_PATH, header=1)
df.columns = [str(c).strip() for c in df.columns]
# symbol is in company_id column
df = df.rename(columns={"company_id": "symbol"})
df = df[df["symbol"].notna()].copy()
df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
df = df[~df["symbol"].isin(["NAN","NONE","","COMPANY_ID","ID"])]

print(f"  Rows in file: {len(df)}")
print(f"  Symbols: {df['symbol'].nunique()} unique")

# Each row has the period embedded in the value string
# Extract period from compounded_sales_growth column
rows = []
for _, row in df.iterrows():
    symbol = row["symbol"]
    # Parse period from any non-null value column
    period = None
    for col in ["compounded_sales_growth", "compounded_profit_growth",
                "stock_price_cagr", "roe"]:
        if col in df.columns and pd.notna(row.get(col)):
            p = parse_period(row[col])
            if p:
                period = p
                break
    if not period:
        continue

    rows.append({
        "symbol":      symbol,
        "period_label": period,
        "compounded_sales_growth_pct":   parse_value(row.get("compounded_sales_growth")),
        "compounded_profit_growth_pct":  parse_value(row.get("compounded_profit_growth")),
        "stock_price_cagr_pct":          parse_value(row.get("stock_price_cagr")),
        "roe_pct":                       parse_value(row.get("roe")),
    })

print(f"  Parsed rows: {len(rows)}")
if rows:
    run_sql("TRUNCATE fact_analysis")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO fact_analysis
            (symbol, period_label, compounded_sales_growth_pct,
             compounded_profit_growth_pct, stock_price_cagr_pct, roe_pct)
            VALUES (:symbol,:period_label,:compounded_sales_growth_pct,
                    :compounded_profit_growth_pct,:stock_price_cagr_pct,:roe_pct)
            ON CONFLICT (symbol, period_label) DO UPDATE
            SET compounded_sales_growth_pct  = EXCLUDED.compounded_sales_growth_pct,
                compounded_profit_growth_pct = EXCLUDED.compounded_profit_growth_pct,
                stock_price_cagr_pct         = EXCLUDED.stock_price_cagr_pct,
                roe_pct                      = EXCLUDED.roe_pct
        """), rows)
    print(f"  ✅ fact_analysis: {len(rows)} rows inserted")

    # Preview
    df_preview = pd.DataFrame(rows).head(6)
    print("\n  Preview:")
    print(df_preview[["symbol","period_label",
                       "compounded_sales_growth_pct","roe_pct"]].to_string(index=False))
else:
    print("  ❌ Still no rows — check file manually")

# ─── PATCH 2: cash_conversion_ratio ──────────────────────────
print("\n[2/3] cash_conversion_ratio on fact_cash_flow...")
try:
    run_sql("""
        UPDATE fact_cash_flow cf
        SET cash_conversion_ratio =
            CASE WHEN pl.net_profit::numeric != 0
            THEN ROUND(cf.operating_activity::numeric
                 / NULLIF(pl.net_profit::numeric, 0), 4)
            END
        FROM fact_profit_loss pl
        WHERE cf.symbol    = pl.symbol
          AND cf.year_label = pl.year_label
    """)
    print("  ✅ cash_conversion_ratio populated")
except Exception as e:
    print(f"  ⚠️  {e}")

# ─── PATCH 3: asset_turnover + return_on_assets ───────────────
print("\n[3/3] asset_turnover + return_on_assets on fact_profit_loss...")
try:
    run_sql("""
        UPDATE fact_profit_loss pl
        SET asset_turnover   = CASE WHEN bs.total_assets::numeric > 0
            THEN ROUND(pl.sales::numeric / NULLIF(bs.total_assets::numeric, 0), 4) END,
            return_on_assets = CASE WHEN bs.total_assets::numeric > 0
            THEN ROUND((pl.net_profit::numeric / NULLIF(bs.total_assets::numeric, 0))*100, 2) END
        FROM fact_balance_sheet bs
        WHERE pl.symbol    = bs.symbol
          AND pl.year_label = bs.year_label
    """)
    print("  ✅ asset_turnover + return_on_assets populated")
except Exception as e:
    print(f"  ⚠️  {e}")

print("\n" + "=" * 55)
print("✅ PATCH COMPLETE!")
print("=" * 55)
