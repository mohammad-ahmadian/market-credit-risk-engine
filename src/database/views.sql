-- ====================================================================
-- SQL REPORTING VIEWS FOR POWER BI DASHBOARD SUITE
-- ====================================================================

-- View 1: Daily Market Overview (Prices, Log Returns, Percentage Returns)
CREATE OR REPLACE VIEW vw_daily_market_overview AS
SELECT 
    d.price_id,
    a.asset_id,
    a.ticker,
    a.asset_name,
    a.asset_class,
    a.currency,
    d.price_date,
    d.close_price,
    d.adj_close,
    d.log_return,
    ROUND((d.log_return * 100)::numeric, 4) AS return_pct
FROM daily_market_data d
JOIN asset_metadata a ON d.asset_id = a.asset_id;

-- View 2: Comprehensive Risk & Volatility Summary
CREATE OR REPLACE VIEW vw_portfolio_risk_summary AS
SELECT 
    r.metric_id,
    a.asset_id,
    a.ticker,
    a.asset_name,
    a.asset_class,
    r.calc_date,
    r.confidence_level,
    r.parametric_var,
    r.historical_var,
    r.expected_shortfall,
    ROUND((r.parametric_var * 100)::numeric, 2) AS parametric_var_pct,
    ROUND((r.historical_var * 100)::numeric, 2) AS historical_var_pct,
    ROUND((r.expected_shortfall * 100)::numeric, 2) AS expected_shortfall_pct,
    ROUND((g.annualized_volatility * 100)::numeric, 2) AS garch_ann_vol_pct,
    ROUND((g.garch_var_99 * 100)::numeric, 2) AS garch_var_99_pct
FROM portfolio_risk_metrics r
JOIN asset_metadata a ON r.asset_id = a.asset_id
LEFT JOIN garch_volatility_forecasts g ON r.asset_id = g.asset_id AND r.calc_date = g.forecast_date;

-- View 3: Portfolio Stress Testing Reporting
CREATE OR REPLACE VIEW vw_stress_test_reporting AS
SELECT 
    stress_id,
    scenario_name,
    calc_date,
    portfolio_value,
    stressed_portfolio_value,
    dollar_loss,
    percentage_loss,
    ROUND(percentage_loss::numeric, 2) AS loss_pct_formatted
FROM stress_test_results;

-- View 4: ALM & Interest Rate Risk Sensitivity
CREATE OR REPLACE VIEW vw_alm_rate_risk_reporting AS
SELECT 
    alm_id,
    calc_date,
    rate_shock_bps,
    base_eve_eur,
    stressed_eve_eur,
    eve_change_eur,
    eve_change_pct,
    nii_impact_eur,
    CASE 
        WHEN rate_shock_bps > 0 THEN '+' || rate_shock_bps || ' bps Rate Shock'
        ELSE rate_shock_bps || ' bps Rate Shock'
    END AS shock_label
FROM alm_interest_rate_risk;

-- View 5: Basel III VaR Model Backtesting (Filters for Latest Run Only)
CREATE OR REPLACE VIEW vw_backtest_basel_summary AS
SELECT 
    b.backtest_id,
    a.ticker,
    a.asset_name,
    b.confidence_level,
    b.total_days,
    b.expected_exceptions,
    b.actual_exceptions,
    ROUND((b.exception_rate * 100)::numeric, 2) AS exception_rate_pct,
    b.basel_zone,
    b.calc_date
FROM var_backtest_results b
JOIN asset_metadata a ON b.asset_id = a.asset_id
WHERE b.calc_date = (SELECT MAX(calc_date) FROM var_backtest_results);