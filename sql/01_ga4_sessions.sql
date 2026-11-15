-- =====================================================================
-- 01 · GA4 sessions and their channel                       PUBLIC DATA
-- Source: Google's GA4 obfuscated sample (Google Merchandise Store,
-- Nov 2020 - Jan 2021). View ga4_events = data/raw/ga4/ga4_events_slim.parquet
-- (built by src/extract_ga4.py; sql/bigquery/ has the same logic on the
-- official nested table). Standard SQL that runs on DuckDB and BigQuery.
-- =====================================================================

-- One row per session with a known source. The channel of a session is the
-- source/medium of its first page_view that carries one. Self-referrals (the
-- shop's own domains) are internal navigation, not a channel: ignored.
CREATE OR REPLACE TABLE ga4_session_touch AS
WITH tagged AS (
    SELECT
        user_pseudo_id,
        ga_session_id,
        event_timestamp,
        CASE
            WHEN ep_medium = 'cpc'                                   THEN 'Paid Search'
            WHEN ep_medium = 'organic'                               THEN 'Organic Search'
            WHEN ep_medium = 'affiliate'                             THEN 'Affiliates'
            WHEN ep_medium = 'referral'
                 AND ep_source NOT LIKE '%googlemerchandisestore.com' THEN 'Referral'
            WHEN ep_medium = '(none)'                                THEN 'Direct'
            WHEN ep_medium IN ('<Other>', '(data deleted)')          THEN 'Unknown (obfuscated)'
        END AS channel
    FROM ga4_events
    WHERE event_name = 'page_view' AND ep_medium IS NOT NULL
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY user_pseudo_id, ga_session_id ORDER BY event_timestamp) AS rn
    FROM tagged
    WHERE channel IS NOT NULL
)
SELECT user_pseudo_id, ga_session_id, channel
FROM ranked
WHERE rn = 1;


-- One row per session (all sessions). No source at all = Direct.
CREATE OR REPLACE TABLE ga4_sessions AS
SELECT
    e.user_pseudo_id,
    e.ga_session_id,
    MIN(e.event_timestamp)                                         AS session_ts,
    MIN(e.event_date)                                              AS session_date,
    COALESCE(ANY_VALUE(t.channel), 'Direct')                       AS channel,
    MAX(CASE WHEN e.event_name = 'purchase' THEN 1 ELSE 0 END)     AS has_purchase,
    MAX(CASE WHEN e.event_name = 'add_to_cart' THEN 1 ELSE 0 END)  AS has_add_to_cart,
    SUM(COALESCE(e.ecom_revenue_usd, 0))                           AS revenue_usd,
    ANY_VALUE(e.country)                                           AS country,
    ANY_VALUE(e.device_category)                                   AS device
FROM ga4_events e
LEFT JOIN ga4_session_touch t
       ON t.user_pseudo_id = e.user_pseudo_id AND t.ga_session_id = e.ga_session_id
WHERE e.ga_session_id IS NOT NULL
GROUP BY e.user_pseudo_id, e.ga_session_id;


-- output: ga4_channel_summary
SELECT
    channel,
    COUNT(*)                                   AS sessions,
    COUNT(DISTINCT user_pseudo_id)             AS users,
    SUM(has_purchase)                          AS purchase_sessions,
    SUM(has_purchase) / COUNT(*)               AS session_conversion_rate,
    SUM(revenue_usd)                           AS revenue_usd
FROM ga4_sessions
GROUP BY channel
ORDER BY sessions DESC;


-- output: ga4_daily
-- Daily sessions and purchase sessions: the real baseline for A/B test sizing.
SELECT
    session_date,
    COUNT(*)                     AS sessions,
    SUM(has_add_to_cart)         AS add_to_cart_sessions,
    SUM(has_purchase)            AS purchase_sessions
FROM ga4_sessions
GROUP BY session_date
ORDER BY session_date;
