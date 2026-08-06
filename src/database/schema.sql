-- 1. Create Metadata Table for Assets
CREATE TABLE IF NOT EXISTS asset_metadata (
    asset_id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) UNIQUE NOT NULL,
    asset_name VARCHAR(100) NOT NULL,
    asset_class VARCHAR(50) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create Daily Market Data Table
CREATE TABLE IF NOT EXISTS daily_market_data (
    price_id SERIAL PRIMARY KEY,
    asset_id INT REFERENCES asset_metadata(asset_id) ON DELETE CASCADE,
    price_date DATE NOT NULL,
    open_price NUMERIC(12, 4),
    high_price NUMERIC(12, 4),
    low_price NUMERIC(12, 4),
    close_price NUMERIC(12, 4),
    adj_close NUMERIC(12, 4) NOT NULL,
    volume BIGINT,
    log_return NUMERIC(10, 6),
    CONSTRAINT unique_asset_date UNIQUE (asset_id, price_date)
);

-- 3. Create Daily Yield Curve Table
CREATE TABLE IF NOT EXISTS daily_interest_rates (
    rate_id SERIAL PRIMARY KEY,
    rate_date DATE NOT NULL,
    tenor VARCHAR(10) NOT NULL,
    yield_pct NUMERIC(8, 4) NOT NULL,
    CONSTRAINT unique_tenor_date UNIQUE (tenor, rate_date)
);

-- 4. Create Performance Indexes (FIXED: rate_date used here)
CREATE INDEX IF NOT EXISTS idx_market_data_asset_date ON daily_market_data(asset_id, price_date);
CREATE INDEX IF NOT EXISTS idx_rates_tenor_date ON daily_interest_rates(tenor, rate_date);



-- Create Table for Calculated Portfolio & Asset Risk Metrics
CREATE TABLE IF NOT EXISTS portfolio_risk_metrics (
    metric_id SERIAL PRIMARY KEY,
    asset_id INT REFERENCES asset_metadata(asset_id) ON DELETE CASCADE,
    calc_date DATE NOT NULL,
    confidence_level NUMERIC(4, 2) NOT NULL, -- 0.95 or 0.99
    parametric_var NUMERIC(10, 6) NOT NULL,
    historical_var NUMERIC(10, 6) NOT NULL,
    expected_shortfall NUMERIC(10, 6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_asset_date_conf UNIQUE (asset_id, calc_date, confidence_level)
);

-- Performance Index for Risk Queries
CREATE INDEX IF NOT EXISTS idx_risk_metrics_asset_date ON portfolio_risk_metrics(asset_id, calc_date);