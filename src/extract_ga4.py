"""Extract a slim copy of the real GA4 sample events (PUBLIC DATA) for the attribution analysis.

Source: Google's public BigQuery dataset `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
(Google Merchandise Store, 1 Nov 2020 - 31 Jan 2021, obfuscated). Without a Google Cloud account we read
a flattened CSV export of that same table published on Hugging Face (gizdevans/ga4-bq-flattened-data,
MIT licence, one row per event, event_params unnested). DuckDB streams the file over HTTPS and keeps
only the columns and events we need, so the 1.8 GB file is never stored.
With BigQuery access, sql/bigquery/ga4_session_channels.sql builds the same table from the official source.

    python src/extract_ga4.py
Output: data/raw/ga4/ga4_events_slim.parquet (not committed; aggregates are written by sql/)
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
URL = "https://huggingface.co/datasets/gizdevans/ga4-bq-flattened-data/resolve/main/full_flatten_data.csv"
OUT = ROOT / "data" / "raw" / "ga4" / "ga4_events_slim.parquet"

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute(f"""
COPY (
  SELECT event_date, event_name, CAST(event_timestamp AS BIGINT) AS event_timestamp,
         user_pseudo_id, ga_session_id, TRY_CAST(ga_session_number AS INTEGER) AS ga_session_number,
         ep_source, ep_medium, ep_campaign, traffic_source, traffic_medium, traffic_campaign,
         country, device_category, TRY_CAST(ecom_revenue_usd AS DOUBLE) AS ecom_revenue_usd, ecom_transaction_id
  FROM read_csv('{URL}', header = true, all_varchar = true, parallel = false)
  WHERE event_name IN ('session_start', 'first_visit', 'page_view', 'add_to_cart', 'begin_checkout', 'purchase')
) TO '{OUT.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
""")
print(con.sql(f"SELECT event_name, count(*) n FROM '{OUT.as_posix()}' GROUP BY 1 ORDER BY 2 DESC"))
