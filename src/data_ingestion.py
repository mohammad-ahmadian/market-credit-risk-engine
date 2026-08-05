import sys
import os

# Ensure root folder is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import numpy as np
import pandas as pd
import yfinance as yf
from sqlalchemy import text
from config.config import TARGET_ASSETS, YIELD_TICKERS
from src.database.db_connection import get_db_engine

class MarketDataIngestor:
    def __init__(self):
        self.engine = get_db_engine()
        self.create_tables_if_not_exist()

    def create_tables_if_not_exist(self):
        """Reads schema.sql and creates tables if they do not exist."""
        schema_path = os.path.join(os.path.dirname(__file__), 'database', 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            with self.engine.begin() as conn:
                conn.execute(text(schema_sql))

    def sync_asset_metadata(self):
        """Populates the asset_metadata table in PostgreSQL."""
        print("🔄 Syncing asset metadata...")
        with self.engine.begin() as conn:
            for asset in TARGET_ASSETS:
                query = text("""
                    INSERT INTO asset_metadata (ticker, asset_name, asset_class, currency)
                    VALUES (:ticker, :name, :class, :currency)
                    ON CONFLICT (ticker) DO UPDATE 
                    SET asset_name = EXCLUDED.asset_name,
                        asset_class = EXCLUDED.asset_class,
                        currency = EXCLUDED.currency;
                """)
                conn.execute(query, {
                    "ticker": asset["ticker"],
                    "name": asset["name"],
                    "class": asset["class"],
                    "currency": asset["currency"]
                })
        print("✅ Asset metadata sync complete.")

    def _clean_yfinance_columns(self, df):
        """Helper method to robustly rename yfinance columns across all versions."""
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Standardize strings
        df.columns = [str(col).strip() for col in df.columns]

        col_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'date' in col_lower:
                col_map[col] = 'price_date'
            elif 'adj close' in col_lower or 'adjclose' in col_lower:
                col_map[col] = 'adj_close'
            elif 'close' in col_lower:
                col_map[col] = 'close_price'
            elif 'open' in col_lower:
                col_map[col] = 'open_price'
            elif 'high' in col_lower:
                col_map[col] = 'high_price'
            elif 'low' in col_lower:
                col_map[col] = 'low_price'
            elif 'volume' in col_lower:
                col_map[col] = 'volume'

        df.rename(columns=col_map, inplace=True)

        # Fallback: if 'adj_close' is missing, use 'close_price'
        if 'adj_close' not in df.columns and 'close_price' in df.columns:
            df['adj_close'] = df['close_price']
            
        return df

    def fetch_and_load_market_data(self, start_date="2018-01-01"):
        """Fetches daily market data via yfinance, computes log returns, and loads to DB."""
        self.sync_asset_metadata()

        with self.engine.connect() as conn:
            metadata_df = pd.read_sql("SELECT asset_id, ticker FROM asset_metadata", conn)
        ticker_to_id = dict(zip(metadata_df['ticker'], metadata_df['asset_id']))

        for asset in TARGET_ASSETS:
            ticker = asset["ticker"]
            asset_id = ticker_to_id[ticker]
            print(f"📥 Fetching market data for {ticker} (Asset ID: {asset_id})...")

            df = yf.download(ticker, start=start_date, progress=False)
            if df.empty:
                print(f"⚠️ Warning: No data found for {ticker}")
                continue

            df.reset_index(inplace=True)
            df = self._clean_yfinance_columns(df)

            # Econometric Feature Engineering: Compute Log Return ln(P_t / P_{t-1})
            df['log_return'] = np.log(df['adj_close'] / df['adj_close'].shift(1))
            df['asset_id'] = asset_id

            # Filter valid rows
            df_to_load = df[['asset_id', 'price_date', 'open_price', 'high_price', 
                             'low_price', 'close_price', 'adj_close', 'volume', 'log_return']].dropna(subset=['adj_close'])

            # Fast Ingestion via Temporary Table + UPSERT
            with self.engine.begin() as conn:
                df_to_load.to_sql("temp_market_data", conn, if_exists="replace", index=False)
                
                upsert_query = text("""
                    INSERT INTO daily_market_data (asset_id, price_date, open_price, high_price, low_price, close_price, adj_close, volume, log_return)
                    SELECT asset_id, price_date, open_price, high_price, low_price, close_price, adj_close, volume, log_return
                    FROM temp_market_data
                    ON CONFLICT (asset_id, price_date) DO UPDATE
                    SET adj_close = EXCLUDED.adj_close,
                        close_price = EXCLUDED.close_price,
                        log_return = EXCLUDED.log_return,
                        volume = EXCLUDED.volume;
                    
                    DROP TABLE temp_market_data;
                """)
                conn.execute(upsert_query)

            print(f"✅ Loaded {len(df_to_load)} records for {ticker}.")

    def fetch_and_load_yield_curve(self, start_date="2018-01-01"):
        """Fetches Treasury yield curve data."""
        print("📈 Fetching US Treasury Yield Curve Data...")
        rates_data = []

        for ticker, tenor in YIELD_TICKERS.items():
            df = yf.download(ticker, start=start_date, progress=False)
            if df.empty:
                continue

            df.reset_index(inplace=True)
            df = self._clean_yfinance_columns(df)
            
            df['tenor'] = tenor
            df.rename(columns={"close_price": "yield_pct"}, inplace=True)
            if "yield_pct" not in df.columns and "adj_close" in df.columns:
                df["yield_pct"] = df["adj_close"]

            df_clean = df[['price_date', 'tenor', 'yield_pct']].dropna()
            df_clean.rename(columns={'price_date': 'rate_date'}, inplace=True)
            rates_data.append(df_clean)

        if rates_data:
            full_rates_df = pd.concat(rates_data, ignore_index=True)
            with self.engine.begin() as conn:
                full_rates_df.to_sql("temp_rates", conn, if_exists="replace", index=False)
                upsert_rates = text("""
                    INSERT INTO daily_interest_rates (rate_date, tenor, yield_pct)
                    SELECT rate_date, tenor, yield_pct FROM temp_rates
                    ON CONFLICT (tenor, rate_date) DO UPDATE
                    SET yield_pct = EXCLUDED.yield_pct;
                    
                    DROP TABLE temp_rates;
                """)
                conn.execute(upsert_rates)
            print("✅ Yield curve data loaded successfully.")

if __name__ == "__main__":
    ingestor = MarketDataIngestor()
    ingestor.fetch_and_load_market_data()
    ingestor.fetch_and_load_yield_curve()