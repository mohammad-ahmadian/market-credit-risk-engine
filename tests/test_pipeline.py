import sys
import os

# Force Python to add the root project directory to its path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import pytest
import numpy as np
import pandas as pd
from sqlalchemy import text
from src.database.db_connection import get_db_engine
from src.models.risk_engine import RiskAnalyticsEngine

def test_database_connection():
    """Test 1: Verify PostgreSQL database connection works."""
    engine = get_db_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1;")).scalar()
    assert result == 1, "Database connection test failed."

def test_market_data_non_empty():
    """Test 2: Verify market data table contains populated records."""
    engine = get_db_engine()
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM daily_market_data;")).scalar()
    assert count > 1000, "Daily market data table has insufficient records."

def test_parametric_var_non_negative():
    """Test 3: Verify Parametric VaR calculation yields a non-negative number."""
    returns = np.random.normal(0.0005, 0.015, 500)  # Simulated returns
    var_95 = RiskAnalyticsEngine.calculate_parametric_var(returns, confidence_level=0.95)
    assert var_95 >= 0.0, "Parametric VaR must be a non-negative loss value."

def test_historical_var_non_negative():
    """Test 4: Verify Historical VaR calculation yields a non-negative number."""
    returns = np.random.normal(0.0005, 0.015, 500)
    hvar_99 = RiskAnalyticsEngine.calculate_historical_var(returns, confidence_level=0.99)
    assert hvar_99 >= 0.0, "Historical VaR must be a non-negative loss value."

def test_expected_shortfall_greater_than_var():
    """Test 5: Verify Expected Shortfall is greater than or equal to VaR."""
    returns = np.random.normal(0.0, 0.02, 1000)
    var_99 = RiskAnalyticsEngine.calculate_historical_var(returns, confidence_level=0.99)
    es_99 = RiskAnalyticsEngine.calculate_expected_shortfall(returns, confidence_level=0.99)
    assert es_99 >= var_99, "Expected Shortfall must be greater than or equal to VaR."