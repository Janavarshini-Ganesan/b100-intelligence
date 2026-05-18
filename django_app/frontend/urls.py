from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('companies/', views.companies, name='companies'),
    path('companies/<str:symbol>/', views.company_detail, name='company_detail'),
    path('sectors/', views.sectors, name='sectors'),
    path('sectors/<str:sector_name>/', views.sector_detail, name='sector_detail'),
    path('compare/', views.compare, name='compare'),
    path('search/', views.search, name='search'),
    path('health-scores/', views.health_scores, name='health_scores'),
]