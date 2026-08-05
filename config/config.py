import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "RiskDataDB")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Assets to track for portfolio risk management
TARGET_ASSETS = [
    {"ticker": "^GSPC", "name": "S&P 500", "class": "Equity Index", "currency": "USD"},
    {"ticker": "^GDAXI", "name": "DAX 40", "class": "Equity Index", "currency": "EUR"},
    {"ticker": "AAPL", "name": "Apple Inc.", "class": "Equity Stock", "currency": "USD"},
    {"ticker": "DBK.DE", "name": "Deutsche Bank AG", "class": "Equity Stock", "currency": "EUR"},
    {"ticker": "BTC-USD", "name": "Bitcoin", "class": "Crypto", "currency": "USD"},
]

# Yield Curve Tickers (US Treasury Yields from Yahoo Finance)
YIELD_TICKERS = {
    "^IRX": "13W",  # 3-Month Bill
    "^FVX": "5Y",   # 5-Year Treasury
    "^TNX": "10Y",  # 10-Year Treasury
    "^TYX": "30Y"   # 30-Year Treasury
}