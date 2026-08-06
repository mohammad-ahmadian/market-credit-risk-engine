import sys
import os

# Ensure root folder is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import numpy as np
import pandas as pd
from scipy.stats import norm
from sqlalchemy import text
from src.database.db_connection import get_db_engine

class RiskAnalyticsEngine:
    """
    Quantitative Risk Analytics Engine calculating:
    - Parametric Value-at-Risk (Normal Distribution)
    - Historical Simulation Value-at-Risk
    - Expected Shortfall (Conditional VaR)
    """

    def __init__(self):
        self.engine = get_db_engine()

    def fetch_returns_data(self):
        """Fetches historical log returns from PostgreSQL daily_market_data table."""
        query = """
            SELECT 
                d.asset_id,
                a.ticker,
                a.asset_name,
                d.price_date,
                d.log_return
            FROM daily_market_data d
            JOIN asset_metadata a ON d.asset_id = a.asset_id
            WHERE d.log_return IS NOT NULL
            ORDER BY a.ticker, d.price_date ASC;
        """
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df

    @staticmethod
    def calculate_parametric_var(returns, confidence_level=0.95):
        """
        Calculates Parametric VaR assuming Normal Distribution.
        Loss is returned as a positive number.
        """
        mu = np.mean(returns)
        sigma = np.std(returns, ddof=1)
        z_score = norm.ppf(1 - confidence_level)
        var = -(mu + z_score * sigma)
        return max(0.0, float(var))

    @staticmethod
    def calculate_historical_var(returns, confidence_level=0.95):
        """
        Calculates Historical Simulation VaR using empirical percentiles.
        Loss is returned as a positive number.
        """
        percentile = (1 - confidence_level) * 100
        var = -np.percentile(returns, percentile)
        return max(0.0, float(var))

    @staticmethod
    def calculate_expected_shortfall(returns, confidence_level=0.95):
        """
        Calculates Expected Shortfall (Tail Loss beyond VaR).
        Loss is returned as a positive number.
        """
        percentile = (1 - confidence_level) * 100
        cutoff = np.percentile(returns, percentile)
        tail_losses = returns[returns <= cutoff]
        if len(tail_losses) == 0:
            return 0.0
        expected_shortfall = -np.mean(tail_losses)
        return max(0.0, float(expected_shortfall))

    def compute_rolling_risk_metrics(self, window=250, confidence_levels=[0.95, 0.99]):
        """
        Computes rolling 250-day window VaR and ES for each asset over time,
        and uploads results to PostgreSQL portfolio_risk_metrics table.
        """
        df_returns = self.fetch_returns_data()
        results = []

        print(f"⚙️ Calculating Rolling Risk Metrics ({window}-day window)...")

        for (asset_id, ticker), group in df_returns.groupby(['asset_id', 'ticker']):
            group = group.sort_values('price_date').reset_index(drop=True)
            returns = group['log_return'].values
            dates = group['price_date'].values

            if len(returns) < window:
                print(f"⚠️ Skipping {ticker}: Insufficient data ({len(returns)} < {window} days)")
                continue

            # Compute rolling metrics across time
            for i in range(window, len(returns)):
                calc_date = dates[i]
                window_returns = returns[i - window : i]

                for conf in confidence_levels:
                    p_var = self.calculate_parametric_var(window_returns, confidence_level=conf)
                    h_var = self.calculate_historical_var(window_returns, confidence_level=conf)
                    es = self.calculate_expected_shortfall(window_returns, confidence_level=conf)

                    results.append({
                        "asset_id": int(asset_id),
                        "calc_date": calc_date,
                        "confidence_level": float(conf),
                        "parametric_var": p_var,
                        "historical_var": h_var,
                        "expected_shortfall": es
                    })

            print(f"✅ Risk metrics computed for {ticker}.")

        # Load computed risk metrics into PostgreSQL
        if results:
            df_risk = pd.DataFrame(results)
            print(f"📥 Loading {len(df_risk)} risk records into PostgreSQL...")

            with self.engine.begin() as conn:
                df_risk.to_sql("temp_risk_metrics", conn, if_exists="replace", index=False)
                
                upsert_query = text("""
                    INSERT INTO portfolio_risk_metrics (asset_id, calc_date, confidence_level, parametric_var, historical_var, expected_shortfall)
                    SELECT asset_id, calc_date, confidence_level, parametric_var, historical_var, expected_shortfall
                    FROM temp_risk_metrics
                    ON CONFLICT (asset_id, calc_date, confidence_level) DO UPDATE
                    SET parametric_var = EXCLUDED.parametric_var,
                        historical_var = EXCLUDED.historical_var,
                        expected_shortfall = EXCLUDED.expected_shortfall;

                    DROP TABLE temp_risk_metrics;
                """)
                conn.execute(upsert_query)

            print("🎉 Risk metrics stored in PostgreSQL successfully!")

    def generate_summary_report(self):
        """Prints a high-level summary report of recent risk metrics across assets."""
        query = """
            SELECT 
                a.ticker,
                a.asset_name,
                r.calc_date,
                r.confidence_level,
                ROUND(r.parametric_var * 100, 2) AS parametric_var_pct,
                ROUND(r.historical_var * 100, 2) AS historical_var_pct,
                ROUND(r.expected_shortfall * 100, 2) AS expected_shortfall_pct
            FROM portfolio_risk_metrics r
            JOIN asset_metadata a ON r.asset_id = a.asset_id
            WHERE r.calc_date = (SELECT MAX(calc_date) FROM portfolio_risk_metrics)
            ORDER BY r.confidence_level DESC, r.historical_var DESC;
        """
        with self.engine.connect() as conn:
            summary_df = pd.read_sql(query, conn)
        
        print("\n=======================================================")
        print("📊 LATEST DAILY PORTFOLIO RISK SUMMARY REPORT")
        print("=======================================================")
        print(summary_df.to_string(index=False))
        print("=======================================================\n")

if __name__ == "__main__":
    engine = RiskAnalyticsEngine()
    engine.compute_rolling_risk_metrics(window=250, confidence_levels=[0.95, 0.99])
    engine.generate_summary_report()