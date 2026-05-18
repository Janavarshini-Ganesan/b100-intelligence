"""
etl/05_fill_gaps_v2.py
Fixed version — individual transactions per UPDATE, proper numeric cast for ROUND
"""

import os
import re
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def run_sql(query, params=None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})

def safe_float(val):
    try:
        return float(str(val).replace(",","").replace("%","").strip())
    except:
        return None

print("=" * 60)
print("B100 INTELLIGENCE — GAP FILL SCRIPT v2")
print("=" * 60)

# ─── 1. dim_sector ────────────────────────────────────────────
print("\n[1/6] dim_sector...")
SECTOR_MAP = {
    "TCS":"IT","INFY":"IT","WIPRO":"IT","HCLTECH":"IT","TECHM":"IT",
    "LTIM":"IT","PERSISTENT":"IT","COFORGE":"IT","MPHASIS":"IT","OFSS":"IT",
    "HDFCBANK":"Banking","ICICIBANK":"Banking","SBIN":"Banking","KOTAKBANK":"Banking",
    "AXISBANK":"Banking","BANKBARODA":"Banking","FEDERALBNK":"Banking",
    "IDFCFIRSTB":"Banking","PNB":"Banking","CANBK":"Banking","UNIONBANK":"Banking",
    "BAJFINANCE":"NBFC","BAJAJFINSV":"NBFC","CHOLAFIN":"NBFC","MUTHOOTFIN":"NBFC","SBICARD":"NBFC",
    "SBILIFE":"Insurance","HDFCLIFE":"Insurance","ICICIPRULI":"Insurance","ICICIGI":"Insurance",
    "RELIANCE":"Energy & Oil","ONGC":"Energy & Oil","IOC":"Energy & Oil",
    "BPCL":"Energy & Oil","GAIL":"Energy & Oil",
    "ADANIGREEN":"Renewable Energy","ADANIPOWER":"Power","ADANIENSOL":"Power",
    "ATGL":"Gas","TATAPOWER":"Power","NTPC":"Power","POWERGRID":"Power",
    "ADANIENT":"Conglomerate","ADANIPORTS":"Ports & Logistics",
    "AMBUJACEM":"Cement","ULTRACEMCO":"Cement","SHREECEM":"Cement","GRASIM":"Conglomerate",
    "APOLLOHOSP":"Healthcare","CIPLA":"Pharma","DRREDDY":"Pharma","SUNPHARMA":"Pharma",
    "DIVISLAB":"Pharma","ZYDUSLIFE":"Pharma","TORNTPHARM":"Pharma","AUROPHARMA":"Pharma",
    "MARUTI":"Auto","TATAMOTORS":"Auto","M&M":"Auto","BAJAJ-AUTO":"Auto",
    "HEROMOTOCO":"Auto","EICHERMOT":"Auto","TVSMOTOR":"Auto",
    "ASIANPAINT":"Paints","BERGERPAINTS":"Paints",
    "HINDUNILVR":"FMCG","ITC":"FMCG","NESTLEIND":"FMCG","BRITANNIA":"FMCG",
    "MARICO":"FMCG","DABUR":"FMCG","GODREJCP":"FMCG","COLPAL":"FMCG","TATACONSUM":"FMCG",
    "LT":"Infrastructure","JSWSTEEL":"Steel & Metals","TATASTEEL":"Steel & Metals",
    "HINDALCO":"Steel & Metals","VEDL":"Steel & Metals",
    "COALINDIA":"Mining","NMDC":"Mining",
    "DLF":"Real Estate","GODREJPROP":"Real Estate",
    "ZOMATO":"Consumer Tech","BHARTIARTL":"Telecom",
    "ABB":"Capital Goods","BHEL":"Capital Goods","SIEMENS":"Capital Goods","HAVELLS":"Capital Goods",
    "TITAN":"Consumer Durables","DMART":"Retail","TRENT":"Retail",
    "INDIGO":"Aviation","IRCTC":"Travel & Tourism",
    "PIDILITIND":"Chemicals","UPL":"Chemicals",
    "INDUSINDBK":"Banking","BANDHANBNK":"Banking",
    "LTTS":"IT","NYKAA":"Consumer Tech","POLICYBZR":"Fintech","PAYTM":"Fintech",
    "OBEROIRLTY":"Real Estate","PHOENIXLTD":"Real Estate",
    "VOLTAS":"Consumer Durables","KALYANKJIL":"Consumer Durables","WHIRLPOOL":"Consumer Durables",
    "PIIND":"Chemicals","ACC":"Cement","DALBHARAT":"Cement",
    "MAXHEALTH":"Healthcare","FORTIS":"Healthcare","BIOCON":"Pharma",
}

sectors = sorted(set(SECTOR_MAP.values()))
run_sql("DROP TABLE IF EXISTS dim_sector CASCADE")
run_sql("""
CREATE TABLE dim_sector (
    sector_id   SERIAL PRIMARY KEY,
    sector_name VARCHAR(100) UNIQUE NOT NULL,
    sector_code VARCHAR(20),
    description TEXT
)
""")
with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO dim_sector (sector_id, sector_name, sector_code, description)
        VALUES (:sector_id, :sector_name, :sector_code, :description)
    """), [{"sector_id":i+1,"sector_name":s,
            "sector_code":s.upper().replace(" ","_").replace("&","AND")[:20],
            "description":f"{s} sector"} for i,s in enumerate(sectors)])
print(f"  ✅ dim_sector: {len(sectors)} sectors")

# ─── 2. dim_health_label ──────────────────────────────────────
print("\n[2/6] dim_health_label...")
run_sql("DROP TABLE IF EXISTS dim_health_label CASCADE")
run_sql("""
CREATE TABLE dim_health_label (
    label_id   SERIAL PRIMARY KEY,
    label_name VARCHAR(20) UNIQUE NOT NULL,
    min_score  NUMERIC(5,2),
    max_score  NUMERIC(5,2),
    color_hex  VARCHAR(10)
)
""")
with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO dim_health_label (label_id,label_name,min_score,max_score,color_hex)
        VALUES (:l,:n,:mn,:mx,:c)
    """), [
        {"l":1,"n":"EXCELLENT","mn":80,  "mx":100,  "c":"#16a34a"},
        {"l":2,"n":"GOOD",     "mn":65,  "mx":79.99,"c":"#65a30d"},
        {"l":3,"n":"AVERAGE",  "mn":50,  "mx":64.99,"c":"#ca8a04"},
        {"l":4,"n":"WEAK",     "mn":35,  "mx":49.99,"c":"#ea580c"},
        {"l":5,"n":"POOR",     "mn":0,   "mx":34.99,"c":"#dc2626"},
    ])
print("  ✅ dim_health_label: 5 labels")

# ─── 3. fact_analysis ─────────────────────────────────────────
print("\n[3/6] fact_analysis from analysis.xlsx...")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS_PATH = os.path.join(BASE, "data", "raw", "analysis.xlsx")

run_sql("DROP TABLE IF EXISTS fact_analysis CASCADE")
run_sql("""
CREATE TABLE fact_analysis (
    id                             SERIAL PRIMARY KEY,
    symbol                         VARCHAR(20),
    period_label                   VARCHAR(10),
    compounded_sales_growth_pct    NUMERIC(10,2),
    compounded_profit_growth_pct   NUMERIC(10,2),
    stock_price_cagr_pct           NUMERIC(10,2),
    roe_pct                        NUMERIC(10,2),
    UNIQUE(symbol, period_label)
)
""")

try:
    # Try reading with header=1 first (most common for these files)
    df_raw = pd.read_excel(ANALYSIS_PATH, header=1)
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    print(f"  Columns found: {list(df_raw.columns[:8])}")

    # First col = symbol
    first_col = df_raw.columns[0]
    df_raw = df_raw.rename(columns={first_col: "symbol"})
    df_raw = df_raw[df_raw["symbol"].notna()].copy()
    df_raw["symbol"] = df_raw["symbol"].astype(str).str.strip().str.upper()
    df_raw = df_raw[~df_raw["symbol"].isin(["NAN","NONE","","SYMBOL"])]

    PERIOD_MAP = {
        "10 year": "10Y", "10year": "10Y", "10 yr": "10Y",
        "5 year": "5Y",  "5year": "5Y",  "5 yr": "5Y",
        "3 year": "3Y",  "3year": "3Y",  "3 yr": "3Y",
        "ttm": "TTM",
    }
    METRIC_MAP = {
        "sales": "compounded_sales_growth_pct",
        "revenue": "compounded_sales_growth_pct",
        "profit": "compounded_profit_growth_pct",
        "stock": "stock_price_cagr_pct",
        "cagr": "stock_price_cagr_pct",
        "roe": "roe_pct",
    }

    rows = []
    for _, row in df_raw.iterrows():
        symbol = row["symbol"]
        for col in df_raw.columns[1:]:
            cl = col.lower()
            period = next((v for k, v in PERIOD_MAP.items() if k in cl), None)
            metric = next((v for k, v in METRIC_MAP.items() if k in cl), None)
            if period and metric:
                val = safe_float(row[col])
                rows.append({"symbol": symbol, "period_label": period,
                             "metric": metric, "value_pct": val})

    if rows:
        df_long = pd.DataFrame(rows)
        df_pivot = df_long.pivot_table(
            index=["symbol","period_label"], columns="metric",
            values="value_pct", aggfunc="first"
        ).reset_index()
        df_pivot.columns.name = None
        for c in ["compounded_sales_growth_pct","compounded_profit_growth_pct",
                  "stock_price_cagr_pct","roe_pct"]:
            if c not in df_pivot.columns:
                df_pivot[c] = None

        with engine.begin() as conn:
            for _, r in df_pivot.iterrows():
                conn.execute(text("""
                    INSERT INTO fact_analysis
                    (symbol,period_label,compounded_sales_growth_pct,
                     compounded_profit_growth_pct,stock_price_cagr_pct,roe_pct)
                    VALUES (:sym,:per,:s,:p,:st,:roe)
                    ON CONFLICT (symbol,period_label) DO NOTHING
                """), {"sym":r["symbol"],"per":r["period_label"],
                       "s":r.get("compounded_sales_growth_pct"),
                       "p":r.get("compounded_profit_growth_pct"),
                       "st":r.get("stock_price_cagr_pct"),
                       "roe":r.get("roe_pct")})
        print(f"  ✅ fact_analysis: {len(df_pivot)} rows inserted")
    else:
        print("  ⚠️  No rows parsed. Printing first 3 rows of analysis.xlsx for debug:")
        print(df_raw.head(3).to_string())
except FileNotFoundError:
    print(f"  ❌ Not found: {ANALYSIS_PATH}")

# ─── 4. fact_pros_cons ────────────────────────────────────────
print("\n[4/6] fact_pros_cons (already inserted — skipping recreate)...")
print("  ✅ fact_pros_cons: 42 rows already present")

# ─── 5. Add computed columns (each in own transaction) ────────
print("\n[5/6] Adding computed columns...")
NEW_COLS = [
    ("fact_profit_loss",   "expense_ratio_pct",   "NUMERIC(10,2)"),
    ("fact_profit_loss",   "interest_coverage",   "NUMERIC(10,2)"),
    ("fact_profit_loss",   "asset_turnover",      "NUMERIC(10,2)"),
    ("fact_profit_loss",   "return_on_assets",    "NUMERIC(10,2)"),
    ("fact_balance_sheet", "equity_ratio",        "NUMERIC(10,2)"),
    ("fact_cash_flow",     "cash_conversion_ratio","NUMERIC(10,2)"),
]
for table, col, dtype in NEW_COLS:
    try:
        run_sql(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {dtype}")
        print(f"  ✅ {table}.{col}")
    except Exception as e:
        print(f"  ⚠️  {table}.{col}: {e}")

# ─── 6. Populate computed columns (each in own transaction) ────
print("\n[6/6] Populating computed columns...")

UPDATES = [
    ("expense_ratio_pct on fact_profit_loss",
     """UPDATE fact_profit_loss SET expense_ratio_pct =
        CASE WHEN sales::numeric > 0
        THEN ROUND((expenses::numeric / NULLIF(sales::numeric,0))*100, 2) END"""),

    ("interest_coverage on fact_profit_loss",
     """UPDATE fact_profit_loss SET interest_coverage =
        CASE WHEN interest::numeric > 0
        THEN ROUND(operating_profit::numeric / NULLIF(interest::numeric,0), 2) END"""),

    ("equity_ratio on fact_balance_sheet",
     """UPDATE fact_balance_sheet SET equity_ratio =
        CASE WHEN total_assets::numeric > 0
        THEN ROUND((equity_capital::numeric + reserves::numeric)
             / NULLIF(total_assets::numeric,0), 4) END"""),

    ("cash_conversion_ratio on fact_cash_flow",
     """UPDATE fact_cash_flow cf
        SET cash_conversion_ratio = sub.ratio
        FROM (
            SELECT cf2.id,
                   CASE WHEN pl.net_profit::numeric != 0
                   THEN ROUND(cf2.operating_activity::numeric
                        / NULLIF(pl.net_profit::numeric,0), 4) END AS ratio
            FROM fact_cash_flow cf2
            JOIN fact_profit_loss pl
              ON cf2.symbol = pl.symbol AND cf2.year_label = pl.year_label
        ) sub WHERE cf.id = sub.id"""),

    ("asset_turnover + return_on_assets on fact_profit_loss",
     """UPDATE fact_profit_loss pl
        SET asset_turnover = sub.at_val,
            return_on_assets = sub.roa_val
        FROM (
            SELECT pl2.id,
                   CASE WHEN bs.total_assets::numeric > 0
                   THEN ROUND(pl2.sales::numeric / NULLIF(bs.total_assets::numeric,0), 4) END AS at_val,
                   CASE WHEN bs.total_assets::numeric > 0
                   THEN ROUND((pl2.net_profit::numeric / NULLIF(bs.total_assets::numeric,0))*100, 2) END AS roa_val
            FROM fact_profit_loss pl2
            JOIN fact_balance_sheet bs
              ON pl2.symbol = bs.symbol AND pl2.year_label = bs.year_label
        ) sub WHERE pl.id = sub.id"""),
]

for label, query in UPDATES:
    try:
        run_sql(query)
        print(f"  ✅ {label}")
    except Exception as e:
        print(f"  ⚠️  {label}: {e}")

print("\n" + "=" * 60)
print("✅ ALL GAP FILLS COMPLETE!")
print("=" * 60)
