import sys
import os

# Ensure root folder is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pandas as pd
from datetime import datetime
from sqlalchemy import text
from src.database.db_connection import get_db_engine

class VaRBacktestingEngine:
    """
    Backtests VaR predictions against actual daily losses and evaluates model
    validity using the Basel III Traffic Light System (Green, Yellow, Red).
    """

    def __init__(self):
        self.engine = get_db_engine()

    def run_backtest(self):
        """Compares actual log returns against historical VaR estimates."""
        query = """
            SELECT 
                r.asset_id,
                a.ticker,
                r.calc_date,
                r.confidence_level,
                r.historical_var,
                d.log_return
            FROM portfolio_risk_metrics r
            JOIN daily_market_data d ON r.asset_id = d.asset_id AND r.calc_date = d.price_date
            JOIN asset_metadata a ON r.asset_id = a.asset_id
            ORDER BY a.ticker, r.confidence_level, r.calc_date ASC;
        """
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn)

        results = []
        latest_date = datetime.now().strftime('%Y-%m-%d')

        print("\n🚦 Running Basel III VaR Model Backtesting...")

        for (asset_id, ticker, conf), group in df.groupby(['asset_id', 'ticker', 'confidence_level']):
            total_days = len(group)
            if total_days == 0:
                continue

            # Actual loss occurs when log_return < 0. Breach occurs if -log_return > VaR
            actual_losses = -group['log_return']
            var_thresholds = group['historical_var']
            
            # Count exceptions (breaches)
            exceptions = int((actual_losses > var_thresholds).sum())
            expected_exceptions = total_days * (1.0 - conf)
            exception_rate = exceptions / total_days

            # Assign Basel Traffic Light Zone (for 99% VaR over ~250 days standard)
            if conf == 0.99:
                if exceptions <= 4:
                    zone = "Green"
                elif 5 <= exceptions <= 9:
                    zone = "Yellow"
                else:
                    zone = "Red"
            else:
                # 95% VaR Basel adjustment (~12.5 expected exceptions per 250 days)
                if exceptions <= 15:
                    zone = "Green"
                elif 16 <= exceptions <= 22:
                    zone = "Yellow"
                else:
                    zone = "Red"

            results.append({
                "asset_id": int(asset_id),
                "confidence_level": float(conf),
                "total_days": int(total_days),
                "expected_exceptions": float(expected_exceptions),
                "actual_exceptions": int(exceptions),
                "exception_rate": float(exception_rate),
                "basel_zone": zone,
                "calc_date": latest_date
            })

            color_icon = "🟢" if zone == "Green" else ("🟡" if zone == "Yellow" else "🔴")
            print(f"{color_icon} {ticker:7s} | Conf: {conf*100:.0f}% | Days: {total_days} | Actual Exceptions: {exceptions:2d} (Expected: {expected_exceptions:4.1f}) | Zone: {zone}")

        # Store Backtest Results in PostgreSQL
        if results:
            df_backtest = pd.DataFrame(results)
            df_backtest['calc_date'] = pd.to_datetime(df_backtest['calc_date']).dt.date

            with self.engine.begin() as conn:
                df_backtest.to_sql("temp_backtest", conn, if_exists="replace", index=False)
                
                upsert_query = text("""
                    INSERT INTO var_backtest_results (asset_id, confidence_level, total_days, expected_exceptions, actual_exceptions, exception_rate, basel_zone, calc_date)
                    SELECT asset_id, confidence_level, total_days, expected_exceptions, actual_exceptions, exception_rate, basel_zone, calc_date::DATE
                    FROM temp_backtest
                    ON CONFLICT (asset_id, confidence_level, calc_date) DO UPDATE
                    SET total_days = EXCLUDED.total_days,
                        expected_exceptions = EXCLUDED.expected_exceptions,
                        actual_exceptions = EXCLUDED.actual_exceptions,
                        exception_rate = EXCLUDED.exception_rate,
                        basel_zone = EXCLUDED.basel_zone;

                    DROP TABLE temp_backtest;
                """)
                conn.execute(upsert_query)
            print("🎉 VaR Backtesting results stored in PostgreSQL successfully!\n")

if __name__ == "__main__":
    backtester = VaRBacktestingEngine()
    backtester.run_backtest()