import re

def standardize_year(year_str):
    """
    'Mar-13'   → 'Mar 2013'
    'Mar 2024' → 'Mar 2024'  (already clean)
    'Dec 2012' → 'Dec 2012'  (already clean)
    'Sep 2024' → 'Sep 2024'  (already clean)
    'TTM'      → 'TTM'
    """
    year_str = str(year_str).strip()
    if year_str == 'TTM': return 'TTM'

    # Handle 'Mar-13' format (cashflow table)
    match = re.match(r'(\w{3})-(\d{2})$', year_str)
    if match:
        mon, yr = match.groups()
        full_yr = f"20{yr}" if int(yr) > 0 else f"20{yr}"
        return f"{mon} 20{yr}"

    return year_str  # already in 'Mar 2024' format

def get_fiscal_year(year_label):
    if year_label == 'TTM': return 9999  # sort last
    match = re.search(r'(\d{4})', year_label)
    return int(match.group(1)) if match else None

def get_sort_order(year_label):
    month_order = {'Mar':3,'Jun':6,'Sep':9,'Dec':12,'Jan':1,'Feb':2}
    if year_label == 'TTM': return 99999
    parts = year_label.split()
    mon = month_order.get(parts[0], 3)
    yr = int(parts[1])
    return yr * 100 + mon

def parse_analysis_value(text):
    """'10 Years: 21%' → ('10Y', 21.0)"""
    if pd.isna(text): return None, None
    text = str(text).strip()
    period_map = {'10 Years': '10Y', '5 Years': '5Y',
                  '3 Years': '3Y', 'TTM': 'TTM',
                  '1 Year': 'TTM', 'Last Year': 'TTM'}
    for key, label in period_map.items():
        if key in text:
            match = re.search(r'(-?\d+)', text)
            val = float(match.group(1)) if match else None
            return label, val
    return None, None

SECTOR_MAP = {
    # IT
    'TCS':'IT', 'INFY':'IT', 'WIPRO':'IT', 'HCLTECH':'IT',
    'TECHM':'IT', 'LTIM':'IT', 'PERSISTENT':'IT',
    # Banking
    'HDFCBANK':'Banking', 'AXISBANK':'Banking', 'ICICIBANK':'Banking',
    'KOTAKBANK':'Banking', 'SBIN':'Banking', 'BANKBARODA':'Banking',
    'UNIONBANK':'Banking', 'CANBK':'Banking', 'PNB':'Banking',
    # NBFC/Finance
    'BAJFINANCE':'NBFC', 'BAJAJFINSV':'NBFC', 'CHOLAFIN':'NBFC',
    'MUTHOOTFIN':'NBFC', 'HDFCLIFE':'Insurance', 'SBILIFE':'Insurance',
    'ICICIGI':'Insurance',
    # Energy/Power
    'ADANIGREEN':'Energy', 'ADANIPOWER':'Energy', 'ADANIENSOL':'Energy',
    'ATGL':'Energy', 'TATAPOWER':'Energy', 'NTPC':'Energy',
    'POWERGRID':'Energy', 'GAIL':'Energy', 'COALINDIA':'Energy',
    'BPCL':'Energy', 'IOC':'Energy', 'ONGC':'Energy',
    # Ports/Infra
    'ADANIPORTS':'Infrastructure', 'ADANIENT':'Infrastructure', 'LT':'Infrastructure',
    # Cement
    'AMBUJACEM':'Cement', 'ULTRACEMCO':'Cement', 'GRASIM':'Cement', 'JSWSTEEL':'Metals',
    # Healthcare/Pharma
    'APOLLOHOSP':'Healthcare', 'DRREDDY':'Pharma', 'CIPLA':'Pharma',
    'SUNPHARMA':'Pharma', 'DIVISLAB':'Pharma', 'TORNTPHARM':'Pharma',
    # FMCG/Consumer
    'HINDUNILVR':'FMCG', 'DABUR':'FMCG', 'GODREJCP':'FMCG',
    'MARICO':'FMCG', 'COLPAL':'FMCG', 'NESTLEIND':'FMCG',
    'BRITANNIA':'FMCG', 'TRENT':'Retail', 'DMART':'Retail',
    # Auto
    'BAJAJ-AUTO':'Auto', 'TATAMOTORS':'Auto', 'MARUTI':'Auto',
    'HEROMOTOCO':'Auto', 'EICHERMOT':'Auto', 'TVSMOTOR':'Auto',
    'M&M':'Auto',
    # Paints
    'ASIANPAINT':'Paints',
    # Others
    'TITAN':'Consumer Goods', 'ABB':'Capital Goods',
    # ... add remaining companies
}

# In fact_balance_sheet
df['debt_to_equity'] = df['borrowings'] / (df['equity_capital'] + df['reserves'])

# In fact_profit_loss
df['net_profit_margin_pct'] = (df['net_profit'] / df['sales']) * 100
df['expense_ratio_pct'] = (df['expenses'] / df['sales']) * 100
df['interest_coverage'] = df['operating_profit'] / df['interest'].replace(0, float('nan'))

# In fact_cash_flow
df['free_cash_flow'] = df['operating_activity'] + df['investing_activity']