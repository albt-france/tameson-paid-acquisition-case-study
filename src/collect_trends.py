"""Google Trends: real search-interest data for Tameson's categories and countries (PUBLIC DATA).

We use Google Trends *topics* (language-independent entities) rather than English keywords, so that
'Magnetventil' (DE), 'magneetventiel' (NL) and 'électrovanne' (FR) all count towards 'Solenoid valve'.
Trends values are indexes (0-100), not search volumes:
- interest_by_region: share of all searches in a country that go to the topic, scaled so the top country = 100;
- interest_over_time per country: weekly index, comparable between topics *within* one country.
We use them for (1) seasonality, (2) the week-to-week noise that drives the power of a geo test,
(3) relative demand per country. Low request rate (>= 10 s apart), no login.

    python src/collect_trends.py
Outputs: data/public/trends_by_country.csv, data/public/trends_weekly.csv
"""
import time
from datetime import date
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "data" / "public"
PUB.mkdir(parents=True, exist_ok=True)
TODAY = date.today().isoformat()
TIMEFRAME = "today 5-y"
# Topic ids found with pytrends.suggestions() (type 'Topic')
TOPICS = {"/m/06hsj2": "Solenoid valve", "/m/02wv_k": "Ball valve", "/m/09kpsf": "Pneumatic cylinder",
          "/m/0gtlsq": "Pipe fitting", "/m/01bv6j": "Pneumatics"}
COUNTRIES = {"NL": "Netherlands", "BE": "Belgium", "DE": "Germany", "FR": "France", "GB": "United Kingdom",
             "ES": "Spain", "US": "United States", "IT": "Italy", "PL": "Poland", "AT": "Austria"}
STORE_COUNTRIES = ["NL", "BE", "DE", "FR", "GB", "ES"]

py = TrendReq(hl="en-US", tz=0, timeout=(10, 30))


def call(fn, *a, tries=4, **k):
    for i in range(tries):
        try:
            out = fn(*a, **k)
            time.sleep(12)
            return out
        except Exception as e:  # 429 too many requests -> wait longer, no retry storm
            print("retry after error:", e)
            time.sleep(60 * (i + 1))
    raise RuntimeError("Google Trends unavailable")


def by_country() -> pd.DataFrame:
    rows = []
    for mid, name in TOPICS.items():
        call(py.build_payload, [mid], timeframe=TIMEFRAME, geo="")
        df = call(py.interest_by_region, resolution="COUNTRY", inc_low_vol=True, inc_geo_code=True)
        df = df[df["geoCode"].isin(COUNTRIES)].rename(columns={mid: "index"})
        for geo, r in df.iterrows():
            rows.append({"topic": name, "topic_id": mid, "country_code": r["geoCode"], "country": geo,
                         "interest_index": int(r["index"]), "timeframe": TIMEFRAME, "collected": TODAY})
    return pd.DataFrame(rows)


def weekly() -> pd.DataFrame:
    out = []
    for geo in STORE_COUNTRIES:
        call(py.build_payload, list(TOPICS), timeframe=TIMEFRAME, geo=geo)
        df = call(py.interest_over_time)
        df = df.drop(columns=[c for c in ["isPartial"] if c in df]).rename(columns=TOPICS)
        df = df.reset_index().melt(id_vars="date", var_name="topic", value_name="interest_index")
        df["country_code"] = geo
        out.append(df)
    w = pd.concat(out)
    w["collected"] = TODAY
    return w


if __name__ == "__main__":
    bc = by_country(); bc.to_csv(PUB / "trends_by_country.csv", index=False)
    print(bc.pivot(index="country_code", columns="topic", values="interest_index"))
    w = weekly(); w.to_csv(PUB / "trends_weekly.csv", index=False)
    print(w.groupby(["country_code", "topic"])["interest_index"].agg(["mean", "std"]).round(1))
