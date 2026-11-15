-- =====================================================================
-- 05 · Weekly country panel for the media-mix model and the geo test
--                                                              SIMULATED
-- One row per country and week: spend per channel (pivoted with
-- conditional sums, valid in DuckDB and BigQuery) and the business result.
-- =====================================================================

-- output: weekly_panel
WITH sp AS (
    SELECT week, country,
        SUM(CASE WHEN channel = 'Google Search'   THEN spend_eur ELSE 0 END) AS spend_search,
        SUM(CASE WHEN channel = 'Google Shopping' THEN spend_eur ELSE 0 END) AS spend_shopping,
        SUM(CASE WHEN channel = 'Microsoft Ads'   THEN spend_eur ELSE 0 END) AS spend_microsoft,
        SUM(CASE WHEN channel = 'Meta'            THEN spend_eur ELSE 0 END) AS spend_meta,
        SUM(CASE WHEN channel = 'Marketplaces'    THEN spend_eur ELSE 0 END) AS spend_marketplaces
    FROM spend_weekly
    GROUP BY week, country
),
cap AS (   -- 99th percentile of order gross profit (BigQuery: APPROX_QUANTILES(gross_profit_eur, 100)[OFFSET(99)])
    SELECT QUANTILE_CONT(gross_profit_eur, 0.99) AS p99 FROM orders
),
res AS (
    SELECT week, country,
           COUNT(*)               AS orders,
           SUM(revenue_eur)       AS revenue_eur,
           SUM(gross_profit_eur)  AS gross_profit_eur,
           -- model target: a few very large one-off B2B orders are capped at the 99th percentile,
           -- so that one 20k EUR order does not bend a weekly response curve
           SUM(LEAST(gross_profit_eur, (SELECT p99 FROM cap))) AS gross_profit_capped_eur,
           SUM(CASE WHEN is_new_customer THEN 1 ELSE 0 END) AS new_customers,
           SUM(CASE WHEN is_new_customer THEN gross_profit_eur ELSE 0 END) AS new_customer_gp_eur
    FROM orders
    GROUP BY week, country
)
SELECT sp.*, res.orders, res.revenue_eur, res.gross_profit_eur, res.gross_profit_capped_eur, res.new_customers, res.new_customer_gp_eur, se.season
FROM sp
JOIN res USING (week, country)
JOIN seasonality se ON se.week = sp.week AND se.country = sp.country
ORDER BY sp.country, sp.week;


-- output: geo_test_weekly
-- Geo holdout: Google Search switched off in FR, ES and GB for 16 weeks from 6 Apr 2026.
-- One row per country and week, 52 weeks before to 20 weeks after the start (the notebook
-- forms the test and control groups, so other designs can be compared on the same data).
-- Reads the weekly_panel built above (re-created here as a subquery for BigQuery portability).
-- Test metric: order gross profit winsorised at the 90th percentile (variance reduction: a few large B2B
-- orders would otherwise dominate the weekly noise and halve the power of the test).
WITH cap AS (SELECT QUANTILE_CONT(gross_profit_eur, 0.99) AS p99, QUANTILE_CONT(gross_profit_eur, 0.90) AS p90 FROM orders),
r AS (
    SELECT week, country,
           SUM(gross_profit_eur)                                AS gross_profit_eur,
           SUM(LEAST(gross_profit_eur, (SELECT p99 FROM cap)))  AS gross_profit_capped_eur,
           SUM(LEAST(gross_profit_eur, (SELECT p90 FROM cap)))  AS gross_profit_w90_eur,
           COUNT(*)                                             AS orders
    FROM orders GROUP BY week, country
),
sp AS (
    SELECT week, country,
           SUM(CASE WHEN channel = 'Google Search' THEN spend_eur ELSE 0 END) AS spend_search,
           SUM(CASE WHEN channel = 'Meta'          THEN spend_eur ELSE 0 END) AS spend_meta
    FROM spend_weekly GROUP BY week, country
)
SELECT
    r.week, r.country, r.gross_profit_eur, r.gross_profit_capped_eur, r.gross_profit_w90_eur, r.orders,
    sp.spend_search, sp.spend_meta
FROM r JOIN sp USING (week, country)
WHERE r.week BETWEEN DATE '2026-04-06' - INTERVAL 364 DAY AND DATE '2026-04-06' + INTERVAL 139 DAY
ORDER BY r.week, r.country;
