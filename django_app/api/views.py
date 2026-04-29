from django.core.cache import cache
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter


def run_query(sql, params=None):
    """Execute raw SQL and return list of dicts."""
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ─────────────────────────────────────────────────────────────
# COMPANIES
# ─────────────────────────────────────────────────────────────

class CompanyListView(APIView):
    """List all 101 Nifty 100 companies with basic info."""

    @extend_schema(
        parameters=[OpenApiParameter("sector", str, description="Filter by sector")],
        summary="List all companies"
    )
    def get(self, request):
        cache_key = "companies_all"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        sector = request.query_params.get("sector")
        if sector:
            data = run_query(
                "SELECT * FROM dim_company WHERE sector = %s ORDER BY company_name",
                [sector]
            )
        else:
            data = run_query("SELECT * FROM dim_company ORDER BY company_name")

        result = {"count": len(data), "companies": data}
        cache.set(cache_key, result, 3600)
        return Response(result)


class CompanyDetailView(APIView):
    """Get full details of a single company."""

    @extend_schema(summary="Get company detail by symbol")
    def get(self, request, symbol):
        cache_key = f"company_{symbol}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        rows = run_query(
            "SELECT * FROM dim_company WHERE symbol = %s", [symbol.upper()]
        )
        if not rows:
            return Response(
                {"error": f"Company '{symbol}' not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        cache.set(cache_key, rows[0], 3600)
        return Response(rows[0])


# ─────────────────────────────────────────────────────────────
# SECTORS
# ─────────────────────────────────────────────────────────────

class SectorListView(APIView):
    """List all sectors with company count and avg metrics."""

    @extend_schema(summary="List all sectors with stats")
    def get(self, request):
        cache_key = "sectors_summary"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        data = run_query("""
            SELECT
                sector,
                COUNT(*)                         AS company_count,
                ROUND(AVG(NULLIF(roe_pct,'')::numeric), 2)  AS avg_roe_pct,
                ROUND(AVG(NULLIF(roce_pct,'')::numeric), 2) AS avg_roce_pct
            FROM dim_company
            GROUP BY sector
            ORDER BY company_count DESC
        """)

        result = {"count": len(data), "sectors": data}
        cache.set(cache_key, result, 3600)
        return Response(result)


# ─────────────────────────────────────────────────────────────
# FINANCIAL DATA
# ─────────────────────────────────────────────────────────────

class ProfitLossView(APIView):
    """Year-wise Profit & Loss for a company."""

    @extend_schema(summary="Get P&L data for a company")
    def get(self, request, symbol):
        cache_key = f"pl_{symbol}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        rows = run_query("""
            SELECT
                pl.year_label, y.fiscal_year, y.is_ttm,
                pl.sales, pl.expenses, pl.operating_profit,
                pl.opm_pct, pl.net_profit, pl.net_profit_margin_pct,
                pl.eps, pl.tax_pct, pl.interest, pl.depreciation
            FROM fact_profit_loss pl
            JOIN dim_year y ON pl.year_label = y.year_label
            WHERE pl.symbol = %s
            ORDER BY y.sort_order
        """, [symbol.upper()])

        if not rows:
            return Response(
                {"error": f"No P&L data for '{symbol}'"},
                status=status.HTTP_404_NOT_FOUND
            )

        result = {"symbol": symbol.upper(), "count": len(rows), "data": rows}
        cache.set(cache_key, result, 3600)
        return Response(result)


class BalanceSheetView(APIView):
    """Year-wise Balance Sheet for a company."""

    @extend_schema(summary="Get Balance Sheet data for a company")
    def get(self, request, symbol):
        cache_key = f"bs_{symbol}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        rows = run_query("""
            SELECT
                bs.year_label, y.fiscal_year, y.is_ttm,
                bs.equity_capital, bs.reserves, bs.borrowings,
                bs.total_liabilities, bs.total_assets,
                bs.investments, bs.debt_to_equity
            FROM fact_balance_sheet bs
            JOIN dim_year y ON bs.year_label = y.year_label
            WHERE bs.symbol = %s
            ORDER BY y.sort_order
        """, [symbol.upper()])

        if not rows:
            return Response(
                {"error": f"No Balance Sheet data for '{symbol}'"},
                status=status.HTTP_404_NOT_FOUND
            )

        result = {"symbol": symbol.upper(), "count": len(rows), "data": rows}
        cache.set(cache_key, result, 3600)
        return Response(result)


class CashFlowView(APIView):
    """Year-wise Cash Flow for a company."""

    @extend_schema(summary="Get Cash Flow data for a company")
    def get(self, request, symbol):
        cache_key = f"cf_{symbol}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        rows = run_query("""
            SELECT
                cf.year_label, y.fiscal_year,
                cf.operating_activity, cf.investing_activity,
                cf.financing_activity, cf.net_cash_flow,
                cf.free_cash_flow
            FROM fact_cash_flow cf
            JOIN dim_year y ON cf.year_label = y.year_label
            WHERE cf.symbol = %s
            ORDER BY y.sort_order
        """, [symbol.upper()])

        if not rows:
            return Response(
                {"error": f"No Cash Flow data for '{symbol}'"},
                status=status.HTTP_404_NOT_FOUND
            )

        result = {"symbol": symbol.upper(), "count": len(rows), "data": rows}
        cache.set(cache_key, result, 3600)
        return Response(result)


# ─────────────────────────────────────────────────────────────
# ML SCORES
# ─────────────────────────────────────────────────────────────

class MLScoreListView(APIView):
    """All company ML health scores, ranked."""

    @extend_schema(
        parameters=[
            OpenApiParameter("label",  str, description="Filter: EXCELLENT/GOOD/AVERAGE/WEAK/POOR"),
            OpenApiParameter("sector", str, description="Filter by sector"),
        ],
        summary="Get all ML health scores"
    )
    def get(self, request):
        label  = request.query_params.get("label", "").upper()
        sector = request.query_params.get("sector", "")

        cache_key = f"scores_{label}_{sector}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        sql = """
            SELECT symbol, company_name, sector, rank,
                   total_score, health_label, score_pct,
                   score_revenue_growth, score_profit_margin,
                   score_debt_equity, score_roe, score_cash_flow,
                   revenue_cagr_3y, avg_opm_pct, latest_de_ratio,
                   roe_pct, fcf_positive_years, fcf_total_years
            FROM fact_ml_scores
            WHERE 1=1
        """
        params = []
        if label:
            sql += " AND health_label = %s"
            params.append(label)
        if sector:
            sql += " AND sector = %s"
            params.append(sector)
        sql += " ORDER BY rank ASC"

        rows = run_query(sql, params)
        result = {"count": len(rows), "scores": rows}
        cache.set(cache_key, result, 3600)
        return Response(result)


class MLScoreDetailView(APIView):
    """ML health score detail for one company."""

    @extend_schema(summary="Get ML score for a specific company")
    def get(self, request, symbol):
        rows = run_query(
            "SELECT * FROM fact_ml_scores WHERE symbol = %s",
            [symbol.upper()]
        )
        if not rows:
            return Response(
                {"error": f"No score found for '{symbol}'"},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(rows[0])


# ─────────────────────────────────────────────────────────────
# DASHBOARD SUMMARY (KPIs)
# ─────────────────────────────────────────────────────────────

class DashboardSummaryView(APIView):
    """Top-level KPIs for the executive dashboard."""

    @extend_schema(summary="Get dashboard summary KPIs")
    def get(self, request):
        cache_key = "dashboard_summary"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        total = run_query("SELECT COUNT(*) AS total FROM dim_company")[0]["total"]

        avg_roe = run_query(
            "SELECT ROUND(AVG(NULLIF(roe_pct,'')::numeric), 2) AS avg_roe FROM dim_company"
        )[0]["avg_roe"]

        revenue = run_query("""
            SELECT ROUND(SUM(pl.sales)::numeric, 2) AS total_revenue
            FROM fact_profit_loss pl
            JOIN dim_year y ON pl.year_label = y.year_label
            WHERE y.fiscal_year = (SELECT MAX(fiscal_year) FROM dim_year WHERE is_ttm = FALSE)
              AND y.is_ttm = FALSE
        """)[0]["total_revenue"]

        health = run_query("""
            SELECT health_label, COUNT(*) AS count
            FROM fact_ml_scores
            GROUP BY health_label
            ORDER BY count DESC
        """)

        top5 = run_query("""
            SELECT symbol, company_name, sector, total_score, health_label
            FROM fact_ml_scores
            ORDER BY rank ASC LIMIT 5
        """)

        sectors = run_query(
            "SELECT COUNT(DISTINCT sector) AS count FROM dim_company"
        )[0]["count"]

        result = {
            "total_companies":           total,
            "total_sectors":             sectors,
            "avg_roe_pct":               float(avg_roe) if avg_roe else 0,
            "latest_year_revenue_cr":    float(revenue) if revenue else 0,
            "health_distribution":       health,
            "top_5_companies":           top5,
        }

        cache.set(cache_key, result, 3600)
        return Response(result)
