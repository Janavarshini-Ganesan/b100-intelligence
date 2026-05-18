from django.shortcuts import render

def home(request):
    return render(request, 'frontend/home.html')

def companies(request):
    return render(request, 'frontend/companies.html')

def company_detail(request, symbol):
    return render(request, 'frontend/company_detail.html', {
        'symbol': symbol.upper()
    })

def sectors(request):
    return render(request, 'frontend/sector.html')

# views.py — sector_detail page view
def sector_detail(request, sector_name):
    return render(request, 'frontend/sector_detail.html', {
        'sector_name': sector_name   # ← must pass this!
    })

def health_scores(request):
    return render(request, 'frontend/health_score.html')

def compare(request):
    return render(request, 'frontend/compare.html')

def search(request):
    query = request.GET.get('q', '')
    return render(request, 'frontend/search_results.html', {
        'query': query
    })

