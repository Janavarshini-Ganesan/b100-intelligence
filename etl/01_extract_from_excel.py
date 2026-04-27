import pandas as pd
import os

FILES = {
    "companies":    "data/companies.xlsx",
    "analysis":     "data/analysis.xlsx",
    "balancesheet": "data/balancesheet.xlsx",
    "profitandloss":"data/profitandloss.xlsx",
    "cashflow":     "data/cashflow.xlsx",
    "prosandcons":  "data/prosandcons.xlsx",
    "documents":    "data/documents.xlsx",
}

SHEET_NAMES = {
    "companies": "Companies", "analysis": "Analysis",
    "balancesheet": "Balance Sheet", "profitandloss": "Profit & Loss",
    "cashflow": "Cash Flow", "prosandcons": "Pros & Cons",
    "documents": "Documents"
}

os.makedirs("data/raw", exist_ok=True)

for name, path in FILES.items():
    df = pd.read_excel(path, sheet_name=SHEET_NAMES[name], skiprows=1)
    df.to_csv(f"data/raw/{name}.csv", index=False)
    print(f"✅ {name}: {len(df)} rows, columns: {list(df.columns)}")