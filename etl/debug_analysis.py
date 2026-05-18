"""
etl/debug_analysis.py
Run this first to see the actual column names in analysis.xlsx
"""
import os
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(BASE, "data", "raw", "analysis.xlsx")

print("Reading analysis.xlsx...")
# Try different header rows
for h in [0, 1, 2]:
    df = pd.read_excel(path, header=h, nrows=5)
    print(f"\n--- header={h} ---")
    print("Columns:", list(df.columns))
    print(df.head(3).to_string())
    print()