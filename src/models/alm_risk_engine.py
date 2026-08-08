import sys
import os

# Ensure root folder is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pandas as pd
from datetime import datetime
from sqlalchemy import text
from src.database.db_connection import get_db_engine

class ALMRiskEngine:
    """
    Asset Liability Management (ALM) Engine computing IRRBB metrics:
    - Economic Value of Equity (EVE) Sensitivity under +/- 200 bps yield curve shifts
    - Net Interest Income (NII) 1-year earnings impact
    """

    def __init__(self, base_eve_eur=50_000_000, portfolio_duration_years=4.5, repricing_gap_eur=15_000_000):
        self.engine = get_db_engine()
        self.base_eve = base_eve_eur
        self.modified_duration = portfolio_duration_years / (1.0 + 0.035)  # Modified duration at 3.5% yield
        self.repricing_gap = repricing_gap_eur  # Asset-sensitive gap

    def run_interest_rate_shocks(self, shocks_bps=[+200, -200]):
        """Calculates EVE & NII changes under parallel interest rate shocks."""
        results = []
        latest_date = datetime.now().strftime('%Y-%m-%d')

        print(f"\n🏛️ Running ALM Interest Rate Sensitivity Analysis (Base EVE: EUR {self.base_eve:,.2f})...")

        for shock in shocks_bps:
            delta_y = shock / 10000.0  # Convert bps to decimal (e.g. +200 bps = 0.02)

            # 1. Calculate EVE Change
            eve_change_pct = -self.modified_duration * delta_y
            eve_change_eur = self.base_eve * eve_change_pct
            stressed_eve = self.base_eve + eve_change_eur

            # 2. Calculate NII Change (Earnings Impact)
            nii_impact_eur = self.repricing_gap * delta_y

            results.append({
                "calc_date": latest_date,
                "rate_shock_bps": int(shock),
                "base_eve_eur": self.base_eve,
                "stressed_eve_eur": stressed_eve,
                "eve_change_eur": eve_change_eur,
                "eve_change_pct": eve_change_pct * 100.0,
                "nii_impact_eur": nii_impact_eur
            })

            print(f"📊 Shock: {shock:+4d} bps | ΔEVE: EUR {eve_change_eur:12,.2f} ({eve_change_pct*100:6.2f}%) | ΔNII: EUR {nii_impact_eur:10,.2f}")

        # Store ALM Results in PostgreSQL
        if results:
            df_alm = pd.DataFrame(results)
            df_alm['calc_date'] = pd.to_datetime(df_alm['calc_date']).dt.date

            with self.engine.begin() as conn:
                df_alm.to_sql("temp_alm", conn, if_exists="replace", index=False)
                
                upsert_query = text("""
                    INSERT INTO alm_interest_rate_risk (calc_date, rate_shock_bps, base_eve_eur, stressed_eve_eur, eve_change_eur, eve_change_pct, nii_impact_eur)
                    SELECT calc_date::DATE, rate_shock_bps, base_eve_eur, stressed_eve_eur, eve_change_eur, eve_change_pct, nii_impact_eur
                    FROM temp_alm
                    ON CONFLICT (calc_date, rate_shock_bps) DO UPDATE
                    SET base_eve_eur = EXCLUDED.base_eve_eur,
                        stressed_eve_eur = EXCLUDED.stressed_eve_eur,
                        eve_change_eur = EXCLUDED.eve_change_eur,
                        eve_change_pct = EXCLUDED.eve_change_pct,
                        nii_impact_eur = EXCLUDED.nii_impact_eur;

                    DROP TABLE temp_alm;
                """)
                conn.execute(upsert_query)
            print("🎉 ALM Interest Rate Risk metrics stored in PostgreSQL successfully!\n")

if __name__ == "__main__":
    alm_engine = ALMRiskEngine()
    alm_engine.run_interest_rate_shocks()