from django.urls import path
from . import views

urlpatterns = [
    # ── Companies ─────────────────────────────
    path("companies/",           views.CompanyListView.as_view(),    name="company-list"),
    path("companies/<str:symbol>/", views.CompanyDetailView.as_view(), name="company-detail"),

    # ── Sectors ───────────────────────────────
    path("sectors/",             views.SectorListView.as_view(),     name="sector-list"),

    # ── Financial Data ─────────────────────────
    path("financials/<str:symbol>/pl/",      views.ProfitLossView.as_view(),   name="pl"),
    path("financials/<str:symbol>/bs/",      views.BalanceSheetView.as_view(), name="bs"),
    path("financials/<str:symbol>/cf/",      views.CashFlowView.as_view(),     name="cf"),

    # ── ML Scores ─────────────────────────────
    path("scores/",              views.MLScoreListView.as_view(),    name="score-list"),
    path("scores/<str:symbol>/", views.MLScoreDetailView.as_view(),  name="score-detail"),

    # ── Dashboard KPIs ─────────────────────────
    path("dashboard/summary/",   views.DashboardSummaryView.as_view(), name="summary"),
]