from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os, pandas as pd

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

# Load order matters: dim tables first, then fact tables
LOAD_ORDER = [
    ("dim_sector", "data/clean/dim_sector.csv"),
    ("dim_company", "data/clean/dim_company.csv"),
    ("dim_year", "data/clean/dim_year.csv"),
    ("dim_health_label", "data/clean/dim_health_label.csv"),
    ("fact_profit_loss", "data/clean/fact_profit_loss.csv"),
    ("fact_balance_sheet", "data/clean/fact_balance_sheet.csv"),
    ("fact_cash_flow", "data/clean/fact_cash_flow.csv"),
    ("fact_analysis", "data/clean/fact_analysis.csv"),
    ("fact_pros_cons", "data/clean/fact_pros_cons.csv"),
]

for table_name, csv_path in LOAD_ORDER:
    df = pd.read_csv(csv_path)
    df.to_sql(table_name, engine, if_exists='replace', index=False)
    print(f"✅ Loaded {len(df)} rows into {table_name}")