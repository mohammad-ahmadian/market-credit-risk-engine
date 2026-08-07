import sys
import os

# Ensure root folder is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pandas as pd
from datetime import datetime
from sqlalchemy import text
from src.database.db_connection import get_db_engine

class StressTestingEngine:
    """
    Portfolio Stress Testing Engine simulating severe market crashes
    and rate shocks on a EUR 10,000,000 multi-asset portfolio.
    """

    def __init__(self, portfolio_value_eur=10_000_000):
        self.engine = get_db_engine()
        self.portfolio_value = portfolio_value_eur

        # Portfolio Weight Allocation across target assets
        # ^GSPC (30%), ^GDAXI (25%), AAPL (20%), DBK.DE (15%), BTC-USD (10%)
        self.weights = {
            "^GSPC": 0.30,
            "^GDAXI": 0.25,
            "AAPL": 0.20,
            "DBK.DE": 0.15,
            "BTC-USD": 0.10
        }

        # Defined Historical & Hypothetical Stress Scenarios
        self.scenarios = {
            "2008_Global_Financial_Crisis": {
                "^GSPC": -0.20, "^GDAXI": -0.22, "AAPL": -0.18, "DBK.DE": -0.35, "BTC-USD": -0.40
            },
            "2020_COVID19_Market_Crash": {
                "^GSPC": -0.12, "^GDAXI": -0.14, "AAPL": -0.10, "DBK.DE": -0.25, "BTC-USD": -0.30
            },
            "2022_Inflation_Rate_Shock": {
                "^GSPC": -0.08, "^GDAXI": -0.10, "AAPL": -0.12, "DBK.DE": +0.05, "BTC-USD": -0.25
            },
            "Crypto_Market_Collapse": {
                "^GSPC": -0.01, "^GDAXI": -0.01, "AAPL": -0.01, "DBK.DE": -0.02, "BTC-USD": -0.70
            }
        }

    def run_stress_tests(self):
        """Calculates portfolio loss under each scenario and saves to PostgreSQL."""
        results = []
        latest_date = datetime.now().strftime('%Y-%m-%d')

        print(f"\n🚨 Running Portfolio Stress Tests (Portfolio Value: EUR {self.portfolio_value:,.2f})...")

        for scenario_name, shocks in self.scenarios.items():
            # Calculate Weighted Portfolio Shock
            portfolio_shock = sum(self.weights[ticker] * shocks.get(ticker, 0.0) for ticker in self.weights)
            
            stressed_val = self.portfolio_value * (1.0 + portfolio_shock)
            dollar_loss = self.portfolio_value - stressed_val
            pct_loss = abs(portfolio_shock) * 100.0

            results.append({
                "scenario_name": scenario_name,
                "calc_date": latest_date,
                "portfolio_value": self.portfolio_value,
                "stressed_portfolio_value": stressed_val,
                "dollar_loss": dollar_loss,
                "percentage_loss": pct_loss
            })

            print(f"⚠️ {scenario_name:30s} | Loss: EUR {dollar_loss:12,.2f} ({pct_loss:5.2f}%) | Stressed Val: EUR {stressed_val:12,.2f}")

        # Store Stress Test Results in PostgreSQL
        if results:
            df_stress = pd.DataFrame(results)
            df_stress['calc_date'] = pd.to_datetime(df_stress['calc_date']).dt.date  # Convert to date object
            
            with self.engine.begin() as conn:
                df_stress.to_sql("temp_stress", conn, if_exists="replace", index=False)
                
                # Explicitly cast calc_date::DATE in SQL statement
                upsert_query = text("""
                    INSERT INTO stress_test_results (scenario_name, calc_date, portfolio_value, stressed_portfolio_value, dollar_loss, percentage_loss)
                    SELECT scenario_name, calc_date::DATE, portfolio_value, stressed_portfolio_value, dollar_loss, percentage_loss
                    FROM temp_stress
                    ON CONFLICT (scenario_name, calc_date) DO UPDATE
                    SET portfolio_value = EXCLUDED.portfolio_value,
                        stressed_portfolio_value = EXCLUDED.stressed_portfolio_value,
                        dollar_loss = EXCLUDED.dollar_loss,
                        percentage_loss = EXCLUDED.percentage_loss;

                    DROP TABLE temp_stress;
                """)
                conn.execute(upsert_query)
            print("🎉 Stress Test Scenarios stored in PostgreSQL successfully!\n")

if __name__ == "__main__":
    stress_engine = StressTestingEngine(portfolio_value_eur=10_000_000)
    stress_engine.run_stress_tests()