-- =====================================================================
-- 02 · GA4 user journeys for the Markov attribution        PUBLIC DATA
-- One path per user: the channels of their sessions in time order, up to
-- and including the first purchase. Users who never bought give a
-- non-converting path. Consecutive repeats ("Direct > Direct") are
-- collapsed: they say nothing new about which channel played a role.
-- =====================================================================

CREATE OR REPLACE TABLE ga4_user_paths AS
WITH first_buy AS (
    SELECT user_pseudo_id, MIN(session_ts) AS buy_ts
    FROM ga4_sessions
    WHERE has_purchase = 1
    GROUP BY user_pseudo_id
),
steps AS (
    SELECT
        s.user_pseudo_id,
        s.session_ts,
        s.channel,
        f.buy_ts,
        LAG(s.channel) OVER (PARTITION BY s.user_pseudo_id ORDER BY s.session_ts) AS previous_channel
    FROM ga4_sessions s
    LEFT JOIN first_buy f ON f.user_pseudo_id = s.user_pseudo_id
    WHERE f.buy_ts IS NULL OR s.session_ts <= f.buy_ts
)
SELECT
    user_pseudo_id,
    STRING_AGG(CASE WHEN previous_channel IS NULL OR channel <> previous_channel THEN channel END, ' > '
               ORDER BY session_ts)                                   AS path,
    COUNT(*)                                                          AS sessions,
    MAX(CASE WHEN buy_ts IS NOT NULL THEN 1 ELSE 0 END)               AS converted,
    -- last click = channel of the purchase session
    MAX(CASE WHEN session_ts = buy_ts THEN channel END)               AS last_click_channel
FROM steps
GROUP BY user_pseudo_id;


-- output: markov_paths
-- (fully ordered, so the bootstrap in the notebook draws the same sample every run)
SELECT
    path,
    SUM(converted)              AS conversions,
    SUM(1 - converted)          AS non_conversions
FROM ga4_user_paths
GROUP BY path
ORDER BY conversions DESC, non_conversions DESC, path;


-- output: ga4_last_click
SELECT last_click_channel AS channel, COUNT(*) AS conversions
FROM ga4_user_paths
WHERE converted = 1
GROUP BY last_click_channel
ORDER BY conversions DESC, channel;


-- output: ga4_path_length
SELECT
    LEAST(sessions, 6)          AS sessions_until_purchase,   -- 6 = 6 or more
    COUNT(*)                    AS buyers
FROM ga4_user_paths
WHERE converted = 1
GROUP BY 1
ORDER BY 1;
