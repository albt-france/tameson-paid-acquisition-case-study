-- =====================================================================
-- 03 · Channel and campaign economics: ROAS vs POAS            SIMULATED
-- ROAS = revenue / ad spend. POAS = gross profit / ad spend, where gross
-- profit = product margin - net shipping cost - payment & marketplace fees.
-- "Attributed" = what an ad platform reports: last click.
-- =====================================================================

-- Spend per campaign = channel spend x the campaign's share of the channel budget.
CREATE OR REPLACE TABLE campaign_spend AS
SELECT s.channel, c.category, SUM(s.spend_eur * c.share) AS spend_eur
FROM spend_weekly s
JOIN campaign_split c ON c.channel = s.channel
GROUP BY s.channel, c.category;


-- output: campaign_economics
WITH attributed AS (
    SELECT last_click AS channel, category,
           COUNT(*)                                   AS orders,
           SUM(CASE WHEN is_new_customer THEN 1 END)  AS new_customers,
           SUM(revenue_eur)                           AS revenue_eur,
           SUM(gross_profit_eur)                      AS gross_profit_eur
    FROM orders
    GROUP BY last_click, category
)
SELECT
    cs.channel,
    cs.category,
    cs.spend_eur,
    a.orders,
    a.new_customers,
    a.revenue_eur,
    a.gross_profit_eur,
    a.revenue_eur      / cs.spend_eur                 AS roas,
    a.gross_profit_eur / cs.spend_eur                 AS poas,
    a.gross_profit_eur / a.revenue_eur                AS net_margin,
    a.revenue_eur      / a.gross_profit_eur           AS breakeven_roas    -- ROAS needed for POAS = 1
FROM campaign_spend cs
JOIN attributed a ON a.channel = cs.channel AND a.category = cs.category
ORDER BY cs.channel, cs.category;


-- output: channel_country_economics
WITH sp AS (
    SELECT channel, country, SUM(spend_eur) AS spend_eur
    FROM spend_weekly GROUP BY channel, country
),
att AS (
    SELECT last_click AS channel, country,
           COUNT(*)                                   AS orders,
           SUM(CASE WHEN is_new_customer THEN 1 END)  AS new_customers,
           SUM(revenue_eur)                           AS revenue_eur,
           SUM(gross_profit_eur)                      AS gross_profit_eur
    FROM orders GROUP BY last_click, country
)
SELECT
    sp.channel, sp.country, sp.spend_eur,
    att.orders, att.new_customers, att.revenue_eur, att.gross_profit_eur,
    att.revenue_eur / sp.spend_eur           AS roas,
    att.gross_profit_eur / sp.spend_eur      AS poas,
    sp.spend_eur / att.new_customers         AS cac_eur          -- cost per new customer (last click)
FROM sp JOIN att ON att.channel = sp.channel AND att.country = sp.country
ORDER BY sp.channel, sp.country;


-- output: country_economics
SELECT
    country,
    COUNT(*)                                       AS orders,
    SUM(revenue_eur)                               AS revenue_eur,
    SUM(gross_profit_eur)                          AS gross_profit_eur,
    SUM(gross_profit_eur) / SUM(revenue_eur)       AS net_margin,
    AVG(revenue_eur)                               AS aov_eur,
    SUM(shipping_net_eur) / COUNT(*)               AS shipping_net_per_order
FROM orders
GROUP BY country
ORDER BY revenue_eur DESC;


-- output: monthly_kpis
-- Monthly totals per channel for the dashboard (spend, attributed revenue and profit, new customers).
WITH sp AS (
    SELECT date_trunc('month', week) AS month, channel, SUM(spend_eur) AS spend_eur
    FROM spend_weekly GROUP BY 1, 2
),
att AS (
    SELECT date_trunc('month', order_date) AS month, last_click AS channel,
           SUM(revenue_eur) AS revenue_eur, SUM(gross_profit_eur) AS gross_profit_eur,
           SUM(CASE WHEN is_new_customer THEN 1 END) AS new_customers
    FROM orders GROUP BY 1, 2
)
SELECT sp.month, sp.channel, sp.spend_eur, att.revenue_eur, att.gross_profit_eur, att.new_customers
FROM sp LEFT JOIN att ON att.month = sp.month AND att.channel = sp.channel
ORDER BY sp.month, sp.channel;
