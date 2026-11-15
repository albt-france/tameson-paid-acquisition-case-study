"""Public catalog snapshot: category mix and list prices from Tameson's product sitemaps and product pages.

The storefront JSON endpoints are limited (collections return one product), so we use what any visitor sees:
1. all product sitemaps listed in /sitemap.xml (161) -> product handles (URLs);
2. handles are mapped to 9 analysis categories with keyword rules (share of the catalog per category);
3. a random sample of product pages per category -> the list price in the page's structured data (JSON-LD).
Very low rate (>= 10 s between requests), robots.txt respected, stop on rate limiting.

    python src/collect_catalog.py
Outputs: data/public/catalog_categories.csv, data/public/catalog_prices.csv
"""
import json
import re
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import polite

polite.MIN_DELAY_S = 10.0
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "public"
PUB = ROOT / "data" / "public"
TODAY = date.today().isoformat()
SAMPLE_PER_CAT = 30
RULES = [  # first match wins (order matters: 'pressure-switch' is measurement, other switches are electrical)
    ("Solenoid valves", r"solenoid-valve|magneetventiel"),
    ("Hydraulics", r"hydraulic|ng6|ng10|-d03-|-d05-|sandwich"),
    ("Pneumatics", r"pneumatic|cylinder|festo|frl|filter-regulator|5-2-way|3-2-way|silencer|muffler|push-in"),
    ("Hoses", r"hose(?!-clamp)|-tubing|-tube-"),
    ("Measurement & control", r"gauge|transducer|transmitter|sensor|thermometer|pressure-switch|flow-meter|level-switch|thermostat|wika|-meter"),
    ("Electrical & automation", r"circuit-breaker|breaker|relay|contactor|switch|socket|outlet|power-strip|cable|terminal|din-rail|eaton|hager|schneider|legrand|jung-|gira-|niko-|abb-|lamp|light|ballast|led-|door|comelit|enclosure|cabinet|earthing|switchgear|plug"),
    ("Fittings & couplings", r"fitting|coupling|nipple|elbow|-tee-|adapter|reducer|bushing|union|flange|hose-clamp"),
    ("Sealing, tools & MRO", r"o-ring|seal|gasket|tool|wrench|plier|screwdriver|drill|lubric|grease|spanner|hammer|knife"),
    ("Ball & process valves", r"valve|actuator|strainer"),
]

def get_or_stop(url):
    r = polite.get(url)
    if r is not None and r.status_code == 429 or (r is not None and "rate_limited" in r.text[:200]):
        print("rate limited, pausing 5 min:", url)
        time.sleep(300)
        r = polite.get(url)
        if r is None or r.status_code == 429:
            raise SystemExit("still rate limited: stopping politely")
    return r


def categorise(handle):
    for cat, pat in RULES:
        if re.search(pat, handle):
            return cat
    return "Other"


def main():
    idx = (RAW / "sitemap_com.xml").read_text(encoding="utf-8")
    maps = [u.replace("&amp;", "&") for u in re.findall(r"<loc>([^<]*sitemap_products_[^<]*)</loc>", idx)]
    pick = maps                                   # all of them: products are ordered by creation date
    handles = []
    for u in pick:
        r = get_or_stop(u)
        if r is None:
            continue
        hs = re.findall(r"<loc>https://tameson\.com/products/([^<]+)</loc>", r.text)
        handles += hs
        print(u.split("?")[0].rsplit("/", 1)[-1], len(hs))
    h = pd.DataFrame({"handle": sorted(set(handles))})
    h["category"] = h.handle.map(categorise)
    h.to_csv(RAW / "sitemap_handles_sample.csv", index=False)
    cats = (h.category.value_counts().rename_axis("category").reset_index(name="handles_in_sample"))
    cats["share_of_sample"] = cats.handles_in_sample / len(h)
    cats["sitemaps_sampled"], cats["sitemaps_total"], cats["collected"] = len(pick), len(maps), TODAY
    cats.to_csv(PUB / "catalog_categories.csv", index=False)
    print(cats)

    rng = np.random.default_rng(42)
    rows = []
    fx = pd.read_csv(PUB / "stores.csv").set_index("currency")["fx_rate_vs_eur"].to_dict()
    for cat in [c for c, _ in RULES]:
        pool = h[h.category == cat].handle.to_numpy()
        for handle in rng.choice(pool, size=min(SAMPLE_PER_CAT, len(pool)), replace=False):
            r = get_or_stop(f"https://tameson.com/products/{handle}")
            if r is None or r.status_code != 200:
                continue
            price = re.search(r'"price"\s*:\s*"?([\d.]+)"?', r.text)
            curr = re.search(r'"priceCurrency"\s*:\s*"(\w+)"', r.text)
            brand = re.search(r'"brand"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', r.text)
            if not price:
                continue
            # the first "price" on a Shopify product page is the product JSON, in minor units (cents)
            raw = price.group(1)
            p = float(raw) if "." in raw else float(raw) / 100
            cur = curr.group(1) if curr else "EUR"
            rows.append({"category": cat, "handle": handle, "price": p, "currency": cur,
                         "price_eur": round(p / fx.get(cur, 1.0), 2), "brand": brand.group(1) if brand else None,
                         "collected": TODAY})
        pd.DataFrame(rows).to_csv(PUB / "catalog_prices.csv", index=False)   # save as we go
        print(cat, sum(r["category"] == cat for r in rows))
    p = pd.DataFrame(rows)
    print(p.groupby("category").price_eur.describe(percentiles=[.25, .5, .75]).round(1))


if __name__ == "__main__":
    main()
