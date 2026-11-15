-- =====================================================================
-- 04 · Customer value (LTV) by cohort, segment and channel     SIMULATED
-- LTV is measured in gross profit, not revenue. To avoid the censoring bias
-- (recent customers have had less time to come back), an h-month LTV only
-- uses customers acquired at least h months before the end of the data.
-- =====================================================================

CREATE OR REPLACE TABLE customer_orders AS
WITH firsts AS (
    SELECT customer_id, MIN(order_date) AS first_date
    FROM orders GROUP BY customer_id
)
SELECT
    o.customer_id, o.order_date, o.gross_profit_eur, o.revenue_eur,
    f.first_date,
    date_diff('day', f.first_date, o.order_date) AS days_since_first
FROM orders o
JOIN firsts f USING (customer_id);


-- output: cohort_ltv
WITH horizons AS (
    SELECT * FROM (VALUES (1), (3), (6), (12), (18)) AS h(months)
),
data_end AS (SELECT MAX(order_date) AS end_date FROM orders),
eligible AS (   -- customers observed for the full horizon
    SELECT c.customer_id, c.segment, c.acquisition_channel, c.country, h.months, f.first_date
    FROM customers c
    JOIN (SELECT customer_id, MIN(first_date) AS first_date FROM customer_orders GROUP BY 1) f USING (customer_id)
    CROSS JOIN horizons h
    CROSS JOIN data_end d
    WHERE f.first_date <= d.end_date - h.months * INTERVAL 30 DAY
),
value AS (
    SELECT e.customer_id, e.segment, e.acquisition_channel, e.months,
           SUM(o.gross_profit_eur) AS gp, SUM(o.revenue_eur) AS revenue, COUNT(*) AS orders
    FROM eligible e
    JOIN customer_orders o
      ON o.customer_id = e.customer_id AND o.days_since_first < e.months * 30
    GROUP BY e.customer_id, e.segment, e.acquisition_channel, e.months
)
SELECT segment, acquisition_channel, months,
       COUNT(*)        AS customers,
       AVG(gp)         AS gp_ltv_eur,
       AVG(revenue)    AS revenue_ltv_eur,
       AVG(orders)     AS orders_per_customer
FROM value
GROUP BY GROUPING SETS ((segment, acquisition_channel, months), (segment, months), (acquisition_channel, months), (months))
ORDER BY months, segment, acquisition_channel;


-- output: cohort_curve
-- Cumulative gross profit per customer by month of acquisition (classic cohort triangle).
WITH m AS (
    SELECT date_trunc('month', first_date) AS cohort,
           CAST(FLOOR(days_since_first / 30) AS INTEGER) AS month_n,
           SUM(gross_profit_eur) AS gp
    FROM customer_orders GROUP BY 1, 2
),
size AS (
    SELECT date_trunc('month', MIN(order_date)) AS cohort, customer_id
    FROM customer_orders GROUP BY customer_id
)
SELECT m.cohort, m.month_n,
       SUM(m.gp) OVER (PARTITION BY m.cohort ORDER BY m.month_n) / s.n AS cum_gp_per_customer,
       s.n AS cohort_customers
FROM m
JOIN (SELECT cohort, COUNT(*) AS n FROM size GROUP BY cohort) s USING (cohort)
ORDER BY m.cohort, m.month_n;


-- output: customer_value
-- One row per customer acquired early enough to observe 12 months: what we knew at the first
-- order (segment, country, category, value) and the 12-month gross profit that followed.
WITH firsts AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS rn
    FROM orders
),
first_order AS (SELECT * FROM firsts WHERE rn = 1),
data_end AS (SELECT MAX(order_date) AS end_date FROM orders)
SELECT
    f.customer_id, f.order_date AS first_date, f.segment, f.country, f.category AS first_category,
    c.acquisition_channel,
    f.revenue_eur AS first_revenue_eur, f.gross_profit_eur AS first_gp_eur,
    SUM(o.gross_profit_eur) AS gp_12m_eur,
    COUNT(*) AS orders_12m
FROM first_order f
JOIN customers c USING (customer_id)
JOIN customer_orders o ON o.customer_id = f.customer_id AND o.days_since_first < 360
CROSS JOIN data_end d
WHERE f.order_date <= d.end_date - INTERVAL 360 DAY
GROUP BY ALL
ORDER BY f.customer_id;
