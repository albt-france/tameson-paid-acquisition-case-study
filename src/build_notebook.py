"""Write notebooks/analysis.ipynb (the single analysis notebook). Run it with:
    python src/build_notebook.py && jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb
(src/run_all.py does both). The notebook reads data/public, data/sim and data/output (SQL results)
and writes the analysis results to data/output for the report and the dashboard.
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Tameson: steering paid acquisition on profit, with honest uncertainty

**Independent case study based on public data · not affiliated with or endorsed by Tameson.**

| Part | Data | Question |
|---|---|---|
| 1 | SIMULATED | Where do ROAS and POAS lead to opposite budget decisions? |
| 2 | PUBLIC (GA4 sample) | What does a Markov model say about channels, and how sure can we be? |
| 3 | PUBLIC (GA4, Google Trends) + SIMULATED | How big and how long must a test be before we run it? |
| 4 | SIMULATED | Where does saturation start, and where should the next euro go? |
| 5 | SIMULATED + PUBLIC (Trends) | Which customers, countries and keywords are worth paying for? |

Simulated data come from `src/simulate.py` (seed 42) with known true effects, so we can check that each
method finds them. Real data: the GA4 obfuscated sample (Google Merchandise Store, not Tameson) and Google Trends.
""")

code("""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
import methods as m

OUT, SIM, PUB = ROOT / "data" / "output", ROOT / "data" / "sim", ROOT / "data" / "public"
truth = json.loads((SIM / "true_params.json").read_text())
CHANNELS = ["Google Search", "Google Shopping", "Microsoft Ads", "Meta", "Marketplaces"]
results = {}          # headline numbers for the report, saved at the end
pd.set_option("display.width", 140)

def save(df, name):
    df.to_csv(OUT / f"{name}.csv", index=False)
""")

# ------------------------------------------------------------------ 1 POAS
md("""
## 1 · ROAS lies, POAS decides  (SIMULATED)

ROAS = revenue / ad spend. **POAS = gross profit / ad spend**, with gross profit = product margin − net shipping
cost − payment and marketplace fees. A campaign breaks even at POAS = 1, so the ROAS it needs to break even is
1 / net margin: a low-margin category needs a much higher ROAS. The SQL query `sql/03_channel_economics.sql`
builds the campaign table (channel × category, last-click attribution, as an ad platform reports it).
""")

code("""
camp = pd.read_csv(OUT / "campaign_economics.csv")
paid = camp[camp.channel.isin(CHANNELS)].copy()
print(paid.shape)
paid[["channel", "category", "spend_eur", "roas", "poas", "breakeven_roas"]].round(2).head(9)
""")

code("""
# Two decision rules a team could use on the same campaigns:
#  - ROAS rule (what a tROAS set-up does): scale the top third by ROAS, cut the bottom third
#  - POAS rule: scale the top third by POAS, cut the bottom third
def rule(s):
    lo, hi = s.quantile([1/3, 2/3])
    return np.where(s >= hi, "scale", np.where(s <= lo, "cut", "hold"))

paid["roas_decision"] = rule(paid.roas)
paid["poas_decision"] = rule(paid.poas)
opposite = paid[((paid.roas_decision == "scale") & (paid.poas_decision == "cut")) |
                ((paid.roas_decision == "cut") & (paid.poas_decision == "scale"))]
differ = paid[paid.roas_decision != paid.poas_decision]
print(f"{len(differ)} of {len(paid)} campaigns get a different decision, {len(opposite)} get the opposite one")
opposite[["channel", "category", "roas", "poas", "roas_decision", "poas_decision"]].round(2)
""")

code("""
# Spend that a ROAS rule would scale although it loses money (POAS < 1)
scaled_by_roas = paid[paid.roas_decision == "scale"]
losing = scaled_by_roas[scaled_by_roas.poas < 1]
results["poas_campaigns_differ"] = len(differ)
results["poas_campaigns_total"] = len(paid)
results["poas_campaigns_opposite"] = len(opposite)
results["roas_scaled_losing_share"] = losing.spend_eur.sum() / scaled_by_roas.spend_eur.sum()
results["roas_scaled_losing_spend"] = losing.spend_eur.sum()

# break-even ROAS by category (net margin after shipping and fees, all orders)
orders = pd.read_parquet(SIM / "orders.parquet")
cat = orders.groupby("category").agg(revenue=("revenue_eur", "sum"), gp=("gross_profit_eur", "sum"),
                                      aov=("revenue_eur", "mean"))
cat["net_margin"] = cat.gp / cat.revenue
cat["breakeven_roas"] = 1 / cat.net_margin
cat = cat.sort_values("breakeven_roas").reset_index()
save(cat, "category_breakeven")
results["breakeven_min"] = cat.iloc[0][["category", "breakeven_roas"]].to_dict()
results["breakeven_max"] = cat.iloc[-1][["category", "breakeven_roas"]].to_dict()
save(paid, "poas_campaigns")
print(f"ROAS rule: {results['roas_scaled_losing_share']:.0%} of the spend it would scale has POAS < 1")
cat.round(2)
""")

code("""
# Channel level: ROAS and POAS rank the channels differently once margins differ
ch = pd.read_csv(OUT / "channel_country_economics.csv")
chs = ch.groupby("channel")[["spend_eur", "revenue_eur", "gross_profit_eur", "new_customers"]].sum()
chs["roas"], chs["poas"], chs["cac"] = chs.revenue_eur / chs.spend_eur, chs.gross_profit_eur / chs.spend_eur, chs.spend_eur / chs.new_customers
chs = chs.loc[CHANNELS]
chs["roas_rank"], chs["poas_rank"] = chs.roas.rank(ascending=False).astype(int), chs.poas.rank(ascending=False).astype(int)
save(chs.reset_index(), "channel_summary")
cc = pd.read_csv(OUT / "country_economics.csv")
results["country_margin"] = cc.set_index("country").net_margin.round(4).to_dict()
chs.round(2)
""")

# ------------------------------------------------------------------ 2 Attribution
md("""
## 2 · Attribution with error bars  (PUBLIC DATA: GA4 sample)

Real user journeys from Google's public GA4 sample (Google Merchandise Store, Nov 2020 – Jan 2021), built in
`sql/01_ga4_sessions.sql` and `sql/02_ga4_paths.sql`. The Markov model gives each channel its **removal effect**:
the share of conversions lost if the channel disappeared. We add **bootstrap intervals**: draw the same number of
users again with replacement, re-fit, repeat 500 times. The spread is the sampling error a single number hides.
""")

code("""
paths = pd.read_csv(OUT / "markov_paths.csv")
lc = pd.read_csv(OUT / "ga4_last_click.csv").set_index("channel").conversions
print(f"{len(paths)} distinct paths, {paths.conversions.sum():,.0f} buyers, {paths.non_conversions.sum():,.0f} non-buyers")
base, eff, mk_share, mk_boot = m.markov_with_bootstrap(paths, n_boot=500)
lc_share, lc_boot = m.last_click_with_bootstrap(lc, n_boot=500)
diff_boot = mk_boot[lc_share.index] - lc_boot.values          # Markov minus last click, replicate by replicate
attr = pd.DataFrame({
    "conversions_last_click": lc,
    "last_click": lc_share, "lc_lo": lc_boot.quantile(.05), "lc_hi": lc_boot.quantile(.95),
    "markov": mk_share, "mk_lo": mk_boot.quantile(.05), "mk_hi": mk_boot.quantile(.95),
    "diff_lo": diff_boot.quantile(.05), "diff_hi": diff_boot.quantile(.95),
}).sort_values("markov", ascending=False)
attr["diff_is_clear"] = (attr.diff_lo > 0) | (attr.diff_hi < 0)     # 90% interval of the difference excludes 0
print(f"Baseline conversion probability: {base:.2%}")
attr.round(4)
""")

code("""
# Second source of uncertainty: modelling choices. Variant = treat 'Direct' as no channel
# (remove it from the paths, merge repeats again; direct-only buyers cannot be attributed).
def drop_direct(p):
    steps = [s for s in p.split(" > ") if s != "Direct"]
    steps = [s for i, s in enumerate(steps) if i == 0 or s != steps[i - 1]]
    return " > ".join(steps)

p2 = paths.assign(path=paths.path.map(drop_direct))
p2 = p2[p2.path != ""].groupby("path", as_index=False)[["conversions", "non_conversions"]].sum()
_, _, mk_nodirect, _ = m.markov_with_bootstrap(p2, n_boot=0)
attr["markov_no_direct"] = mk_nodirect.reindex(attr.index)
single = pd.read_csv(OUT / "ga4_path_length.csv")
results["ga4_buyers"] = int(paths.conversions.sum())
results["ga4_single_session_share"] = float(single.loc[single.sessions_until_purchase == 1, "buyers"].sum() / single.buyers.sum())
ps = attr.loc["Paid Search"]
results["paid_search"] = {k: float(ps[k]) for k in ["conversions_last_click", "last_click", "lc_lo", "lc_hi", "markov", "mk_lo", "mk_hi", "markov_no_direct"]}
results["attr_max_shift_pts"] = float((attr.markov - attr.last_click).abs().max())
save(attr.reset_index(names="channel"), "attribution_ci")
attr[["last_click", "markov", "mk_lo", "mk_hi", "markov_no_direct", "diff_is_clear"]].round(3)
""")

md("""
**What the model cannot say.** (1) It is correlational: a channel that sits on many converting paths gets credit
even if the buyer would have come anyway; only an experiment measures incrementality. (2) It only sees clicks
that reached the site: no impressions, no view-through, no offline. (3) GA4's obfuscation puts part of the
traffic in '<Other>' / '(data deleted)'; sessions with no source tag fall into Direct. (4) Three months of one
shop (the Google Merchandise Store), not Tameson; B2B buying cycles are longer. (5) First-order Markov ignores
order beyond one step.
""")

# ------------------------------------------------------------------ 3 Power
md("""
## 3 · Power before testing  (PUBLIC DATA for the baselines, SIMULATED for the false-positive demo)

Before a test, fix the smallest effect worth detecting, then compute the sample size and duration. A test that is
too small does not just "miss" effects: when it does find one, the estimate is exaggerated.
""")

code("""
daily = pd.read_csv(OUT / "ga4_daily.csv")
p0 = daily.purchase_sessions.sum() / daily.sessions.sum()          # real session conversion rate
sessions_per_day = daily.sessions.mean()
rows = []
for mde in [0.05, 0.10, 0.15, 0.20, 0.30]:
    n = m.n_per_arm(p0, mde)
    rows.append({"relative_mde": mde, "n_per_arm": n, "days_50_50": int(np.ceil(2 * n / sessions_per_day))})
ab = pd.DataFrame(rows)
results["ab_p0"], results["ab_sessions_per_day"] = p0, sessions_per_day
results["ab_days_10pct"] = int(ab.loc[ab.relative_mde == 0.10, "days_50_50"].iloc[0])
results["ab_days_5pct"] = int(ab.loc[ab.relative_mde == 0.05, "days_50_50"].iloc[0])
save(ab, "ab_sizing")
print(f"Baseline: {p0:.2%} of sessions buy, {sessions_per_day:,.0f} sessions/day (GA4 sample)")
ab
""")

code("""
# What an under-sized test would have concluded: true lift +5%, but the test runs 14 days only.
rng = np.random.default_rng(42)
true_lift, days = 0.05, 14
n = int(sessions_per_day * days / 2)
p1 = p0 * (1 + true_lift)
sims = 20000
ca, cb = rng.binomial(n, p0, sims), rng.binomial(n, p1, sims)
ra, rb = ca / n, cb / n
pooled = (ca + cb) / (2 * n)
z = (rb - ra) / np.sqrt(pooled * (1 - pooled) * 2 / n)
sig = np.abs(z) > 1.96
est = rb / ra - 1
under = {
    "true_lift": true_lift, "days": days, "n_per_arm": n,
    "power": float(sig.mean()),
    "mean_estimate_when_significant": float(est[sig & (z > 0)].mean()),
    "exaggeration_ratio": float(est[sig & (z > 0)].mean() / true_lift),
    "wrong_sign_share_of_significant": float((sig & (z < 0)).sum() / sig.sum()),
}
# A/A test with daily peeking: stop at the first day the p-value is below 5%
aa_hits = 0
for _ in range(4000):
    a = rng.binomial(int(sessions_per_day / 2), p0, days).cumsum()
    b = rng.binomial(int(sessions_per_day / 2), p0, days).cumsum()
    nn = np.arange(1, days + 1) * int(sessions_per_day / 2)
    pp = (a + b) / (2 * nn)
    zz = (b - a) / nn / np.sqrt(pp * (1 - pp) * 2 / nn)
    aa_hits += np.any(np.abs(zz[2:]) > 1.96)
under["false_positive_with_peeking"] = aa_hits / 4000
results["underpowered"] = under
pd.DataFrame({"estimate": est[:3000], "significant": sig[:3000]}).to_csv(OUT / "underpowered_draws.csv", index=False)
under
""")

code("""
# Geo tests: real week-to-week noise per country from Google Trends (5 years, weekly).
# Noise = std of the weekly log-ratio 'test country / rest of the stores' after removing its slow trend.
tw = pd.read_csv(PUB / "trends_weekly.csv", parse_dates=["date"])
tw = tw[tw.topic.isin(["Solenoid valve", "Ball valve", "Pipe fitting"])]
wk = tw.pivot_table(index="date", columns="country_code", values="interest_index", aggfunc="sum")
rows = []
for k in ["NL", "DE", "GB", "FR", "ES", "BE"]:
    ctrl = wk.drop(columns=[k]).sum(axis=1)
    d = np.log(wk[k].clip(lower=1)) - np.log(ctrl)
    resid = (d - d.rolling(13, center=True, min_periods=5).mean()).dropna()
    sd, rho = resid.std(), m.ar1(resid)
    for weeks in [2, 4, 6, 8, 10, 12]:
        rows.append({"country": k, "test_weeks": weeks, "weekly_noise_sd": sd, "ar1": rho,
                     "mde_relative": m.geo_mde(sd, n_pre=26, n_test=weeks, rho=rho)})
geo = pd.DataFrame(rows)
save(geo, "geo_mde")
min_weeks = geo[geo.mde_relative <= 0.10].groupby("country").test_weeks.min().reindex(["NL", "DE", "GB", "FR", "ES", "BE"])
results["geo_min_weeks_10pct"] = {k: (None if pd.isna(v) else int(v)) for k, v in min_weeks.items()}
geo.pivot(index="test_weeks", columns="country", values="mde_relative").round(3)
""")

code("""
# Geo holdout (SIMULATED). Step 1, BEFORE the test: choose the design with a power calculation,
# using only data from before the test. Metric = weekly gross profit with each order winsorised at the
# 90th percentile (variance reduction); effects are scaled back to full gross profit at the end.
# Estimator: test-group profit = a + b1*control country 1 + b2*control country 2 + ..., fitted on the pre-period;
# the counterfactual during the test = that equation applied to the control countries.
g = pd.read_csv(OUT / "geo_test_weekly.csv", parse_dates=["week"])
W = g.pivot(index="week", columns="country", values="gross_profit_w90_eur")
cap90 = orders.gross_profit_eur.quantile(0.90)
w90 = orders.assign(gw=orders.gross_profit_eur.clip(upper=cap90))
ratio = (w90.groupby("last_click").gw.sum() / w90.groupby("last_click").gross_profit_eur.sum())   # winsorised / full
start = pd.Timestamp(truth["geo_test"]["start"])
W_pre = W[W.index < start]
att_week = ch.set_index(["channel", "country"]).gross_profit_eur / 104       # attributed GP per week

def design_power(channel, test, n_pre, n_test, incrementality):
    ctrl = [c for c in W.columns if c not in test]
    pre = W_pre.tail(n_pre)
    Xc = np.c_[np.ones(n_pre), pre[ctrl].to_numpy()]
    coef, *_ = np.linalg.lstsq(Xc, pre[test].sum(axis=1).to_numpy(), rcond=None)
    resid = pre[test].sum(axis=1).to_numpy() - Xc @ coef
    sd = resid.std(ddof=Xc.shape[1])
    se_sum = sd * np.sqrt(n_test + n_test ** 2 / n_pre)                  # error of the summed counterfactual
    effect = incrementality * att_week.loc[channel].reindex(test).sum() * n_test * ratio[channel]   # in winsorised units
    return {"channel": channel, "test_countries": "+".join(test), "pre_weeks": n_pre, "test_weeks": n_test,
            "incrementality_assumed": incrementality, "expected_effect": effect, "mde": 2.8 * se_sum,
            "power": float(stats.norm.cdf(effect / se_sum - 1.96))}

be = 1 / chs.loc["Google Search", "poas"]          # break-even incrementality: below it Search loses money
designs = []
for inc in [round(be, 2), 0.7]:
    designs += [design_power("Google Search", ["FR", "ES"], 26, 8, inc),
                design_power("Google Search", ["FR", "ES", "GB"], 52, 12, inc),
                design_power("Google Search", ["FR", "ES", "GB"], 52, 16, inc)]
designs.append(design_power("Meta", ["FR", "ES", "GB"], 52, 16, 0.7))
designs.append(design_power("Microsoft Ads", ["FR", "ES", "GB"], 52, 16, 0.7))
plan = pd.DataFrame(designs)
save(plan, "geo_test_plan")
q = lambda ch_, tc, wk, inc: float(plan[(plan.channel == ch_) & (plan.test_countries == tc) & (plan.test_weeks == wk) & (plan.incrementality_assumed == inc)].power.iloc[0])
results["geo_plan"] = {"breakeven_incrementality": float(be), "winsor_ratio_search": float(ratio["Google Search"]),
                       "power_small_70": q("Google Search", "FR+ES", 8, 0.7), "power_mid_70": q("Google Search", "FR+ES+GB", 12, 0.7),
                       "power_big_70": q("Google Search", "FR+ES+GB", 16, 0.7),
                       "power_small_be": q("Google Search", "FR+ES", 8, round(be, 2)), "power_big_be": q("Google Search", "FR+ES+GB", 16, round(be, 2)),
                       "power_meta": float(plan[plan.channel == "Meta"].power.iloc[0]),
                       "power_microsoft": float(plan[plan.channel == "Microsoft Ads"].power.iloc[0])}
plan.round(2)
""")

code("""
# Step 2, AFTER the test (design chosen: Search off in FR+ES+GB, 16 weeks, 52-week pre-period):
# estimate the lost gross profit and compare with the truth known in the simulation.
test, n_pre, n_t = truth["geo_test"]["countries"], 52, truth["geo_test"]["weeks"]
ctrl = [c for c in W.columns if c not in test]
pre = W_pre.tail(n_pre)
Xc = np.c_[np.ones(n_pre), pre[ctrl].to_numpy()]
coef, *_ = np.linalg.lstsq(Xc, pre[test].sum(axis=1).to_numpy(), rcond=None)
sd = (pre[test].sum(axis=1).to_numpy() - Xc @ coef).std(ddof=Xc.shape[1])
w = pd.DataFrame({"test": W[test].sum(axis=1), "control": W[ctrl].sum(axis=1)})
w["counterfactual"] = np.c_[np.ones(len(W)), W[ctrl].to_numpy()] @ coef
w = w[w.index >= pre.index[0]]
post = (w.index >= start) & (w.index < start + pd.Timedelta(weeks=n_t + 4))   # + 4 weeks of carry-over
n_post = int(post.sum())
r_s = ratio["Google Search"]                                             # back to full gross profit
effect = float((w.test - w.counterfactual)[post].sum()) / r_s
se_post = sd * np.sqrt(n_post + n_post ** 2 / n_pre) / r_s
saved = truth["geo_test"]["spend_not_spent"]
geo_res = {"effect_gp": effect, "ci90_lo": effect - 1.645 * se_post, "ci90_hi": effect + 1.645 * se_post,
           "true_lost_gp": -truth["geo_test"]["true_lost_gp"], "spend_not_spent": saved,
           "incremental_poas": -effect / saved, "incremental_poas_lo": -(effect + 1.645 * se_post) / saved,
           "incremental_poas_hi": -(effect - 1.645 * se_post) / saved,
           "attributed_poas": float(chs.loc["Google Search", "poas"]),
           "true_incremental_poas": truth["geo_test"]["true_lost_gp"] / saved}
results["geo_test"] = geo_res
w.assign(in_test=(w.index >= start) & (w.index < start + pd.Timedelta(weeks=n_t))).reset_index().to_csv(OUT / "geo_test_fit.csv", index=False)
{k: round(v, 2) for k, v in geo_res.items()}
""")

# ------------------------------------------------------------------ 4 MMM
md("""
## 4 · Saturation and where the next euro goes  (SIMULATED)

A light media-mix model, fitted on a panel of 5 countries × 104 weeks (`sql/05_weekly_panel.sql`):

weekly gross profit = baseline × seasonality (Google Trends) + trend + Σ channels β · Hill(adstock(spend))

- **adstock**: part of this week's ad effect carries into next weeks (decay λ);
- **Hill**: returns diminish as spend grows (half-saturation spend K, shape S).

With 104 weeks and ~9% weekly noise per country, small channels are hard to see: we add weak priors (carry-over,
curve shape), wide ROI priors from the platform-attributed POAS, and calibrate Google Search with the geo holdout of part 3.
Uncertainty: residual block bootstrap (resample 4-week blocks of residuals, re-fit). The simulation knows the true
curves, so we can check where the model is right and where it is not.
""")

code("""
from scipy import signal
panel = pd.read_csv(OUT / "weekly_panel.csv", parse_dates=["week"])
cols = ["spend_search", "spend_shopping", "spend_microsoft", "spend_meta", "spend_marketplaces"]
target = "gross_profit_capped_eur"                     # weekly gross profit, top 1% orders capped (sql/05)
size = panel.groupby("country")[target].sum() / panel[target].sum()       # country size, observed
panel["size"] = panel.country.map(size)
countries = sorted(panel.country.unique())
panel["k"] = panel.country.map({c: i for i, c in enumerate(countries)})
panel = panel.sort_values(["k", "week"]).reset_index(drop=True)
# control: a linear trend. Not the active customer base: it is fed by the new customers the ads just
# brought (a mediator), so as a control it would absorb part of the ad effect (a "bad control").
X = panel[cols].to_numpy() / panel["size"].to_numpy()[:, None] / 1000       # kEUR per unit of country size
y = panel[target].to_numpy() / panel["size"].to_numpy() / 1000
t = panel.groupby("k").cumcount().to_numpy() / 104
Z = np.c_[t]
season, kidx = panel.season.to_numpy(), panel.k.to_numpy()

# Priors (a light Bayesian MMM): ROI priors centred on the platform-attributed POAS, wide (sd = 50%),
# and for Google Search the geo holdout result (part 3), which is an experiment: calibration.
calib = {c: (chs.loc[c, "poas"], 0.5 * chs.loc[c, "poas"]) for c in CHANNELS}
geo_se = (geo_res["incremental_poas_hi"] - geo_res["incremental_poas_lo"]) / (2 * 1.645)
calib["Google Search"] = (geo_res["incremental_poas"], geo_se)
PRIORS = dict(lam_prior=(0.3, 0.1), s_prior=(1.2, 0.15), calib=calib)
mmm = m.MMM(CHANNELS).fit(X, y, season, Z, kidx, **PRIORS)
fit_params = mmm.params()
r2 = 1 - np.sum((y - mmm.fitted) ** 2) / np.sum((y - y.mean()) ** 2)
print(f"R² = {r2:.3f}; Search calibrated at POAS {calib['Google Search'][0]:.2f} ± {calib['Google Search'][1]:.2f}")
fit_params.round(3)
""")

code("""
# residual block bootstrap: same spend, new noise -> refit -> spread of the curves
rng = np.random.default_rng(42)
resid = y - mmm.fitted
B, block = 50, 4
boot_params = []
for b in range(B):
    y_star = mmm.fitted.copy()
    for gidx in mmm.groups:                       # resample residual blocks inside each country
        r = resid[gidx]
        starts = rng.integers(0, len(r) - block, int(np.ceil(len(r) / block)))
        y_star[gidx] += np.concatenate([r[s:s + block] for s in starts])[:len(r)]
    mb = m.MMM(CHANNELS).fit(X, y_star, season, Z, kidx, theta0=mmm.theta, max_nfev=150, **PRIORS)
    boot_params.append(mb.params())
print(len(boot_params), "bootstrap fits")
""")

code("""
# Response curves (national weekly spend, kEUR -> weekly gross profit, kEUR): fitted, bootstrap band, truth
current = pd.Series(panel[cols].sum(axis=0).to_numpy() / 104 / 1000, index=CHANNELS)   # average weekly spend, kEUR
rows = []
for c in CHANNELS:
    tp = truth["media"][c]
    grid = np.linspace(0, 3 * current[c], 61)
    boots = np.array([m.response(bp, c, grid) for bp in boot_params])
    margs = np.array([m.marginal(bp, c, grid) for bp in boot_params])
    true_gp = tp["beta"] * tp["gp_per_order"] * m.hill(grid * 1000, tp["K"], tp["S"]) / 1000
    for i, x in enumerate(grid):
        rows.append({"channel": c, "spend_k": x, "gp_fit": m.response(fit_params, c, x),
                     "gp_p10": np.percentile(boots[:, i], 10), "gp_p90": np.percentile(boots[:, i], 90),
                     "marginal_fit": m.marginal(fit_params, c, x), "marginal_p10": np.percentile(margs[:, i], 10),
                     "marginal_p90": np.percentile(margs[:, i], 90), "gp_true": true_gp[i], "current_k": current[c]})
curves = pd.DataFrame(rows)
save(curves, "response_curves")

# average and marginal POAS at current spend: fitted (with range) vs true vs last-click attributed
summ = []
for c in CHANNELS:
    x = current[c]
    tp = truth["media"][c]
    avg_b = np.array([m.response(bp, c, x) / x for bp in boot_params])
    mar_b = np.array([m.marginal(bp, c, x) for bp in boot_params])
    true_avg = tp["beta"] * tp["gp_per_order"] * m.hill(x * 1000, tp["K"], tp["S"]) / (x * 1000)
    h = 1.0
    true_mar = tp["beta"] * tp["gp_per_order"] * (m.hill(x * 1000 + h, tp["K"], tp["S"]) - m.hill(x * 1000 - h, tp["K"], tp["S"])) / (2 * h)
    summ.append({"channel": c, "weekly_spend_k": x, "attributed_poas": chs.loc[c, "poas"],
                 "incremental_poas": m.response(fit_params, c, x) / x, "inc_p10": np.percentile(avg_b, 10), "inc_p90": np.percentile(avg_b, 90),
                 "marginal_poas": m.marginal(fit_params, c, x), "mar_p10": np.percentile(mar_b, 10), "mar_p90": np.percentile(mar_b, 90),
                 "true_incremental_poas": true_avg, "true_marginal_poas": true_mar})
poas_inc = pd.DataFrame(summ)
save(poas_inc, "incremental_poas")
poas_inc.round(2)
""")

code("""
# Reallocation: same total budget, each channel between 0.5x and 2x today (guardrails), maximise gross profit.
recs, gains = [], []
for bp in [fit_params] + boot_params:
    r = m.reallocate(bp, current)
    recs.append(r)
    gains.append(sum(m.response(bp, c, r[c]) - m.response(bp, c, current[c]) for c in CHANNELS))
recs = pd.DataFrame(recs[1:]); rec_fit = m.reallocate(fit_params, current)
realloc = pd.DataFrame({"channel": CHANNELS, "current_k": current.values, "recommended_k": rec_fit.values,
                        "rec_p10": recs.quantile(.1).values, "rec_p90": recs.quantile(.9).values})
realloc["change_k"] = realloc.recommended_k - realloc.current_k
gain_b = np.array(gains[1:]) * 52                                   # kEUR gross profit per year
true_p = pd.DataFrame({"beta": [truth["media"][c]["beta"] * truth["media"][c]["gp_per_order"] / 1000 for c in CHANNELS],
                       "K": [truth["media"][c]["K"] / 1000 for c in CHANNELS], "S": [truth["media"][c]["S"] for c in CHANNELS]}, index=CHANNELS)
true_gain = sum(m.response(true_p, c, rec_fit[c]) - m.response(true_p, c, current[c]) for c in CHANNELS) * 52
opt_total = m.profit_max_total(fit_params, current)
results["realloc"] = {"gain_k_per_year": float(gains[0] * 52), "gain_p10": float(np.percentile(gain_b, 10)),
                      "gain_p90": float(np.percentile(gain_b, 90)), "true_gain_k_per_year": float(true_gain),
                      "moved_k_per_week": float(realloc.change_k.clip(lower=0).sum()),
                      "current_total_k_per_week": float(current.sum()), "profit_max_total_k_per_week": float(opt_total.sum()),
                      "mmm_r2": float(r2)}
save(realloc, "reallocation")
realloc.round(2)
""")

# ------------------------------------------------------------------ 5 Targeting
md("""
## 5 · Who to target  (SIMULATED customers, PUBLIC Google Trends for countries and topics)

B2B value is in the repeat orders. We measure LTV in **gross profit** and without censoring bias
(`sql/04_cohort_ltv.sql`: an h-month LTV only uses customers observed for h months).
""")

code("""
lt = pd.read_csv(OUT / "cohort_ltv.csv")
seg12 = lt[(lt.months == 12) & lt.segment.notna() & lt.acquisition_channel.isna()].set_index("segment")
cust = pd.read_parquet(SIM / "customers.parquet")
mix = cust.segment.value_counts(normalize=True).rename("share_of_new_customers")
cv = pd.read_csv(OUT / "customer_value.csv")
first = cv.groupby("segment").agg(first_order_revenue=("first_revenue_eur", "mean"))
segv = seg12[["customers", "gp_ltv_eur", "orders_per_customer"]].join(mix).join(first).sort_values("gp_ltv_eur", ascending=False)
save(segv.reset_index(), "segment_value")
results["segment_ltv12"] = segv.gp_ltv_eur.round(0).to_dict()
segv.round(2)
""")

code("""
# LTV : CAC by channel. CAC = spend / new customers credited by last click (what you can measure daily);
# LTV = 12-month gross profit of the customers each channel acquired.
ch12 = lt[(lt.months == 12) & lt.segment.isna() & lt.acquisition_channel.notna()].set_index("acquisition_channel")
lc_tab = chs[["cac"]].join(ch12[["gp_ltv_eur"]])
lc_tab["ltv_to_cac"] = lc_tab.gp_ltv_eur / lc_tab.cac
save(lc_tab.reset_index(names="channel"), "ltv_cac")
results["ltv_cac"] = lc_tab.ltv_to_cac.round(2).to_dict()
lc_tab.round(2)
""")

code("""
# From short-term POAS to long-term profit: the MMM measures gross profit within weeks of the ad.
# A new customer then keeps buying: value multiplier = 12-month gross profit / first-order gross profit.
# Break-even marginal POAS is then 1 / multiplier, not 1 (each euro must return 1 euro over 12 months).
sums = cv.groupby("acquisition_channel")[["gp_12m_eur", "first_gp_eur"]].sum()
mult = (sums.gp_12m_eur / sums.first_gp_eur).reindex(CHANNELS)
ltv_view = poas_inc.set_index("channel")[["marginal_poas", "mar_p10", "mar_p90"]].copy()
ltv_view["value_multiplier_12m"] = mult
ltv_view["breakeven_marginal_poas"] = 1 / mult
ltv_view["marginal_12m"] = ltv_view.marginal_poas * mult
ltv_params = fit_params.copy()
ltv_params["beta"] = ltv_params.beta * mult.reindex(ltv_params.index).values
opt_ltv = m.profit_max_total(ltv_params, current)
ltv_view["profit_max_spend_k_12m"] = opt_ltv
ltv_view["current_k"] = current
save(ltv_view.reset_index(names="channel"), "ltv_adjusted")
results["ltv_view"] = {"multiplier": mult.round(2).to_dict(), "profit_max_total_k_12m": float(opt_ltv.sum()),
                       "current_total_k": float(current.sum())}
ltv_view.round(2)
""")

code("""
# Value-based bidding: which signal at the first order best predicts 12-month gross profit?
# (a) the first order's revenue (what a tROAS bid uses), (b) a table: mean 12-month GP by segment x first
# category x country, (c) first-order GP + expected repeat GP of the segment. (b) and (c) are learned on the
# older half of the cohorts and tested on the newer half. In practice the segment comes from B2B signals
# visible at checkout (VAT number, invoice payment, company e-mail domain, order size).
cv["first_date"] = pd.to_datetime(cv.first_date)
cut = cv.first_date.quantile(0.5)
cv = cv.sort_values("customer_id").reset_index(drop=True)          # fixed order: ties rank the same every run
train, test = cv[cv.first_date <= cut], cv[cv.first_date > cut]
keys = ["segment", "first_category", "country"]
table = train.groupby(keys).gp_12m_eur.mean().rename("pred_table")
test = test.join(table, on=keys)
test["pred_table"] = test.pred_table.fillna(train.gp_12m_eur.mean())
# (c) first-order gross profit + the repeat profit expected for the customer's segment and country
repeat = (train.gp_12m_eur - train.first_gp_eur).groupby([train.segment, train.country]).mean().rename("repeat_value")
test = test.join(repeat, on=["segment", "country"])
test["pred"] = test.first_gp_eur + test.repeat_value.fillna(0)

def top_capture(score, value, q=0.2):
    # share of the total 12-month value held by the top q of customers ranked by `score`
    top = score.rank(ascending=False, method="first") <= q * len(score)
    return value[top].sum() / value.sum()

vbb = {"spearman_first_revenue": float(stats.spearmanr(test.first_revenue_eur, test.gp_12m_eur)[0]),
       "spearman_table": float(stats.spearmanr(test.pred_table, test.gp_12m_eur)[0]),
       "spearman_gp_plus_repeat": float(stats.spearmanr(test.pred, test.gp_12m_eur)[0]),
       "top20_capture_first_revenue": float(top_capture(test.first_revenue_eur, test.gp_12m_eur)),
       "top20_capture_table": float(top_capture(test.pred_table, test.gp_12m_eur)),
       "top20_capture_gp_plus_repeat": float(top_capture(test.pred, test.gp_12m_eur)),
       "top20_capture_perfect": float(top_capture(test.gp_12m_eur, test.gp_12m_eur)),
       "n_test": int(len(test))}
results["vbb"] = vbb
vbb
""")

code("""
# Country x topic priority: real search interest (Google Trends) x simulated net margin per country.
tb = pd.read_csv(PUB / "trends_by_country.csv")
stores = ["NL", "BE", "DE", "FR", "GB", "ES"]
pri = tb[tb.country_code.isin(stores) & tb.topic.isin(["Solenoid valve", "Ball valve", "Pipe fitting"])]
pri = pri.pivot(index="country_code", columns="topic", values="interest_index").reindex(stores)
margin = cc.set_index("country").net_margin
pri["net_margin_sim"] = margin.reindex(pri.index)
pri.loc["BE", "net_margin_sim"] = margin.get("NL")            # BE is served by tameson.nl
save(pri.reset_index(), "country_priority")
pri.round(3)
""")

code("""
(OUT / "headline.json").write_text(json.dumps(results, indent=2, default=float))
print(json.dumps(results, indent=1, default=float)[:3000])
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                  "language_info": {"name": "python"}}
out = ROOT / "notebooks" / "analysis.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.write(nb, out)
print("written", out)
