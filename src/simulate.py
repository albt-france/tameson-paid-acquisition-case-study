"""SIMULATED data for the Tameson case study (seed 42). None of these numbers are Tameson's.

What is simulated: 24 months (104 weeks, Nov 2024 - Oct 2026) of weekly ad spend per channel and country,
every order with its margin, the B2B customers who come back, and one geo holdout test.
What is real and read from data/public: the 5 countries (Tameson stores), the 8 product categories and
their public list prices (catalog_prices.csv), and the seasonality of demand per country (Google Trends).

Known "true" effects are programmed in, so the notebook can show that the methods recover them:
- each channel has a true carry-over (adstock) and a true saturation curve (Hill);
- part of the orders that platforms credit to Search / Shopping would have happened anyway;
- Google Search is switched off in FR, ES and GB for 16 weeks (geo holdout); the true lost profit is saved.
All assumptions are listed in data/ASSUMPTIONS.md and saved in data/sim/true_params.json.

    python src/simulate.py
Outputs: data/sim/spend_weekly.parquet, orders.parquet, customers.parquet, true_params.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "data" / "public"
SIM = ROOT / "data" / "sim"
SIM.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(42)

WEEKS = pd.date_range("2024-11-04", periods=104, freq="W-MON")
# 'Pneumatics' is ambiguous in ES/FR (neumático / pneumatique also mean tyre); 'Pneumatic cylinder' is too sparse
SEASON_TOPICS = ["Solenoid valve", "Ball valve", "Pipe fitting"]
COUNTRIES = {"NL": 0.30, "DE": 0.25, "GB": 0.18, "FR": 0.15, "ES": 0.12}  # share of demand (assumption)
CHANNELS = ["Google Search", "Google Shopping", "Microsoft Ads", "Meta", "Marketplaces"]

# ---------------------------------------------------------------- true media parameters (assumptions)
# planned weekly spend for all countries (EUR), Hill shape S, elasticity at planned spend (= marginal / average
# return), adstock decay lambda, and the true average POAS (incremental gross profit / spend) at planned spend.
MEDIA = {
    "Google Search":   dict(spend=20000, S=1.2, elasticity=0.45, lam=0.30, poas=1.60),
    "Google Shopping": dict(spend=16000, S=1.2, elasticity=0.35, lam=0.20, poas=1.15),
    "Microsoft Ads":   dict(spend=3000,  S=1.4, elasticity=0.80, lam=0.30, poas=2.20),
    "Meta":            dict(spend=5000,  S=1.0, elasticity=0.50, lam=0.60, poas=0.55),
    "Marketplaces":    dict(spend=4000,  S=1.2, elasticity=0.50, lam=0.10, poas=0.95),
}
GEO_TEST = dict(channel="Google Search", countries=["FR", "ES", "GB"], start="2026-04-06", weeks=16)

# ---------------------------------------------------------------- products, segments, costs (assumptions)
MARGIN = {"Solenoid valves": 0.40, "Ball & process valves": 0.35, "Pneumatics": 0.36, "Fittings & couplings": 0.46,
          "Hoses": 0.33, "Measurement & control": 0.38, "Hydraulics": 0.28, "Electrical & automation": 0.18,
          "Sealing, tools & MRO": 0.45}
CATS = list(MARGIN)
# category mix of the orders each channel brings (rows sum to 1)
CAT_MIX = {
    "Google Search":   [.17, .14, .10, .12, .08, .12, .08, .10, .09],
    "Google Shopping": [.08, .09, .07, .07, .10, .07, .14, .30, .08],
    "Microsoft Ads":   [.20, .14, .14, .17, .06, .12, .05, .04, .08],
    "Meta":            [.06, .06, .06, .14, .14, .05, .08, .21, .20],
    "Marketplaces":    [.05, .07, .05, .13, .12, .05, .14, .27, .12],
    "Baseline":        [.15, .13, .11, .15, .09, .12, .08, .08, .09],
}
# Current campaign budgets: a revenue-chasing (tROAS) set-up. Each category's share of a channel's budget
# follows its share of the channel's revenue, divided by a tilt: tilt > 1 = the category is allowed a
# higher ROAS target (big-ticket items the agency likes), so it gets slightly less budget per euro of revenue.
ROAS_TILT = {"Solenoid valves": 0.95, "Ball & process valves": 1.0, "Pneumatics": 0.95, "Fittings & couplings": 0.8,
             "Hoses": 1.0, "Measurement & control": 0.95, "Hydraulics": 1.2, "Electrical & automation": 1.35,
             "Sealing, tools & MRO": 0.8}
for _d in (CAT_MIX,):
    for _k, _v in _d.items():
        assert abs(sum(_v) - 1) < 1e-9 and len(_v) == len(CATS), _k
SEGMENTS = {  # share of new customers by channel, then behaviour
    "MRO / maintenance":    dict(units=1.8, disc=0.00, repeats_per_year=1.8, life_weeks=90),
    "OEM / machine builder": dict(units=3.5, disc=0.06, repeats_per_year=2.4, life_weeks=110),
    "Installer / contractor": dict(units=1.5, disc=0.03, repeats_per_year=0.9, life_weeks=60),
    "Reseller":             dict(units=5.0, disc=0.10, repeats_per_year=3.0, life_weeks=80),
    "Consumer / hobby":     dict(units=1.1, disc=0.00, repeats_per_year=0.15, life_weeks=30),
}
SEGS = list(SEGMENTS)
SEG_MIX = {
    "Google Search":   [.30, .15, .25, .05, .25],
    "Google Shopping": [.18, .07, .25, .05, .45],
    "Microsoft Ads":   [.42, .28, .18, .07, .05],
    "Meta":            [.08, .02, .15, .00, .75],
    "Marketplaces":    [.10, .03, .12, .25, .50],
    "Baseline":        [.30, .18, .22, .10, .20],
}
SHIP_COST = {"NL": 7.0, "DE": 9.0, "FR": 11.0, "ES": 13.0, "GB": 19.0}   # cost to Tameson per order (assumption)
SHIP_FEE, FREE_FROM = 9.95, 150.0          # charged to the customer below the free-shipping threshold (assumption)
PAY_FEE, MKT_COMMISSION = 0.018, 0.13      # payment fees on revenue; marketplace commission on revenue
BASELINE_ORDERS = 650                      # weekly organic/direct new orders, all countries, before seasonality
RETURNING_SHARE_PAID = 0.25                # share of ad-driven orders placed by existing customers
CANNIBAL = {"Google Search": 0.04, "Google Shopping": 0.025}   # share of baseline orders whose last click is an ad
RETARGET_REPEAT = 0.025                    # share of repeat orders whose last click is Google Search


# ---------------------------------------------------------------- helpers
def hill(x, K, S):
    x = np.maximum(x, 0)
    return x ** S / (x ** S + K ** S)


def adstock(x, lam):
    """Geometric carry-over, normalised so a constant spend x gives an adstocked value of x."""
    out, carry = np.zeros_like(x, dtype=float), 0.0
    for i, v in enumerate(x):
        carry = v + lam * carry
        out[i] = carry * (1 - lam)
    return out


def seasonality() -> pd.DataFrame:
    """Weekly demand index per country from Google Trends (mean of the 5 topics, 1 = average), real data."""
    f = PUB / "trends_weekly.csv"
    if f.exists():
        t = pd.read_csv(f, parse_dates=["date"])
        t["week"] = t["date"] + pd.Timedelta(days=1)          # Trends weeks start on Sunday
        t = t[t.topic.isin(SEASON_TOPICS)]                    # unambiguous topics only (see ASSUMPTIONS.md)
        t = t.groupby(["country_code", "week"])["interest_index"].sum().reset_index()
        out = []
        for c in COUNTRIES:
            s = t[t.country_code == c].set_index("week")["interest_index"].reindex(WEEKS).interpolate().bfill().ffill()
            s = s.rolling(3, center=True, min_periods=1).mean()   # Trends noise is sampling noise: smooth lightly
            out.append(pd.DataFrame({"country": c, "week": WEEKS, "season": (s / s.mean()).values}))
        return pd.concat(out)
    wk = np.arange(104)
    return pd.concat([pd.DataFrame({"country": c, "week": WEEKS,
                                    "season": 1 + 0.12 * np.cos(2 * np.pi * (wk - 10) / 52)
                                    - 0.25 * ((WEEKS.isocalendar().week.values >= 52) | (WEEKS.isocalendar().week.values <= 1))})
                      for c in COUNTRIES])


def price_sampler():
    """Unit prices drawn from a log-normal fitted to the public list prices of each category
    (catalog_prices.csv, ~30 random products per category), clipped to the observed range."""
    f = PUB / "catalog_prices.csv"
    fits = {}
    if f.exists():
        p = pd.read_csv(f)
        p = p[(p.price_eur > 0.5) & (p.price_eur < 20000)]
        for c in CATS:
            v = np.log(p.loc[p.category == c, "price_eur"].to_numpy())
            if len(v) >= 8:
                fits[c] = (v.mean(), v.std(ddof=1), np.exp(v.min()), np.exp(v.max()))
    for c in CATS:
        if c not in fits:
            print(f"[warning] no public prices for {c}: development default used")
            fits[c] = (np.log(80), 1.0, 2.0, 3000.0)
    PRICE_FITS.update({c: dict(log_mean=m, log_sd=s, median_eur=float(np.exp(m))) for c, (m, s, _, _) in fits.items()})
    # demand tilt: buyers order cheap consumables more often than expensive items, so the price of an ordered
    # item is drawn half a log-sd below the catalogue distribution (assumption, see ASSUMPTIONS.md)
    return lambda cat, n: np.clip(rng.lognormal(fits[cat][0] - DEMAND_TILT * fits[cat][1], fits[cat][1], n), fits[cat][2], fits[cat][3])


PRICE_FITS = {}
DEMAND_TILT = 0.5
SPEND_SPLIT = {}   # filled by calibrate_beta()


SAMPLE_PRICE = price_sampler()


def make_orders(n, source, country, week, new_customer_ids=None):
    """Build n orders brought by `source` (a channel or 'Baseline') with category, value and profit."""
    cat = rng.choice(CATS, size=n, p=CAT_MIX[source])
    seg = rng.choice(SEGS, size=n, p=SEG_MIX[source])
    return pd.DataFrame({"week": week, "country": country, "source": source, "category": cat, "segment": seg})


def value_orders(o: pd.DataFrame) -> pd.DataFrame:
    """Price x units, volume discount, margin by category, shipping, payment fees, marketplace commission."""
    o = o.reset_index(drop=True)
    price = np.empty(len(o))
    for c in CATS:
        m = (o.category == c).to_numpy()
        price[m] = SAMPLE_PRICE(c, m.sum())
    units_mean = o.segment.map({s: v["units"] for s, v in SEGMENTS.items()}).to_numpy()
    units = 1 + rng.poisson(np.maximum(units_mean - 1, 0) * rng.gamma(2.0, 0.5, len(o)))
    disc = o.segment.map({s: v["disc"] for s, v in SEGMENTS.items()}).to_numpy()
    revenue = price * units * (1 - disc)
    margin = o.category.map(MARGIN).to_numpy() - disc + rng.normal(0, 0.03, len(o))
    ship_cost = o.country.map(SHIP_COST).to_numpy() * (1 + 0.15 * (o.category.isin(["Hydraulics", "Hoses"])).to_numpy())
    ship_fee = np.where(revenue < FREE_FROM, SHIP_FEE, 0.0)
    is_mkt = (o.last_click == "Marketplaces").to_numpy() if "last_click" in o else np.zeros(len(o), bool)
    o["revenue_eur"] = revenue.round(2)
    o["product_margin_eur"] = (revenue * margin).round(2)
    o["shipping_net_eur"] = (ship_cost - ship_fee).round(2)
    o["fees_eur"] = (revenue * PAY_FEE + is_mkt * revenue * MKT_COMMISSION).round(2)
    o["gross_profit_eur"] = (o.product_margin_eur - o.shipping_net_eur - o.fees_eur).round(2)
    return o


def calibrate_beta():
    """Average gross profit of one incremental order per channel (large sample), then beta so that the
    average POAS at planned spend equals MEDIA[ch]['poas']. Returns K, beta per channel."""
    out = {}
    for ch, m in MEDIA.items():
        o = make_orders(20000, ch, "NL", WEEKS[0])
        o["last_click"] = ch
        v = value_orders(o)
        gp = v.gross_profit_eur.mean()
        rev_share = v.groupby("category").revenue_eur.sum().reindex(CATS).fillna(0) / v.revenue_eur.sum()
        split = rev_share / pd.Series(ROAS_TILT)
        SPEND_SPLIT[ch] = list((split / split.sum()).values)
        H = 1 - m["elasticity"] / m["S"]               # Hill value at planned spend
        x_over_K = (H / (1 - H)) ** (1 / m["S"])
        K = m["spend"] / x_over_K                      # half-saturation spend (all countries, EUR / week)
        beta = m["poas"] * m["spend"] / (H * gp)       # max incremental orders per week (all countries)
        out[ch] = dict(K=K, beta=beta, gp_per_order=gp, hill_at_plan=H)
    return out


def spend_plan(season: pd.DataFrame) -> pd.DataFrame:
    """Weekly spend per channel and country: budget x seasonality x flighting noise, quarterly budget steps,
    a few dark weeks, and the geo holdout. Enough variation for a media-mix model to learn the curves."""
    rows, planned = [], {}
    for ch, m in MEDIA.items():
        q_steps = rng.choice([0.55, 0.75, 1.0, 1.25, 1.5], size=9)          # budget level per quarter
        for c, share in COUNTRIES.items():
            s = season[season.country == c]["season"].to_numpy()
            q = np.repeat(q_steps, 13)[:104]
            noise = rng.lognormal(0, 0.30, 104)
            dark = rng.random(104) < 0.04
            burst = np.ones(104)                                           # 2 pushes of 3 weeks a year
            for b0 in rng.choice(np.arange(0, 101), size=4, replace=False):
                burst[b0:b0 + 3] = 1.7
            x = m["spend"] * share * q * (0.85 + 0.15 * s) * noise * burst * ~dark
            if ch == GEO_TEST["channel"] and c in GEO_TEST["countries"]:
                planned[c] = x.copy()                                      # spend if there were no test
                start = WEEKS.get_loc(pd.Timestamp(GEO_TEST["start"]))
                x[start:start + GEO_TEST["weeks"]] = 0.0
            rows.append(pd.DataFrame({"week": WEEKS, "country": c, "channel": ch, "spend_eur": x.round(2)}))
    return pd.concat(rows, ignore_index=True), planned


def main():
    season = seasonality()
    params = calibrate_beta()
    spend, planned = spend_plan(season)
    lost_orders = {}

    # ---------------- first orders: baseline + incremental orders from each channel
    batches = []
    for c, share in COUNTRIES.items():
        s = season[season.country == c].set_index("week")["season"]
        trend = np.linspace(0.95, 1.08, 104)
        base_n = rng.poisson(BASELINE_ORDERS * share * s.values * trend)
        for w, n in zip(WEEKS, base_n):
            batches.append(make_orders(n, "Baseline", c, w))
        for ch, m in MEDIA.items():
            x = spend[(spend.country == c) & (spend.channel == ch)]["spend_eur"].to_numpy()
            xa = adstock(x / share, m["lam"])                       # spend per unit of country size
            mu = params[ch]["beta"] * share * hill(xa, params[ch]["K"], m["S"]) * (0.85 + 0.15 * s.values)
            if ch == GEO_TEST["channel"] and c in planned:                # truth: orders the holdout removed
                mu_cf = params[ch]["beta"] * share * hill(adstock(planned[c] / share, m["lam"]), params[ch]["K"], m["S"]) * (0.85 + 0.15 * s.values)
                lost_orders[c] = float((mu_cf - mu).sum())
            for w, n in zip(WEEKS, rng.poisson(mu)):
                batches.append(make_orders(n, ch, c, w))
    first = pd.concat(batches, ignore_index=True)

    # ---------------- who is new: ad-driven orders are partly placed by existing customers
    first["is_new_customer"] = ~((first.source != "Baseline") & (rng.random(len(first)) < RETURNING_SHARE_PAID))

    # last click as an ad platform / GA4 would record it
    lc = np.where(first.source == "Baseline", "Organic & direct", first.source).astype(object)
    paid = first.source != "Baseline"
    lc[paid & (rng.random(len(first)) < 0.12)] = "Organic & direct"          # ad-driven, but last click organic
    r = rng.random(len(first))
    base = (first.source == "Baseline").to_numpy()
    start = pd.Timestamp(GEO_TEST["start"])
    in_test = (first.country.isin(GEO_TEST["countries"]) & (first.week >= start)
               & (first.week < start + pd.Timedelta(weeks=GEO_TEST["weeks"]))).to_numpy()
    lc[base & (r < CANNIBAL["Google Search"]) & ~in_test] = "Google Search"      # no ads shown during the holdout
    lc[base & (r >= CANNIBAL["Google Search"]) & (r < CANNIBAL["Google Search"] + CANNIBAL["Google Shopping"])] = "Google Shopping"
    first["last_click"] = lc

    # ---------------- customers acquired by the new first orders
    new = first[first.is_new_customer].copy()
    new["customer_id"] = np.arange(1, len(new) + 1)
    customers = new[["customer_id", "week", "country", "segment", "last_click", "source"]].rename(
        columns={"week": "first_week", "last_click": "acquisition_channel", "source": "true_driver"})

    # existing customers placing ad-driven orders: attach them to random earlier customers of that country
    old = first[~first.is_new_customer].copy()
    old["customer_id"] = 0
    for c in COUNTRIES:
        pool = customers[customers.country == c][["customer_id", "first_week"]]
        m = (old.country == c).to_numpy()
        if m.sum():
            idx = rng.integers(0, len(pool), m.sum())
            old.loc[m, "customer_id"] = pool.customer_id.to_numpy()[idx]

    # ---------------- repeat orders of the acquired customers (until churn or end of data)
    end = WEEKS[-1]
    seg_p = pd.DataFrame(SEGMENTS).T
    cu = customers.merge(seg_p, left_on="segment", right_index=True)
    life = rng.exponential(cu.life_weeks.astype(float))
    active_end = (cu.first_week + pd.to_timedelta((life * 7).astype(int), unit="D")).clip(upper=end)
    active_weeks = ((active_end - cu.first_week).dt.days / 7).clip(lower=0).to_numpy()
    rate = cu.repeats_per_year.astype(float).to_numpy() * rng.gamma(1.5, 1 / 1.5, len(cu))
    n_rep = rng.poisson(rate * active_weeks / 52)
    rep_cust = np.repeat(cu.customer_id.to_numpy(), n_rep)
    rep_start = np.repeat(cu.first_week.to_numpy(), n_rep)
    rep_span = np.repeat(active_weeks, n_rep)
    offs = np.ceil(rng.random(len(rep_cust)) * rep_span).astype(int).clip(min=1)
    rep_week = pd.to_datetime(rep_start) + pd.to_timedelta(offs * 7, unit="D")
    rep = pd.DataFrame({"customer_id": rep_cust, "week": rep_week})
    rep = rep[rep.week <= end].merge(customers[["customer_id", "country", "segment"]], on="customer_id")
    rep["category"] = [rng.choice(CATS, p=CAT_MIX["Baseline"]) for _ in range(len(rep))] if len(rep) < 1 else \
        rng.choice(CATS, size=len(rep), p=CAT_MIX["Baseline"])
    rep["source"] = "Repeat"
    rep["is_new_customer"] = False
    rep["last_click"] = np.where(rng.random(len(rep)) < RETARGET_REPEAT, "Google Search",
                                 np.where(rng.random(len(rep)) < 0.5, "Email & CRM", "Organic & direct"))

    orders = pd.concat([new, old, rep], ignore_index=True)
    orders = value_orders(orders)
    orders["order_date"] = orders.week + pd.to_timedelta(rng.integers(0, 5, len(orders)), unit="D")  # weekdays (B2B)
    orders = orders.sort_values(["order_date", "customer_id"]).reset_index(drop=True)
    orders.insert(0, "order_id", np.arange(1, len(orders) + 1))
    orders = orders[["order_id", "order_date", "week", "customer_id", "country", "segment", "category", "source",
                     "last_click", "is_new_customer", "revenue_eur", "product_margin_eur", "shipping_net_eur",
                     "fees_eur", "gross_profit_eur"]]

    # spend by campaign (channel x category) for the ROAS / POAS comparison
    split = pd.DataFrame(SPEND_SPLIT, index=CATS).T.stack().rename("share").reset_index()
    split.columns = ["channel", "category", "share"]

    spend.to_parquet(SIM / "spend_weekly.parquet", index=False)
    orders.to_parquet(SIM / "orders.parquet", index=False)
    customers.to_parquet(SIM / "customers.parquet", index=False)
    split.to_csv(SIM / "campaign_split.csv", index=False)
    season.to_csv(SIM / "seasonality.csv", index=False)
    gp_test = orders[(orders.source == GEO_TEST["channel"]) & orders.country.isin(GEO_TEST["countries"])].gross_profit_eur.mean()
    test_spend = spend[(spend.channel == GEO_TEST["channel"]) & spend.country.isin(GEO_TEST["countries"])]
    GEO_TEST["true_lost_orders"] = sum(lost_orders.values())
    GEO_TEST["true_lost_gp_first_orders"] = GEO_TEST["true_lost_orders"] * gp_test
    # customers not acquired during the holdout also miss their first repeat orders inside the measurement window
    # (test weeks + 4): expected repeat profit per lost new customer, by Monte Carlo on the true segment behaviour
    mc = np.random.default_rng(7)                              # separate stream: does not change the data above
    n = 20000
    seg = mc.choice(SEGS, size=n, p=SEG_MIX[GEO_TEST["channel"]])
    sp = pd.DataFrame(SEGMENTS).T.loc[seg]
    window = GEO_TEST["weeks"] + 4
    first = mc.uniform(0, GEO_TEST["weeks"], n)
    active = np.minimum(mc.exponential(sp.life_weeks.astype(float).to_numpy()), window - first)
    reps = mc.poisson(sp.repeats_per_year.astype(float).to_numpy() * mc.gamma(1.5, 1 / 1.5, n) * active / 52)
    rep_gp = orders[orders.source == "Repeat"].groupby("segment").gross_profit_eur.mean()
    rep_per_customer = float(np.mean(reps * rep_gp.reindex(seg).to_numpy()))
    lost_new = GEO_TEST["true_lost_orders"] * (1 - RETURNING_SHARE_PAID)
    GEO_TEST["true_lost_gp_repeats_in_window"] = lost_new * rep_per_customer
    GEO_TEST["true_lost_gp"] = GEO_TEST["true_lost_gp_first_orders"] + GEO_TEST["true_lost_gp_repeats_in_window"]
    GEO_TEST["spend_not_spent"] = float(sum(planned[c].sum() for c in planned) - test_spend.spend_eur.sum())
    truth = {"media": {ch: {**MEDIA[ch], **params[ch]} for ch in MEDIA}, "geo_test": GEO_TEST,
             "countries": COUNTRIES, "margin": MARGIN, "ship_cost": SHIP_COST, "ship_fee": SHIP_FEE,
             "free_from": FREE_FROM, "pay_fee": PAY_FEE, "marketplace_commission": MKT_COMMISSION,
             "cannibalisation": CANNIBAL, "returning_share_paid": RETURNING_SHARE_PAID, "segments": SEGMENTS,
             "price_fits": PRICE_FITS, "campaign_split": SPEND_SPLIT, "roas_tilt": ROAS_TILT, "cat_mix": CAT_MIX, "seg_mix": SEG_MIX}
    (SIM / "true_params.json").write_text(json.dumps(truth, indent=2, default=float), encoding="utf-8")

    print(f"{len(orders):,} orders, {len(customers):,} customers, spend EUR {spend.spend_eur.sum():,.0f}")
    print(orders.groupby("source")[["revenue_eur", "gross_profit_eur"]].sum().round(-3))


if __name__ == "__main__":
    main()
