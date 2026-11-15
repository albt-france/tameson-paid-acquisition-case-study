"""Run every query in sql/ with DuckDB and export the results to data/output/.

Views: ga4_events = real GA4 sample (data/raw/ga4/ga4_events_slim.parquet, built by src/extract_ga4.py);
every simulated table data/sim/<name>.parquet becomes a view called <name>.
Files run in name order. Inside a file, a statement ends with ';' at the end of a line.
A statement preceded by a comment line '-- output: <name>' is exported to data/output/<name>.csv.

    python src/run_sql.py            (all files)
    python src/run_sql.py 01 02      (only files starting with these prefixes)
"""
import re
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM, OUT, SQL = ROOT / "data" / "sim", ROOT / "data" / "output", ROOT / "sql"
GA4 = ROOT / "data" / "raw" / "ga4" / "ga4_events_slim.parquet"
OUT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()
if GA4.exists():
    con.execute(f"CREATE OR REPLACE VIEW ga4_events AS SELECT * FROM read_parquet('{GA4.as_posix()}')")
for f in sorted(SIM.glob("*.parquet")):
    con.execute(f"CREATE OR REPLACE VIEW {f.stem} AS SELECT * FROM read_parquet('{f.as_posix()}')")
for f in sorted(SIM.glob("*.csv")):
    con.execute(f"CREATE OR REPLACE VIEW {f.stem} AS SELECT * FROM read_csv_auto('{f.as_posix()}')")

prefixes = sys.argv[1:]
for sql_file in sorted(SQL.glob("*.sql")):
    if prefixes and not sql_file.name.startswith(tuple(prefixes)):
        continue
    if sql_file.name.startswith(("01", "02")) and not GA4.exists():
        print(f"skip {sql_file.name}: run src/extract_ga4.py first (outputs already in data/output)")
        continue
    t0 = time.time()
    text = sql_file.read_text(encoding="utf-8")
    for statement in re.split(r";\s*$", text, flags=re.MULTILINE):
        if not re.search(r"^\s*[A-Za-z(]", statement, flags=re.MULTILINE):
            continue                                  # only comments / blank
        match = re.search(r"--\s*output:\s*(\w+)", statement)
        if match:
            df = con.execute(statement).df()
            # 8 significant digits: parallel sums differ only around the 15th digit (reproducible outputs)
            for c in df.select_dtypes("float").columns:
                df[c] = df[c].map(lambda v: float(f"{v:.8g}") if pd.notna(v) else v)
            df.to_csv(OUT / f"{match.group(1)}.csv", index=False)
            print(f"  {sql_file.name:30s} -> {match.group(1)}.csv ({len(df):,} rows)")
        else:
            con.execute(statement)
    print(f"{sql_file.name} done in {time.time() - t0:.1f}s")
