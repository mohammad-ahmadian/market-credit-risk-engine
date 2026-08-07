import sys
import os

# Ensure root folder is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import numpy as np
import pandas as pd
from arch import arch_model
from scipy.stats import norm
from sqlalchemy import text
from src.database.db_connection import get_db_engine

class GarchVolatilityEngine:
    """
    Fits GARCH(1,1) models to daily returns, forecasts 1-day conditional volatility,
    calculates Dynamic Conditional VaR, and stores parameters in PostgreSQL.
    """

    def __init__(self):
        self.engine = get_db_engine()

    def fetch_asset_returns(self):
        """Fetches daily log returns grouped by asset."""
        query = """
            SELECT d.asset_id, a.ticker, d.price_date, d.log_return
            FROM daily_market_data d
            JOIN asset_metadata a ON d.asset_id = a.asset_id
            WHERE d.log_return IS NOT NULL
            ORDER BY a.ticker, d.price_date ASC;
        """
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df

    def fit_garch_models(self):
        """Fits GARCH(1,1) to each asset and uploads parameters/forecasts to DB."""
        df_returns = self.fetch_asset_returns()
        garch_results = []

        print("⚡ Fitting GARCH(1,1) Volatility Models...")

        for (asset_id, ticker), group in df_returns.groupby(['asset_id', 'ticker']):
            returns = group['log_return'].dropna().values
            latest_date = group['price_date'].max()

            if len(returns) < 500:
                print(f"⚠️ Skipping {ticker}: Insufficient historical data.")
                continue

            # Scale returns by 100 for stable GARCH optimization convergence
            scaled_returns = returns * 100.0

            try:
                # Fit GARCH(1,1) with Constant Mean & Normal Distribution
                model = arch_model(scaled_returns, vol='Garch', p=1, q=1, dist='Normal', rescale=False)
                res = model.fit(disp='off')

                # Extract Parameters
                omega = res.params.get('omega', 0.0) / 10000.0  # Rescale back
                alpha = res.params.get('alpha[1]', 0.0)
                beta = res.params.get('beta[1]', 0.0)
                persistence = alpha + beta

                # Forecast 1-day-ahead Conditional Variance
                forecast = res.forecast(horizon=1)
                cond_var = forecast.variance.iloc[-1, 0] / 10000.0  # Rescale back
                cond_vol_daily = np.sqrt(cond_var)
                annualized_vol = cond_vol_daily * np.sqrt(252)

                # Dynamic GARCH VaR (95% and 99%)
                mean_return = np.mean(returns)
                garch_var_95 = -(mean_return + norm.ppf(0.05) * cond_vol_daily)
                garch_var_99 = -(mean_return + norm.ppf(0.01) * cond_vol_daily)

                garch_results.append({
                    "asset_id": int(asset_id),
                    "forecast_date": latest_date,
                    "omega": float(omega),
                    "alpha": float(alpha),
                    "beta": float(beta),
                    "persistence": float(persistence),
                    "annualized_volatility": float(annualized_vol),
                    "garch_var_95": float(max(0.0, garch_var_95)),
                    "garch_var_99": float(max(0.0, garch_var_99))
                })

                print(f"✅ GARCH(1,1) Fitted for {ticker:7s} | Persistence (α+β): {persistence:.4f} | Ann. Vol: {annualized_vol*100:.2f}%")

            except Exception as e:
                print(f"❌ Error fitting GARCH for {ticker}: {e}")

        # Store GARCH results in PostgreSQL
        if garch_results:
            df_garch = pd.DataFrame(garch_results)
            with self.engine.begin() as conn:
                df_garch.to_sql("temp_garch", conn, if_exists="replace", index=False)
                upsert_query = text("""
                    INSERT INTO garch_volatility_forecasts (asset_id, forecast_date, omega, alpha, beta, persistence, annualized_volatility, garch_var_95, garch_var_99)
                    SELECT asset_id, forecast_date, omega, alpha, beta, persistence, annualized_volatility, garch_var_95, garch_var_99
                    FROM temp_garch
                    ON CONFLICT (asset_id, forecast_date) DO UPDATE
                    SET omega = EXCLUDED.omega,
                        alpha = EXCLUDED.alpha,
                        beta = EXCLUDED.beta,
                        persistence = EXCLUDED.persistence,
                        annualized_volatility = EXCLUDED.annualized_volatility,
                        garch_var_95 = EXCLUDED.garch_var_95,
                        garch_var_99 = EXCLUDED.garch_var_99;

                    DROP TABLE temp_garch;
                """)
                conn.execute(upsert_query)
            print("🎉 GARCH Volatility Forecasts stored in PostgreSQL!")

if __name__ == "__main__":
    garch_engine = GarchVolatilityEngine()
    garch_engine.fit_garch_models()