"""Matplotlib charts for the PDF report. One function per chart; every number is read from
data/public or data/output (nothing typed in by hand).

Style (same art direction as the earlier case studies): light grey-beige page, white cards, blue for the data,
grey for comparison, red for alerts and thresholds, dashed lines for thresholds, Segoe UI.
Channels keep one fixed colour everywhere (validated categorical order: blue, orange, aqua, yellow, magenta).
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / "data" / "output"
PUB = ROOT / "data" / "public"
IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

BLUE, GREY, RED, INK, MUTED, GRID = "#2A78D6", "#A3A19A", "#D03B3B", "#0B0B0B", "#52514E", "#E1E0D9"
LIGHT = "#C9DDF5"
CH_COLORS = {"Google Search": "#2A78D6", "Google Shopping": "#EB6834", "Microsoft Ads": "#1BAF7A",
             "Meta": "#EDA100", "Marketplaces": "#E87BA4"}
CHANNELS = list(CH_COLORS)
SHORT = {"Google Search": "Search", "Google Shopping": "Shopping", "Microsoft Ads": "Microsoft",
         "Meta": "Meta", "Marketplaces": "Marketplaces"}

plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.facecolor": "white", "axes.facecolor": "white", "legend.frameon": False,
    "axes.titlesize": 11, "axes.titleweight": "semibold", "axes.titlecolor": INK, "axes.titlelocation": "left",
})


def csv(name, folder=OUTD):
    return pd.read_csv(folder / f"{name}.csv")


def headline():
    return json.loads((OUTD / "headline.json").read_text(encoding="utf-8"))


def save(fig, name):
    fig.tight_layout()
    fig.savefig(IMG / f"{name}.png", dpi=200)
    plt.close(fig)
    return f"img/{name}.png"


def eur_k(x, _=None):
    return f"€{x / 1000:,.0f}k"


# ---------------------------------------------------------------- page 1 · public data
def catalog_mix():
    d = csv("catalog_categories", PUB)
    d = d[d.category != "Other"].sort_values("handles_in_sample")
    fig, ax = plt.subplots(figsize=(5.0, 3.3))
    ax.barh(d.category, d.handles_in_sample, color=BLUE, height=0.62)
    for y, v in enumerate(d.handles_in_sample):
        ax.text(v + 300, y, f"{v / 1000:.1f}k", va="center", fontsize=8.5, color=MUTED)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{x / 1000:.0f}k"))
    ax.set_xlabel("Product URLs in the public sitemaps")
    ax.grid(axis="y", visible=False)
    return save(fig, "p1_catalog_mix")


def price_spread():
    p = csv("catalog_prices", PUB)
    order = p.groupby("category").price_eur.median().sort_values().index
    fig, ax = plt.subplots(figsize=(5.0, 3.3))
    for i, c in enumerate(order):
        v = p.loc[p.category == c, "price_eur"]
        ax.scatter(v, np.full(len(v), i) + np.random.default_rng(i).uniform(-0.18, 0.18, len(v)),
                   s=9, color=BLUE, alpha=0.45, linewidths=0)
        ax.plot([v.median()] * 2, [i - 0.3, i + 0.3], color=INK, lw=2)
    ax.set_xscale("log")
    ax.set_yticks(range(len(order)), order)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
    ax.set_xlabel("Public list price per product (log scale), black = median")
    ax.grid(axis="y", visible=False)
    return save(fig, "p1_prices")


def trends_heatmap():
    t = csv("trends_by_country", PUB)
    stores = ["NL", "BE", "DE", "FR", "GB", "ES"]
    topics = ["Solenoid valve", "Ball valve", "Pipe fitting"]
    m = t[t.country_code.isin(stores) & t.topic.isin(topics)].pivot(index="topic", columns="country_code", values="interest_index")
    m = m.reindex(index=topics, columns=stores)
    fig, ax = plt.subplots(figsize=(5.0, 2.5))
    ax.imshow(m.values, cmap="Blues", vmin=0, vmax=max(100, m.values.max()), aspect="auto")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=10, color="white" if v > 55 else INK)
    ax.set_xticks(range(len(stores)), stores)
    ax.set_yticks(range(len(topics)), topics)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Google Trends interest, 5 years (top country worldwide = 100)", fontsize=9.5, color=MUTED, fontweight="normal")
    return save(fig, "p1_trends")


def trends_season():
    w = csv("trends_weekly", PUB)
    w = w[w.topic.isin(["Solenoid valve", "Ball valve", "Pipe fitting"])]
    w["date"] = pd.to_datetime(w.date)
    s = w.groupby(["country_code", "date"]).interest_index.sum().reset_index()
    s["woy"] = s.date.dt.isocalendar().week.clip(upper=52)
    s["idx"] = s.interest_index / s.groupby("country_code").interest_index.transform("mean")
    prof = s.groupby("woy").idx.mean()
    lo, hi = s.groupby("woy").idx.quantile(0.25), s.groupby("woy").idx.quantile(0.75)
    fig, ax = plt.subplots(figsize=(5.0, 2.5))
    ax.fill_between(prof.index, lo, hi, color=LIGHT, lw=0)
    ax.plot(prof.index, prof.values, color=BLUE, lw=2)
    ax.axhline(1, color=GREY, ls="--", lw=1)
    ax.set_xlabel("Week of the year")
    ax.set_ylabel("Demand index (1 = average)")
    ax.set_title("Seasonality: Christmas dip, summer lull (6 stores, 2021-2026)", fontsize=9.5, color=MUTED, fontweight="normal")
    return save(fig, "p1_season")


# ---------------------------------------------------------------- page 2 · ROAS vs POAS
def roas_poas_scatter():
    d = csv("poas_campaigns")
    fig, ax = plt.subplots(figsize=(8.6, 3.9))
    for c in CHANNELS:
        s = d[d.channel == c]
        ax.scatter(s.roas, s.poas, s=np.clip(s.spend_eur / 2500, 12, 260), color=CH_COLORS[c], alpha=0.85,
                   edgecolor="white", linewidth=1.2, label=SHORT[c])
    opp = d[((d.roas_decision == "scale") & (d.poas_decision == "cut")) | ((d.roas_decision == "cut") & (d.poas_decision == "scale"))]
    for i, r in enumerate(opp.sort_values("poas").itertuples()):
        ax.annotate(f"{SHORT[r.channel]} · {r.category.split(' &')[0].split(',')[0]}", (r.roas, r.poas),
                    xytext=(8, -12 if i % 2 else 6), textcoords="offset points", fontsize=8, color=INK)
    ax.axhline(1, color=RED, ls="--", lw=1.2)
    ax.text(d.roas.max(), 1.04, "POAS = 1: break-even", color=RED, fontsize=8, ha="right", va="bottom")
    ax.set_xlabel("ROAS (revenue / ad spend), last click")
    ax.set_ylabel("POAS (gross profit / ad spend)")
    ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.12), handletextpad=0.2, columnspacing=0.8)
    return save(fig, "p2_scatter")


def breakeven_roas():
    d = csv("category_breakeven").sort_values("breakeven_roas")
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    colors = [RED if v == d.breakeven_roas.max() else BLUE for v in d.breakeven_roas]
    ax.barh(d.category, d.breakeven_roas, color=colors, height=0.62)
    for y, (v, mg) in enumerate(zip(d.breakeven_roas, d.net_margin)):
        ax.text(v + 0.15, y, f"{v:.1f}  ({mg:.0%} net margin)", va="center", fontsize=8, color=MUTED)
    ax.set_xlabel("ROAS needed to break even = 1 / net margin")
    ax.set_xlim(0, d.breakeven_roas.max() * 1.55)
    ax.grid(axis="y", visible=False)
    return save(fig, "p2_breakeven")


def channel_ranks():
    d = csv("channel_summary").set_index("channel").loc[CHANNELS]
    fig, axes = plt.subplots(1, 2, figsize=(5.0, 3.0), sharey=True)
    for ax, col, title in ((axes[0], "roas", "ROAS"), (axes[1], "poas", "POAS")):
        ax.barh([SHORT[c] for c in d.index], d[col], color=[CH_COLORS[c] for c in d.index], height=0.6)
        for y, v in enumerate(d[col]):
            ax.text(v, y, f" {v:.2f}", va="center", fontsize=8.5, color=MUTED)
        ax.set_title(title)
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0, d[col].max() * 1.35)
        ax.invert_yaxis() if col == "roas" else None
    axes[1].axvline(1, color=RED, ls="--", lw=1)
    return save(fig, "p2_channels")


# ---------------------------------------------------------------- page 3 · attribution
def attribution_ci():
    a = csv("attribution_ci").set_index("channel").sort_values("markov")
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    y = np.arange(len(a))
    ax.errorbar(a.last_click, y + 0.15, xerr=[a.last_click - a.lc_lo, a.lc_hi - a.last_click], fmt="o", color=GREY,
                ms=6, capsize=3, lw=1.5, label="Last click")
    ax.errorbar(a.markov, y - 0.15, xerr=[a.markov - a.mk_lo, a.mk_hi - a.markov], fmt="o", color=BLUE,
                ms=6, capsize=3, lw=1.5, label="Markov (removal effect)")
    ax.set_yticks(y, a.index)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Share of conversions credited (90% bootstrap interval, 500 resamples)")
    ax.legend(fontsize=8.5, loc="lower right")
    ax.grid(axis="y", visible=False)
    return save(fig, "p3_attribution")


def path_length():
    d = csv("ga4_path_length")
    fig, ax = plt.subplots(figsize=(4.4, 3.0))
    share = d.buyers / d.buyers.sum()
    labels = [str(int(v)) if v < 6 else "6+" for v in d.sessions_until_purchase]
    ax.bar(labels, share, color=[BLUE] + [GREY] * (len(d) - 1), width=0.62)
    for x, v in enumerate(share):
        ax.text(x, v + 0.01, f"{v:.0%}", ha="center", fontsize=8.5, color=MUTED)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Sessions until the first purchase (real GA4 buyers)")
    ax.grid(axis="x", visible=False)
    return save(fig, "p3_pathlength")


def paid_search_zoom():
    h = headline()["paid_search"]
    rows = [("Last click", h["last_click"], h["lc_lo"], h["lc_hi"], GREY),
            ("Markov", h["markov"], h["mk_lo"], h["mk_hi"], BLUE),
            ("Markov, Direct\nnot a channel", h["markov_no_direct"], None, None, BLUE)]
    fig, ax = plt.subplots(figsize=(4.4, 2.6))
    for i, (lab, v, lo, hi, col) in enumerate(rows):
        if lo is not None:
            ax.plot([lo, hi], [i, i], color=col, lw=6, alpha=0.35, solid_capstyle="round")
        ax.plot(v, i, "o", color=col, ms=8, mfc=col if lo is not None else "white", mew=2)
        ax.text(v, i - 0.32, f"{v:.1%}", ha="center", fontsize=8.5, color=MUTED)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, max(r[1] for r in rows) * 1.4)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    ax.set_xlabel(f"Paid Search share ({int(h['conversions_last_click'])} last-click conversions)")
    ax.grid(axis="y", visible=False)
    return save(fig, "p3_paidsearch")


# ---------------------------------------------------------------- page 4 · power
def ab_days():
    d = csv("ab_sizing")
    fig, ax = plt.subplots(figsize=(5.4, 2.9))
    ax.bar([f"{v:.0%}" for v in d.relative_mde], d.days_50_50, color=BLUE, width=0.6)
    for x, v in enumerate(d.days_50_50):
        ax.text(x, v + 4, f"{v} days", ha="center", fontsize=8.5, color=MUTED)
    ax.axhline(28, color=RED, ls="--", lw=1)
    ax.text(len(d) - 0.5, 31, "4 weeks", color=RED, fontsize=8, ha="right")
    ax.set_xlabel("Smallest relative lift we want to detect")
    ax.set_ylabel("Days needed (50/50 split)")
    ax.grid(axis="x", visible=False)
    return save(fig, "p4_abdays")


def underpowered():
    d = csv("underpowered_draws")
    u = headline()["underpowered"]
    fig, ax = plt.subplots(figsize=(5.4, 2.9))
    bins = np.linspace(-0.4, 0.45, 50)
    ax.hist(d.estimate[~d.significant], bins=bins, color=GREY, alpha=0.6, label="not significant")
    ax.hist(d.estimate[d.significant], bins=bins, color=RED, alpha=0.85, label="'significant' (p < 0.05)")
    ax.axvline(u["true_lift"], color=INK, lw=1.5)
    ax.text(u["true_lift"], ax.get_ylim()[1] * 0.95, f" true lift +{u['true_lift']:.0%}", fontsize=8.5, color=INK, va="top")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel(f"Estimated lift in {u['days']}-day A/B tests (simulated 20,000 times)")
    ax.set_yticks([])
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(False)
    return save(fig, "p4_underpowered")


def geo_designs():
    d = csv("geo_test_plan")
    d["label"] = d.channel.map(SHORT) + " · " + d.test_countries + " · " + d.test_weeks.astype(str) + " wk\n" + \
        (d.incrementality_assumed * 100).round().astype(int).astype(str) + "% incremental"
    fig, ax = plt.subplots(figsize=(5.4, 2.9))
    colors = [BLUE if p >= 0.8 else (GREY if p >= 0.5 else RED) for p in d.power]
    ax.barh(d.label, d.power, color=colors, height=0.6)
    for y, v in enumerate(d.power):
        ax.text(v + 0.02, y, f"{v:.0%}", va="center", fontsize=8.5, color=MUTED)
    ax.axvline(0.8, color=INK, ls="--", lw=1)
    ax.set_xlim(0, 1.12)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Power before the test (target 80%)")
    ax.tick_params(axis="y", labelsize=7.5)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    return save(fig, "p4_geodesigns")


def geo_result():
    w = csv("geo_test_fit")
    w["week"] = pd.to_datetime(w.week)
    g = headline()["geo_test"]
    fig, ax = plt.subplots(figsize=(5.4, 2.9))
    ax.plot(w.week, w.counterfactual, color=GREY, lw=1.6, ls="--", label="counterfactual from control countries")
    ax.plot(w.week, w.test, color=BLUE, lw=2, label="FR + ES + GB (Search off)")
    t = w[w.in_test]
    ax.axvspan(t.week.min(), t.week.max(), color=LIGHT, alpha=0.5, lw=0)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(eur_k))
    ax.set_ylabel("Weekly gross profit")
    ax.legend(fontsize=7.5, loc="upper left")
    ax.set_title(f"Lost profit {eur_k(-g['effect_gp'])} (90% CI {eur_k(-g['ci90_hi'])}-{eur_k(-g['ci90_lo'])}); truth {eur_k(-g['true_lost_gp'])}",
                 fontsize=9, color=MUTED, fontweight="normal")
    fig.autofmt_xdate()
    return save(fig, "p4_georesult")


# ---------------------------------------------------------------- page 5 · saturation
def response_curves():
    c = csv("response_curves")
    fig, axes = plt.subplots(1, 5, figsize=(11.5, 2.7))
    for ax, ch in zip(axes, CHANNELS):
        d = c[c.channel == ch]
        ax.fill_between(d.spend_k, d.gp_p10, d.gp_p90, color=CH_COLORS[ch], alpha=0.18, lw=0)
        ax.plot(d.spend_k, d.gp_fit, color=CH_COLORS[ch], lw=2, label="model")
        ax.plot(d.spend_k, d.gp_true, color=INK, lw=1.2, ls=":", label="truth")
        ax.plot(d.spend_k, d.spend_k, color=RED, lw=1, ls="--", label="profit = spend")
        cur = d.current_k.iloc[0]
        ax.axvline(cur, color=GREY, lw=1)
        ax.set_title(SHORT[ch])
        ax.set_xlabel("weekly spend, €k")
        ax.set_ylim(0, max(d.gp_p90.max(), d.gp_true.max()) * 1.1)
    axes[0].set_ylabel("weekly gross profit, €k")
    axes[0].legend(fontsize=7, loc="upper left")
    return save(fig, "p5_curves")


def marginal_poas():
    d = csv("ltv_adjusted").set_index("channel").loc[CHANNELS]
    t = csv("incremental_poas").set_index("channel").loc[CHANNELS]
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    y = np.arange(len(d))
    for i, ch in enumerate(CHANNELS):
        ax.plot([d.mar_p10[ch], d.mar_p90[ch]], [i, i], color=CH_COLORS[ch], lw=6, alpha=0.35, solid_capstyle="round")
        ax.plot(d.marginal_poas[ch], i, "o", color=CH_COLORS[ch], ms=8)
        ax.plot(t.true_marginal_poas[ch], i, "x", color=INK, ms=7, mew=1.5)
        ax.plot([d.breakeven_marginal_poas[ch]] * 2, [i - 0.35, i + 0.35], color=RED, lw=1.5)
    ax.axvline(1, color=RED, ls="--", lw=1)
    ax.set_yticks(y, [SHORT[c] for c in CHANNELS])
    ax.invert_yaxis()
    ax.set_xlabel("Profit from the next euro: dot = model, band = P10-P90, × = truth")
    ax.text(1.02, -0.6, "break-even (first order)", color=RED, fontsize=7.5)
    ax.set_title("red tick = break-even counting 12-month repeat value", fontsize=8, color=RED, fontweight="normal")
    ax.grid(axis="y", visible=False)
    return save(fig, "p5_marginal")


def reallocation():
    d = csv("reallocation").set_index("channel").loc[CHANNELS]
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    y = np.arange(len(d))
    ax.barh(y + 0.18, d.current_k, height=0.34, color=GREY, label="today")
    ax.barh(y - 0.18, d.recommended_k, height=0.34, color=[CH_COLORS[c] for c in CHANNELS], label="recommended")
    ax.errorbar(d.recommended_k, y - 0.18, xerr=[d.recommended_k - d.rec_p10, d.rec_p90 - d.recommended_k],
                fmt="none", ecolor=INK, capsize=3, lw=1)
    ax.set_yticks(y, [SHORT[c] for c in CHANNELS])
    ax.invert_yaxis()
    ax.set_xlabel("Weekly spend, €k (same total; whisker = P10-P90 over 50 refits)")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(axis="y", visible=False)
    return save(fig, "p5_realloc")


# ---------------------------------------------------------------- page 6 · targeting
def segment_ltv():
    d = csv("segment_value").sort_values("gp_ltv_eur")
    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    ax.barh(d.segment, d.gp_ltv_eur, color=BLUE, height=0.6)
    for y, (v, s) in enumerate(zip(d.gp_ltv_eur, d.share_of_new_customers)):
        ax.text(v, y, f"  €{v:,.0f} · {s:.0%} of new", va="center", fontsize=8, color=MUTED)
    ax.set_xlim(0, d.gp_ltv_eur.max() * 2.3)
    ax.set_xlabel("12-month gross profit per new customer")
    ax.grid(axis="y", visible=False)
    return save(fig, "p6_segments")


def cohort_curves():
    lt = csv("cohort_ltv")
    d = lt[lt.segment.notna() & lt.acquisition_channel.isna()]
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    segs = d.groupby("segment").gp_ltv_eur.max().sort_values(ascending=False).index
    shades = [BLUE, "#5B97E0", "#8DB5EA", GREY, "#C8C6BF"]
    for s, col in zip(segs, shades):
        x = d[d.segment == s].sort_values("months")
        ax.plot(x.months, x.gp_ltv_eur, color=col, lw=2, marker="o", ms=4)
        ax.text(x.months.iloc[-1] + 0.3, x.gp_ltv_eur.iloc[-1], s.split(" /")[0], fontsize=8, color=MUTED, va="center")
    ax.set_xlim(0, 23)
    ax.set_xticks([1, 3, 6, 12, 18])
    ax.set_xlabel("Months since first order (only cohorts observed that long)")
    ax.set_ylabel("Cumulative gross profit per customer, €")
    return save(fig, "p6_cohorts")


def ltv_cac():
    d = csv("ltv_cac").set_index("channel").loc[CHANNELS]
    m = csv("ltv_adjusted").set_index("channel").loc[CHANNELS]
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    ax.barh([SHORT[c] for c in CHANNELS], d.ltv_to_cac, color=[CH_COLORS[c] for c in CHANNELS], height=0.6)
    for y, (v, mu) in enumerate(zip(d.ltv_to_cac, m.value_multiplier_12m)):
        ax.text(v, y, f"  {v:.1f}×   (12-m value = {mu:.1f}× first order)", va="center", fontsize=8, color=MUTED)
    ax.axvline(1, color=RED, ls="--", lw=1)
    ax.invert_yaxis()
    ax.set_xlim(0, d.ltv_to_cac.max() * 2.0)
    ax.set_xlabel("12-month gross-profit LTV / CAC")
    ax.grid(axis="y", visible=False)
    return save(fig, "p6_ltvcac")


def build_all():
    fns = [catalog_mix, price_spread, trends_heatmap, trends_season, roas_poas_scatter, breakeven_roas, channel_ranks,
           attribution_ci, path_length, paid_search_zoom, ab_days, underpowered, geo_designs, geo_result,
           response_curves, marginal_poas, reallocation, segment_ltv, cohort_curves, ltv_cac]
    return {f.__name__: f() for f in fns}


if __name__ == "__main__":
    print(build_all())
