# test_connection.py
# Run: python test_connection.py
# If it prints "Connection successful!", you're good to go.

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print("✅ Connection successful!")
        print(f"   PostgreSQL version: {version[:40]}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("   Check your DATABASE_URL in .env file")