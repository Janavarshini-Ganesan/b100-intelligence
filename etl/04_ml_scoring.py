#!/usr/bin/env python3
"""
etl/04_ml_scoring.py
B100 Intelligence — ML Health Scoring Engine

HOW TO RUN:
    (venv) PS> python etl\04_ml_scoring.py

WHAT IT DOES:
  1. Reads all financial data from Neon PostgreSQL
  2. Scores each company on 5 metrics (0-20 points each = 100 total)
  3. Labels: EXCELLENT(80-100) GOOD(60-79) AVERAGE(40-59) WEAK(20-39) POOR(0-19)
  4. Saves fact_ml_scores table back to Neon
  5. Links to dim_health_label in Power BI
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env"); sys.exit(1)

BASE_DIR  = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────
# SCORING RULES (5 metrics × 20 points max = 100 total)
# ─────────────────────────────────────────────────────────────

def score_revenue_growth(cagr_pct):
    """
    3-year revenue CAGR score (20 pts max)
    >20%  → 20  | 15-20% → 16 | 10-15% → 12
    5-10% → 8   | 0-5%   → 4  | <0%    → 0
    """
    if   pd.isna(cagr_pct): return 5   # neutral if missing
    elif cagr_pct >= 20:    return 20
    elif cagr_pct >= 15:    return 16
    elif cagr_pct >= 10:    return 12
    elif cagr_pct >= 5:     return 8
    elif cagr_pct >= 0:     return 4
    else:                   return 0

def score_profit_margin(avg_opm_pct):
    """
    Average Operating Profit Margin score (20 pts max)
    >30%  → 20  | 20-30% → 16 | 15-20% → 12
    10-15%→ 8   | 5-10%  → 4  | <5%    → 0
    """
    if   pd.isna(avg_opm_pct):   return 5
    elif avg_opm_pct >= 30:      return 20
    elif avg_opm_pct >= 20:      return 16
    elif avg_opm_pct >= 15:      return 12
    elif avg_opm_pct >= 10:      return 8
    elif avg_opm_pct >= 5:       return 4
    else:                        return 0

def score_debt_equity(de_ratio):
    """
    Debt-to-Equity ratio score (20 pts max) — lower is better
    <0.3  → 20  | 0.3-0.5 → 16 | 0.5-1.0 → 12
    1.0-2.0→ 8  | 2.0-4.0 →  4 | >4.0    →  0
    """
    if   pd.isna(de_ratio):  return 10  # neutral
    elif de_ratio < 0.3:     return 20
    elif de_ratio < 0.5:     return 16
    elif de_ratio < 1.0:     return 12
    elif de_ratio < 2.0:     return 8
    elif de_ratio < 4.0:     return 4
    else:                    return 0

def score_roe(roe_pct):
    """
    Return on Equity score (20 pts max)
    >25%  → 20  | 20-25% → 16 | 15-20% → 12
    10-15%→ 8   | 5-10%  → 4  | <5%    →  0
    """
    if   pd.isna(roe_pct): return 5
    elif roe_pct >= 25:    return 20
    elif roe_pct >= 20:    return 16
    elif roe_pct >= 15:    return 12
    elif roe_pct >= 10:    return 8
    elif roe_pct >= 5:     return 4
    else:                  return 0

def score_cash_flow(fcf_positive_years, total_years):
    """
    Free Cash Flow consistency score (20 pts max)
    % of years with positive FCF:
    >80% → 20 | 60-80% → 16 | 40-60% → 12
    20-40%→ 8 | 0-20%  →  4 | no data →  5
    """
    if total_years == 0: return 5
    pct = (fcf_positive_years / total_years) * 100
    if   pct >= 80: return 20
    elif pct >= 60: return 16
    elif pct >= 40: return 12
    elif pct >= 20: return 8
    else:           return 4

def get_health_label(score):
    """Map numeric score to health label."""
    if   score >= 80: return "EXCELLENT"
    elif score >= 60: return "GOOD"
    elif score >= 40: return "AVERAGE"
    elif score >= 20: return "WEAK"
    else:             return "POOR"


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  B100 Intelligence — ETL Script 04: ML Health Scoring")
    print("  Scoring 101 companies on 5 financial metrics")
    print("=" * 60)

    # ── Connect ───────────────────────────────────────────────
    print("\nConnecting to Neon PostgreSQL...")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT version()")).scalar()
    print(f"  ✅  {ver[:45]}")

    # ── Read tables ───────────────────────────────────────────
    print("\nReading tables from warehouse...")
    companies  = pd.read_sql("SELECT symbol, company_name, sector, roe_pct, roce_pct FROM dim_company", engine)
    pl         = pd.read_sql("SELECT symbol, year_label, sales, net_profit, opm_pct, eps FROM fact_profit_loss", engine)
    bs         = pd.read_sql("SELECT symbol, year_label, debt_to_equity, borrowings, equity_capital FROM fact_balance_sheet", engine)
    cf         = pd.read_sql("SELECT symbol, year_label, free_cash_flow, operating_activity FROM fact_cash_flow", engine)
    print(f"  ✅  Companies: {len(companies)} | P&L rows: {len(pl)} | BS rows: {len(bs)} | CF rows: {len(cf)}")

    # ── Filter out TTM for scoring (use actual years only) ────
    pl_clean = pl[~pl["year_label"].str.upper().str.contains("TTM", na=False)].copy()
    bs_clean = bs[~bs["year_label"].str.upper().str.contains("TTM", na=False)].copy()
    cf_clean = cf[~cf["year_label"].str.upper().str.contains("TTM", na=False)].copy()

    # Convert numeric (PostgreSQL sometimes returns strings)
    for col in ["sales", "opm_pct"]:
        pl_clean[col] = pd.to_numeric(pl_clean[col], errors="coerce")
    bs_clean["debt_to_equity"] = pd.to_numeric(bs_clean["debt_to_equity"], errors="coerce")
    cf_clean["free_cash_flow"] = pd.to_numeric(cf_clean["free_cash_flow"], errors="coerce")

    # ── Build per-company features ────────────────────────────
    print("\nCalculating scoring features per company...")
    results = []

    for _, row in companies.iterrows():
        sym  = row["symbol"]
        name = row["company_name"]
        sect = row["sector"]

        # --- Feature 1: Revenue CAGR (last 3 years available) ---
        sym_pl = pl_clean[pl_clean["symbol"] == sym].sort_values("year_label")
        revenue_cagr = np.nan
        if len(sym_pl) >= 4:
            # Take first and last of last 4 rows (approx 3-year CAGR)
            sales_vals = sym_pl["sales"].dropna().values
            if len(sales_vals) >= 4:
                s_start = sales_vals[-4]
                s_end   = sales_vals[-1]
                if s_start > 0 and s_end > 0:
                    revenue_cagr = ((s_end / s_start) ** (1/3) - 1) * 100

        # --- Feature 2: Average OPM (last 5 years, clean) ---
        avg_opm = np.nan
        opm_vals = sym_pl["opm_pct"].dropna()
        opm_vals = opm_vals[(opm_vals >= -100) & (opm_vals <= 100)]
        if len(opm_vals) >= 2:
            avg_opm = opm_vals.tail(5).mean()

        # --- Feature 3: Debt-to-Equity (latest year) ---
        sym_bs = bs_clean[bs_clean["symbol"] == sym].sort_values("year_label")
        de_ratio = np.nan
        de_vals = sym_bs["debt_to_equity"].dropna()
        de_vals = de_vals[(de_vals >= 0) & (de_vals <= 50)]
        if len(de_vals) > 0:
            de_ratio = de_vals.iloc[-1]

        # --- Feature 4: ROE (from dim_company directly) ---
        roe = pd.to_numeric(row["roe_pct"], errors="coerce")

        # --- Feature 5: FCF consistency ---
        sym_cf = cf_clean[cf_clean["symbol"] == sym]
        fcf_vals = sym_cf["free_cash_flow"].dropna()
        total_cf_years  = len(fcf_vals)
        positive_cf_years = int((fcf_vals > 0).sum())

        # ── Calculate component scores ─────────────────────────
        s1 = score_revenue_growth(revenue_cagr)
        s2 = score_profit_margin(avg_opm)
        s3 = score_debt_equity(de_ratio)
        s4 = score_roe(roe)
        s5 = score_cash_flow(positive_cf_years, total_cf_years)

        total_score   = s1 + s2 + s3 + s4 + s5
        health_label  = get_health_label(total_score)

        results.append({
            "symbol":               sym,
            "company_name":         name,
            "sector":               sect,
            # Raw features
            "revenue_cagr_3y":      round(revenue_cagr, 2) if not np.isnan(revenue_cagr) else None,
            "avg_opm_pct":          round(avg_opm, 2)      if not np.isnan(avg_opm)      else None,
            "latest_de_ratio":      round(de_ratio, 2)     if not np.isnan(de_ratio)     else None,
            "roe_pct":              round(float(roe), 2)   if not np.isnan(float(roe) if roe is not None else np.nan) else None,
            "fcf_positive_years":   positive_cf_years,
            "fcf_total_years":      total_cf_years,
            # Component scores
            "score_revenue_growth": s1,
            "score_profit_margin":  s2,
            "score_debt_equity":    s3,
            "score_roe":            s4,
            "score_cash_flow":      s5,
            # Final
            "total_score":          total_score,
            "health_label":         health_label,
            "max_possible_score":   100,
            "score_pct":            round(total_score / 100 * 100, 1),
        })

    scores_df = pd.DataFrame(results)
    scores_df = scores_df.sort_values("total_score", ascending=False).reset_index(drop=True)
    scores_df["rank"] = scores_df.index + 1

    # ── Print summary ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SCORING RESULTS SUMMARY")
    print("=" * 60)

    label_counts = scores_df["health_label"].value_counts()
    for label in ["EXCELLENT", "GOOD", "AVERAGE", "WEAK", "POOR"]:
        count = label_counts.get(label, 0)
        bar   = "█" * count
        print(f"  {label:<10} {count:>3} companies  {bar}")

    print()
    print(f"  {'Rank':<5} {'Company':<35} {'Score':>6}  {'Label'}")
    print(f"  {'-'*5} {'-'*35} {'-'*6}  {'-'*10}")
    for _, r in scores_df.head(15).iterrows():
        print(f"  {int(r['rank']):<5} {r['company_name'][:34]:<35} {int(r['total_score']):>5}/100  {r['health_label']}")

    print()
    print("  ... (showing top 15)")

    # ── Save to CSV ───────────────────────────────────────────
    clean_dir = BASE_DIR / "data" / "clean"
    csv_path  = clean_dir / "fact_ml_scores.csv"
    scores_df.to_csv(csv_path, index=False)
    print(f"\n  ✅  Saved → {csv_path}")

    # ── Load to Neon ──────────────────────────────────────────
    print("\nLoading fact_ml_scores → Neon PostgreSQL...")
    scores_df.replace({np.nan: None}).to_sql(
        "fact_ml_scores", engine,
        if_exists="replace", index=False,
        chunksize=200, method="multi"
    )
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM fact_ml_scores")).scalar()
    print(f"  ✅  fact_ml_scores loaded: {count} rows")

    # ── Final stats ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Avg Score  : {scores_df['total_score'].mean():.1f} / 100")
    print(f"  Max Score  : {scores_df['total_score'].max()} / 100  ({scores_df.iloc[0]['company_name']})")
    print(f"  Min Score  : {scores_df['total_score'].min()} / 100  ({scores_df.iloc[-1]['company_name']})")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
