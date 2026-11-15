"""Collect the public facts about Tameson used in the report (run once; snapshot saved in data/raw/public).

Polite collection (src/polite.py): robots.txt checked, >= 2.5 s between requests, generic User-Agent,
no account, no cart, no checkout. Only public endpoints of the Shopify storefront are used:
- /meta.json and the homepage of each country domain (language, currency, market);
- /pages/... company pages (about, history, delivery, payment methods, review ratings);
- /collections/<handle>.json (number of products in a category) and
  /collections/<handle>/products.json (public list prices of the first 250-500 products of a category).

    python src/collect_public.py
Outputs: data/raw/public/* (raw snapshot) and data/public/stores.csv, catalog_categories.csv, catalog_prices.csv
"""
import json
import re
import html as htmllib
from datetime import date
from pathlib import Path

import pandas as pd

import polite

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "public"
PUB = ROOT / "data" / "public"
RAW.mkdir(parents=True, exist_ok=True)
PUB.mkdir(parents=True, exist_ok=True)
TODAY = date.today().isoformat()

DOMAINS = ["tameson.com", "tameson.co.uk", "tameson.nl", "tameson.de", "tameson.fr", "tameson.es", "tameson.be"]
PAGES = ["about-us", "history", "delivery", "payment-methods", "return-policy", "contact-us",
         "pimdata_shipping-rates", "pimdata_review-ratings", "pimdata_footer-company"]

# Analysis categories -> public collections of the Tameson menu (handles copied from the site navigation).
CATEGORIES = {
    "Solenoid valves": ["solenoid-valves"],
    "Ball & process valves": ["ball-valves", "butterfly-valves", "check-valves"],
    "Pneumatics": ["pneumatic-cylinders", "pneumatic-directional-valves", "pneumatics-air-treatment-filters-regulators-lubricators"],
    "Fittings & couplings": ["threaded-fittings", "push-in-fittings-299426", "couplings"],
    "Hoses": ["hydraulic-hoses", "water-and-liquid-hoses", "air-and-gas-hoses"],
    "Measurement & control": ["pressure-gauges", "pressure-measurement-and-control", "temperature-measurement-and-control"],
    "Hydraulics": ["hydraulic-valves", "hydraulic-pump", "hydraulic-fittings"],
    "Tools & maintenance": ["hand-tools", "air-tools", "lubricants"],
}


def text_of(page_html: str) -> str:
    body = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", page_html)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    return " ".join(htmllib.unescape(body).split())


def stores() -> pd.DataFrame:
    rows = []
    for d in DOMAINS:
        r = polite.get(f"https://{d}/")
        if r is None:
            continue
        (RAW / f"home_{d}.html").write_text(r.text, encoding="utf-8")
        cur = re.search(r'Shopify\.currency = \{"active":"(\w+)","rate":"([\d.]+)"', r.text)
        ctry = re.search(r'Shopify\.country = "(\w+)"', r.text)
        lang = re.search(r'<html[^>]*lang="([\w-]+)"', r.text)
        rows.append({"domain": d, "final_url": r.url, "http_status": r.status_code,
                     "language": lang.group(1) if lang else None,
                     "currency": cur.group(1) if cur else None,
                     "fx_rate_vs_eur": float(cur.group(2)) if cur else None,
                     "market_country": ctry.group(1) if ctry else None, "collected": TODAY})
    return pd.DataFrame(rows)


def company_pages() -> None:
    for p in PAGES:
        r = polite.get(f"https://tameson.com/pages/{p}")
        if r is not None and r.status_code == 200:
            (RAW / f"page_{p}.txt").write_text(text_of(r.text), encoding="utf-8")


def catalog():
    cats, prices = [], []
    for cat, handles in CATEGORIES.items():
        for h in handles:
            r = polite.get(f"https://tameson.com/collections/{h}.json")
            n = r.json()["collection"].get("products_count") if r is not None and r.status_code == 200 else None
            cats.append({"category": cat, "collection": h, "products_count": n, "collected": TODAY})
            for page in (1, 2):
                r = polite.get(f"https://tameson.com/collections/{h}/products.json", params={"limit": 250, "page": page})
                if r is None or r.status_code != 200:
                    break
                prods = r.json().get("products", [])
                (RAW / f"products_{h}_p{page}.json").write_text(json.dumps(prods), encoding="utf-8")
                for p in prods:
                    v = p["variants"][0]
                    prices.append({"category": cat, "collection": h, "product_id": p["id"], "vendor": p.get("vendor"),
                                   "product_type": p.get("product_type"), "price_eur": float(v["price"]),
                                   "available": v.get("available"), "collected": TODAY})
                if len(prods) < 250:
                    break
    return pd.DataFrame(cats), pd.DataFrame(prices).drop_duplicates(["category", "product_id"])


if __name__ == "__main__":
    s = stores(); s.to_csv(PUB / "stores.csv", index=False); print(s.to_string())
    company_pages()
    c, p = catalog()
    c.to_csv(PUB / "catalog_categories.csv", index=False)
    p.to_csv(PUB / "catalog_prices.csv", index=False)
    print(c.groupby("category")["products_count"].sum())
    print(p.groupby("category")["price_eur"].describe(percentiles=[.25, .5, .75]).round(1))
