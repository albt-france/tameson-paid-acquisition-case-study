-- =====================================================================
-- BigQuery version of sql/01 + sql/02 on the official public table.
-- Runs in the free BigQuery sandbox. Dataset:
-- bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*
-- Output = the same markov_paths table the notebook reads.
-- =====================================================================
WITH events AS (
    SELECT
        user_pseudo_id,
        (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
        (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source')        AS ep_source,
        (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium')        AS ep_medium,
        event_name,
        event_timestamp
    FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
    WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
),
tagged AS (
    SELECT user_pseudo_id, ga_session_id, event_timestamp,
        CASE
            WHEN ep_medium = 'cpc'                                   THEN 'Paid Search'
            WHEN ep_medium = 'organic'                               THEN 'Organic Search'
            WHEN ep_medium = 'affiliate'                             THEN 'Affiliates'
            WHEN ep_medium = 'referral'
                 AND ep_source NOT LIKE '%googlemerchandisestore.com' THEN 'Referral'
            WHEN ep_medium = '(none)'                                THEN 'Direct'
            WHEN ep_medium IN ('<Other>', '(data deleted)')          THEN 'Unknown (obfuscated)'
        END AS channel
    FROM events
    WHERE event_name = 'page_view' AND ep_medium IS NOT NULL
),
touch AS (
    SELECT user_pseudo_id, ga_session_id, channel
    FROM tagged
    WHERE channel IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY user_pseudo_id, ga_session_id ORDER BY event_timestamp) = 1
),
sessions AS (
    SELECT e.user_pseudo_id, e.ga_session_id,
           MIN(e.event_timestamp)                      AS session_ts,
           COALESCE(ANY_VALUE(t.channel), 'Direct')    AS channel,
           MAX(IF(e.event_name = 'purchase', 1, 0))    AS has_purchase
    FROM events e
    LEFT JOIN touch t USING (user_pseudo_id, ga_session_id)
    WHERE e.ga_session_id IS NOT NULL
    GROUP BY 1, 2
),
first_buy AS (
    SELECT user_pseudo_id, MIN(session_ts) AS buy_ts FROM sessions WHERE has_purchase = 1 GROUP BY 1
),
steps AS (
    SELECT s.user_pseudo_id, s.session_ts, s.channel, f.buy_ts,
           LAG(s.channel) OVER (PARTITION BY s.user_pseudo_id ORDER BY s.session_ts) AS previous_channel
    FROM sessions s
    LEFT JOIN first_buy f USING (user_pseudo_id)
    WHERE f.buy_ts IS NULL OR s.session_ts <= f.buy_ts
),
paths AS (
    SELECT user_pseudo_id,
           STRING_AGG(IF(previous_channel IS NULL OR channel <> previous_channel, channel, NULL), ' > '
                      ORDER BY session_ts)             AS path,
           MAX(IF(buy_ts IS NOT NULL, 1, 0))           AS converted
    FROM steps
    GROUP BY 1
)
SELECT path, SUM(converted) AS conversions, SUM(1 - converted) AS non_conversions
FROM paths
GROUP BY path
ORDER BY conversions DESC, non_conversions DESC, path;
