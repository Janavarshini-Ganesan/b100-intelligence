from rest_framework import serializers


class CompanySerializer(serializers.Serializer):
    symbol = serializers.CharField()
    company_name = serializers.CharField()
    sector = serializers.CharField(allow_null=True, required=False)
    about_company = serializers.CharField(allow_null=True, required=False)
    company_logo = serializers.CharField(allow_null=True, required=False)
    website = serializers.CharField(allow_null=True, required=False)
    nse_url = serializers.CharField(allow_null=True, required=False)
    bse_url = serializers.CharField(allow_null=True, required=False)
    face_value = serializers.FloatField(allow_null=True, required=False)
    book_value = serializers.FloatField(allow_null=True, required=False)
    roce_pct = serializers.FloatField(allow_null=True, required=False)
    roe_pct = serializers.FloatField(allow_null=True, required=False)


class CompanyListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    companies = CompanySerializer(many=True)


class ErrorSerializer(serializers.Serializer):
    error = serializers.CharField()


class SectorSerializer(serializers.Serializer):
    sector = serializers.CharField()
    company_count = serializers.IntegerField()
    avg_roe_pct = serializers.FloatField(allow_null=True, required=False)
    avg_roce_pct = serializers.FloatField(allow_null=True, required=False)


class SectorListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    sectors = SectorSerializer(many=True)


class ProfitLossItemSerializer(serializers.Serializer):
    year_label = serializers.CharField()
    fiscal_year = serializers.IntegerField(allow_null=True, required=False)
    is_ttm = serializers.BooleanField(allow_null=True, required=False)
    sales = serializers.FloatField(allow_null=True, required=False)
    expenses = serializers.FloatField(allow_null=True, required=False)
    operating_profit = serializers.FloatField(allow_null=True, required=False)
    opm_pct = serializers.FloatField(allow_null=True, required=False)
    net_profit = serializers.FloatField(allow_null=True, required=False)
    net_profit_margin_pct = serializers.FloatField(allow_null=True, required=False)
    eps = serializers.FloatField(allow_null=True, required=False)
    tax_pct = serializers.FloatField(allow_null=True, required=False)
    interest = serializers.FloatField(allow_null=True, required=False)
    depreciation = serializers.FloatField(allow_null=True, required=False)


class ProfitLossResponseSerializer(serializers.Serializer):
    symbol = serializers.CharField()
    count = serializers.IntegerField()
    data = ProfitLossItemSerializer(many=True)


class BalanceSheetItemSerializer(serializers.Serializer):
    year_label = serializers.CharField()
    fiscal_year = serializers.IntegerField(allow_null=True, required=False)
    is_ttm = serializers.BooleanField(allow_null=True, required=False)
    equity_capital = serializers.FloatField(allow_null=True, required=False)
    reserves = serializers.FloatField(allow_null=True, required=False)
    borrowings = serializers.FloatField(allow_null=True, required=False)
    total_liabilities = serializers.FloatField(allow_null=True, required=False)
    total_assets = serializers.FloatField(allow_null=True, required=False)
    investments = serializers.FloatField(allow_null=True, required=False)
    debt_to_equity = serializers.FloatField(allow_null=True, required=False)


class BalanceSheetResponseSerializer(serializers.Serializer):
    symbol = serializers.CharField()
    count = serializers.IntegerField()
    data = BalanceSheetItemSerializer(many=True)


class CashFlowItemSerializer(serializers.Serializer):
    year_label = serializers.CharField()
    fiscal_year = serializers.IntegerField(allow_null=True, required=False)
    operating_activity = serializers.FloatField(allow_null=True, required=False)
    investing_activity = serializers.FloatField(allow_null=True, required=False)
    financing_activity = serializers.FloatField(allow_null=True, required=False)
    net_cash_flow = serializers.FloatField(allow_null=True, required=False)
    free_cash_flow = serializers.FloatField(allow_null=True, required=False)


class CashFlowResponseSerializer(serializers.Serializer):
    symbol = serializers.CharField()
    count = serializers.IntegerField()
    data = CashFlowItemSerializer(many=True)


class MLScoreSerializer(serializers.Serializer):
    symbol = serializers.CharField()
    company_name = serializers.CharField()
    sector = serializers.CharField(allow_null=True, required=False)
    rank = serializers.IntegerField(allow_null=True, required=False)
    total_score = serializers.FloatField(allow_null=True, required=False)
    health_label = serializers.CharField(allow_null=True, required=False)
    score_pct = serializers.FloatField(allow_null=True, required=False)
    score_revenue_growth = serializers.FloatField(allow_null=True, required=False)
    score_profit_margin = serializers.FloatField(allow_null=True, required=False)
    score_debt_equity = serializers.FloatField(allow_null=True, required=False)
    score_roe = serializers.FloatField(allow_null=True, required=False)
    score_cash_flow = serializers.FloatField(allow_null=True, required=False)
    revenue_cagr_3y = serializers.FloatField(allow_null=True, required=False)
    avg_opm_pct = serializers.FloatField(allow_null=True, required=False)
    latest_de_ratio = serializers.FloatField(allow_null=True, required=False)
    roe_pct = serializers.FloatField(allow_null=True, required=False)
    fcf_positive_years = serializers.IntegerField(allow_null=True, required=False)
    fcf_total_years = serializers.IntegerField(allow_null=True, required=False)


class MLScoreListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    scores = MLScoreSerializer(many=True)


class TopCompanySerializer(serializers.Serializer):
    symbol = serializers.CharField()
    company_name = serializers.CharField()
    sector = serializers.CharField(allow_null=True, required=False)
    total_score = serializers.FloatField(allow_null=True, required=False)
    health_label = serializers.CharField(allow_null=True, required=False)


class HealthDistributionSerializer(serializers.Serializer):
    health_label = serializers.CharField()
    count = serializers.IntegerField()


class DashboardSummaryResponseSerializer(serializers.Serializer):
    total_companies = serializers.IntegerField()
    total_sectors = serializers.IntegerField()
    avg_roe_pct = serializers.FloatField()
    latest_year_revenue_cr = serializers.FloatField()
    health_distribution = HealthDistributionSerializer(many=True)
    top_5_companies = TopCompanySerializer(many=True)


class TaskTriggerResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    task_id = serializers.CharField()
    status = serializers.CharField()
    note = serializers.CharField(required=False)


class ETLStatusResponseSerializer(serializers.Serializer):
    checked_at = serializers.CharField()
    result = serializers.JSONField()