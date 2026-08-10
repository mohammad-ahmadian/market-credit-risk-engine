import time
import logging
from datetime import datetime

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

from src.data_ingestion import MarketDataIngestor
from src.models.risk_engine import RiskAnalyticsEngine
from src.models.garch_model import GarchVolatilityEngine
from src.models.stress_testing import StressTestingEngine
from src.models.alm_risk_engine import ALMRiskEngine
from src.models.backtesting_engine import VaRBacktestingEngine
from src.database.create_views import deploy_sql_views

def run_full_risk_pipeline():
    """
    Master Orchestrator Function: Executes the complete End-to-End Market & Credit Risk Pipeline.
    """
    start_time = time.time()
    logging.info("=================================================================")
    logging.info(" STARTING END-TO-END MARKET & CREDIT RISK ANALYTICS PIPELINE")
    logging.info("=================================================================")

    try:
        # Phase 1: Data Ingestion & Log Returns Calculation
        logging.info("STAGE 1/7: Fetching Market Data & Yield Curves...")
        ingestor = MarketDataIngestor()
        ingestor.fetch_and_load_market_data()
        ingestor.fetch_and_load_yield_curve()

        # Phase 2: Quantitative Risk Engine (VaR & Expected Shortfall)
        logging.info("STAGE 2/7: Computing Rolling Parametric, Historical VaR & ES...")
        risk_engine = RiskAnalyticsEngine()
        risk_engine.compute_rolling_risk_metrics(window=250, confidence_levels=[0.95, 0.99])

        # Phase 3: GARCH(1,1) Volatility Forecasting
        logging.info("STAGE 3/7: Fitting GARCH(1,1) Volatility Models...")
        garch_engine = GarchVolatilityEngine()
        garch_engine.fit_garch_models()

        # Phase 4: Portfolio Stress Testing Engine (Basel III)
        logging.info("STAGE 4/7: Running Portfolio Stress Test Scenarios...")
        stress_engine = StressTestingEngine(portfolio_value_eur=10_000_000)
        stress_engine.run_stress_tests()

        # Phase 5: Asset Liability Management (ALM) Interest Rate Sensitivity
        logging.info("STAGE 5/7: Executing ALM Interest Rate Shocks (EVE & NII)...")
        alm_engine = ALMRiskEngine()
        alm_engine.run_interest_rate_shocks()

        # Phase 6: Basel III VaR Model Backtesting
        logging.info("STAGE 6/7: Performing VaR Model Backtesting & Traffic Light Assignment...")
        backtester = VaRBacktestingEngine()
        backtester.run_backtest()

        # Phase 7: Deploy SQL Reporting Views for Power BI
        logging.info("STAGE 7/7: Deploying SQL Reporting Views...")
        deploy_sql_views()

        elapsed_time = time.time() - start_time
        logging.info("=================================================================")
        logging.info(f"🎉 PIPELINE COMPLETED SUCCESSFULLY IN {elapsed_time:.2f} SECONDS!")
        logging.info("=================================================================")

    except Exception as e:
        logging.error(f"❌ PIPELINE FAILED WITH ERROR: {e}", exc_info=True)
        raise e

if __name__ == "__main__":
    run_full_risk_pipeline()