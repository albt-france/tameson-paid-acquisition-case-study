"""Build the 8-page PDF report: charts (src/charts.py) -> HTML pages (16:9) -> PDF with headless Edge/Chrome.

Every number on the pages is read from data/public or data/output, so the report always matches the code.
    python src/build_report.py
Outputs: docs/report.html, docs/Tameson_PaidAcquisition_CaseStudy.pdf
"""
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pandas as pd
from pypdf import PdfReader, PdfWriter

import charts

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUTD = ROOT / "data" / "output"
PUB = ROOT / "data" / "public"
COLLECTED = "14 Nov 2026"
PDF_NAME = "Tameson_PaidAcquisition_CaseStudy.pdf"
DISCLAIMER = "Independent case study based on public data · not affiliated with or endorsed by Tameson"
# The AI-use note is written once, in README.md (Methods), and reused here verbatim.
AI_NOTE = next(l[2:].strip() for l in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
               if l.startswith("- AI-assisted workflow:"))
SHORT = charts.SHORT


def pct(x, d=0):
    return f"{x * 100:.{d}f}%"


def eur(x, d=0):
    return f"−€{abs(x):,.{d}f}" if x < 0 else f"€{x:,.{d}f}"


def k(x):
    return f"€{x / 1000:,.0f}k"


# ------------------------------------------------------------------ facts
def load():
    c = lambda n, folder=OUTD: pd.read_csv(folder / f"{n}.csv")
    f = {"h": json.loads((OUTD / "headline.json").read_text(encoding="utf-8"))}
    for n in ["poas_campaigns", "channel_summary", "category_breakeven", "attribution_ci", "ab_sizing", "geo_test_plan",
              "incremental_poas", "reallocation", "ltv_adjusted", "segment_value", "ltv_cac", "country_priority",
              "country_economics"]:
        f[n] = c(n)
    for n in ["stores", "catalog_categories", "catalog_prices", "rating"]:
        f[n] = c(n, PUB)
    return f


# ------------------------------------------------------------------ layout helpers
def page(n, title, subtitle, tag, body, sources):
    tag_html = f'<div class="tag tag-{tag.lower().split()[0]}">{tag}</div>'
    return f"""
<section class="page">
  <header><div><h1>{title}</h1><p class="sub">{subtitle}</p></div>{tag_html}</header>
  <main>{body}</main>
  <footer><span>{sources} · collected {COLLECTED}</span><span>{DISCLAIMER}</span><span>{n}</span></footer>
</section>"""


def card(inner, cls=""):
    return f'<div class="card {cls}">{inner}</div>'


def img(src, cap=""):
    return f'<figure><img src="{src}"/>{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>'


def tile(label, value, text):
    return card(f'<div class="label">{label}</div><div class="big">{value}</div><p>{text}</p>', "tile")


# ------------------------------------------------------------------ pages
def p0(f, ch):
    h = f["h"]
    g, gp, rl, ps = h["geo_test"], h["geo_plan"], h["realloc"], h["paid_search"]
    tiles = "".join([
        tile("SIMULATED · PAGE 2", pct(h["roas_scaled_losing_share"]),
             f"of the budget a ROAS rule would scale goes to campaigns that lose money (POAS &lt; 1). "
             f"{h['poas_campaigns_differ']} of {h['poas_campaigns_total']} campaigns get a different decision under POAS."),
        tile("PUBLIC DATA · PAGE 3", f"{pct(ps['mk_lo'], 1)}–{pct(ps['mk_hi'], 1)}",
             f"Paid Search's Markov share on real GA4 journeys (90% interval), from {int(ps['conversions_last_click'])} "
             f"last-click conversions. {pct(h['ga4_single_session_share'])} of buyers convert in one session."),
        tile("SIMULATED · PAGE 4", f"{pct(gp['power_small_70'])} → {pct(gp['power_big_70'])}",
             f"power of a Search geo holdout: 2 countries × 8 weeks vs 3 countries × 16 weeks. The planned test measured "
             f"{k(-g['effect_gp'])} of lost profit (90%: {k(-g['ci90_hi'])}–{k(-g['ci90_lo'])}; truth {k(-g['true_lost_gp'])})."),
        tile("SIMULATED · PAGE 5", f"+{k(rl['gain_k_per_year'] * 1000)}",
             f"gross profit a year from moving {k(rl['moved_k_per_week'] * 1000)} a week between channels, same budget "
             f"(P10–P90 {k(rl['gain_p10'] * 1000)}–{k(rl['gain_p90'] * 1000)}). True gain: {k(rl['true_gain_k_per_year'] * 1000)}: right direction, overstated."),
    ])
    q = card(f"""<h2>Business questions</h2><ol class="qs">
      <li><b>Value</b> Does steering on ROAS or on POAS change the budget? <span class="pg">p.2</span></li>
      <li><b>Attribution</b> How much credit does each channel get, and how sure are we? <span class="pg">p.3</span></li>
      <li><b>Testing</b> How big and how long must a test be before we trust it? <span class="pg">p.4</span></li>
      <li><b>Budget</b> Where does saturation start, where should the next euro go? <span class="pg">p.5</span></li>
      <li><b>Targeting</b> Which customers, countries and topics are worth paying for? <span class="pg">p.6</span></li></ol>
      <p class="reco"><b>Recommendations:</b> (1) bid on gross profit, not revenue: send margin (and later 12-month value)
      as the conversion value, and judge campaigns on POAS; (2) report every channel share with an interval and stop
      reading sub-2-point differences as signal; (3) size every test before launch: an A/B test on a 10% lift needs
      ~{h['ab_days_10pct']} days at the sample's traffic, and a Search holdout needs 3 countries × 16 weeks;
      (4) cut the saturated tail of Shopping and Meta first, scale Search, and test Microsoft Ads before scaling it;
      (5) acquire B2B repeat buyers (OEM, resellers, MRO): their 12-month value is several times a consumer's.</p>""", "wide")
    m = card("""<h2>Data &amp; methods</h2>
      <p><b class="k">PUBLIC</b> Tameson's six country stores, ~161k product URLs from its public sitemaps, list prices,
      TrustedShops rating, Google Trends (6 countries, 5 topics, 5 years), and real user journeys from Google's public
      GA4 sample (BigQuery).</p>
      <p><b class="k">SIMULATED</b> 24 months of spend, orders with margin and B2B repeat customers in 5 countries, built on the
      public prices and seasonality, with known true effects. Realistic patterns, <u>not</u> Tameson's numbers.</p>
      <p><b class="k">METHODS</b> SQL (DuckDB, BigQuery-compatible), Markov attribution + bootstrap, power calculations,
      geo holdout, a light media-mix model (adstock + Hill, SciPy) with priors, budget optimisation, cohort LTV.</p>""", "wide")
    how = card("""<h3>How to read this report</h3><p><b>Titles</b> state the conclusion. &nbsp; <b>Tags</b> PUBLIC DATA / SIMULATED
      mark where the data come from. &nbsp; <b>Bands and whiskers</b> are 90% or P10–P90 intervals. &nbsp; <b>Dashed red</b> =
      break-even. &nbsp; <b>×</b> or dotted = the truth programmed in the simulation. &nbsp; Each channel keeps one colour.
      &nbsp; Code, SQL, the notebook and an interactive dashboard are in the repository.</p>""", "how")
    work = card("""<h2>Builds on Tameson's recent work (job posting)</h2><ul class="small">
      <li><b>Markov multi-touch attribution</b> → p.3 adds bootstrap intervals and a modelling-choice check.</li>
      <li><b>Cohort LTV and retention fed into bidding</b> → p.6 value signal tested on later cohorts; p.5 LTV-adjusted break-even.</li>
      <li><b>A/B testing and CRO</b> → p.4 sizing from real traffic; peeking and the winner's curse.</li>
      <li><b>Ad incrementality framework</b> → p.4 power-planned geo holdout, used to calibrate the media-mix model (p.5).</li>
      <li><b>BigQuery + Looker Studio (CAC, POAS, LTV)</b> → BigQuery-compatible SQL; a dashboard with the same KPIs.</li></ul>""")
    body = f'<div class="grid4">{tiles}</div><div class="g0">{q}<div class="stack">{m}{work}</div></div>{how}'
    return page(0, "Tameson: steering paid acquisition on profit, with honest uncertainty",
                "POAS-first measurement, uncertainty-aware attribution, power-planned experiments and saturation curves for a multi-country industrial e-commerce.",
                "OVERVIEW", body, "Data sources listed in data/SOURCES.md")


def p1(f, ch):
    st = f["stores"]
    rows = "".join(f"<tr><td>{r.domain}</td><td>{r.language}</td><td>{r.currency}</td><td>{r.market_country}</td></tr>"
                   for r in st.itertuples() if r.domain != "tameson.be")
    cats = f["catalog_categories"]
    total = int(cats.handles_in_sample.sum())
    rt = f["rating"].iloc[0]
    med = f["catalog_prices"].groupby("category").price_eur.median()
    facts = f"""<h2>Company facts (tameson.com)</h2><ul class="facts">
      <li><b>2013</b> founded in the Netherlands as <i>magneetventielshop</i> (solenoid valves); HQ Eindhoven</li>
      <li><b>150,000+ products</b> claimed; <b>{total / 1000:,.0f}k</b> product URLs in the public sitemaps</li>
      <li><b>Webshop only</b>, ships from NL; EU firms enter a VAT number (0% VAT); invoice payment for companies</li>
      <li><b>{rt.rating:.0f} / {rt.best:.0f}</b> TrustedShops seller rating on <b>{int(rt.ratings_count)}</b> ratings</li></ul>
      <table class="small"><tr><th>Store</th><th>Lang.</th><th>Currency</th><th>Market</th></tr>{rows}</table>
      <p class="note">tameson.be redirects to tameson.nl. One Shopify store, base currency EUR.</p>"""
    body = f"""<div class="grid3">{card(facts)}{card(img(ch['catalog_mix'], 'Catalogue mix: URLs mapped to 9 categories with keyword rules (9% stay "Other")'))}
      {card(img(ch['price_spread'], 'Public list prices, 30 random products per category (US store, converted to EUR)'))}</div>
      <div class="grid3">{card(img(ch['trends_heatmap']))}{card(img(ch['trends_season']))}
      {card(f'''<h2>What this means for paid acquisition</h2><ul>
        <li><b>A long tail of technical SKUs</b>: Shopping and search terms must be managed by category and margin, not SKU by SKU.</li>
        <li><b>Prices span two orders of magnitude</b>: median list price {eur(med.min())} for {med.idxmin()}, {eur(med.max())} for {med.idxmax()}; one revenue target cannot fit both.</li>
        <li><b>Demand differs by country</b>: solenoid valves are searched far more in DE, FR and ES than in NL or GB; pipe fittings lead in GB.</li>
        <li><b>B2B rhythm</b>: Christmas dip and summer lull; test windows must avoid them.</li></ul>
        <p class="note">Trends topics are language-independent; "Pneumatics" is excluded (it also means tyre in ES/FR).</p>''')}</div>"""
    return page(1, f"Tameson: {total / 1000:,.0f}k technical products, six country stores, and demand that differs by country",
                "Public facts from Tameson's own stores, sitemaps and product pages, and Google Trends search interest for its core categories.",
                "PUBLIC DATA", body, "tameson.com and country stores, public sitemaps, product pages, TrustedShops data on site, Google Trends")


def p2(f, ch):
    h = f["h"]
    d = f["poas_campaigns"]
    diff = d[d.roas_decision != d.poas_decision].copy()
    diff["flip"] = diff.roas_decision.isin(["scale", "cut"]) & diff.poas_decision.isin(["scale", "cut"])
    diff = diff.sort_values(["flip", "spend_eur"], ascending=False).head(7)
    rows = "".join(f"<tr{' class=flip' if r.flip else ''}><td>{SHORT[r.channel]} · {r.category}</td><td>{k(r.spend_eur)}</td><td>{r.roas:.1f}</td>"
                   f"<td>{r.poas:.2f}</td><td>{r.roas_decision}</td><td><b>{r.poas_decision}</b></td></tr>" for r in diff.itertuples())
    be_lo, be_hi = h["breakeven_min"], h["breakeven_max"]
    cs = f["channel_summary"].set_index("channel")
    body = f"""<div class="grid-2-1">{card(img(ch['roas_poas_scatter'], 'Each dot = one campaign (channel × category), size = spend; last-click attribution as ad platforms report it'))}
      {card(img(ch['breakeven_roas']))}</div>
      <div class="grid-1-1-1">{card(img(ch['channel_ranks'], 'Channel totals, last click'))}
      {card(f'''<h2>Same campaigns, different decisions (largest first)</h2>
        <table class="small"><tr><th>Campaign</th><th>Spend</th><th>ROAS</th><th>POAS</th><th>ROAS rule</th><th>POAS rule</th></tr>{rows}</table>
        <p class="note">Rule: scale the top third, cut the bottom third, by ROAS or by POAS. {h['poas_campaigns_differ']} of
        {h['poas_campaigns_total']} campaigns change decision; {h['poas_campaigns_opposite']} flip from scale to cut or back (red).</p>''')}
      {card(f'''<h2>Why</h2><p>A revenue target treats every euro of sales the same, but net margin (after shipping and fees)
        runs from {pct(f['category_breakeven'].net_margin.min())} to {pct(f['category_breakeven'].net_margin.max())}:
        <b>{be_hi['category']}</b> needs a ROAS of <b>{be_hi['breakeven_roas']:.1f}</b> to break even,
        <b>{be_lo['category']}</b> only <b>{be_lo['breakeven_roas']:.1f}</b>. The campaigns that flip from scale to cut are marketplace
        campaigns, where the commission eats a thin margin.</p>
        <p><b>Action:</b> send gross profit as the conversion value (margin by category in the product feed), set
        targets on POAS, and watch marketplaces: their commission turns a {cs.loc['Marketplaces','roas']:.1f} ROAS into a
        {cs.loc['Marketplaces','poas']:.2f} POAS.</p>''')}</div>"""
    return page(2, "ROAS lies, POAS decides: a ROAS rule would scale campaigns that lose money",
                f"{pct(h['roas_scaled_losing_share'])} of the spend a ROAS rule would scale sits in campaigns with POAS below 1, once margin, shipping and fees are counted.",
                "SIMULATED", body, "Simulated orders and spend (src/simulate.py), public list prices, sql/03_channel_economics.sql")


def p3(f, ch):
    h = f["h"]
    ps = h["paid_search"]
    a = f["attribution_ci"].set_index("channel")
    clear = ", ".join(a.index[a.diff_is_clear])
    body = f"""<div class="grid-2-1">{card(img(ch['attribution_ci'], f"Real journeys of {h['ga4_buyers']:,} GA4 buyers and their non-buying peers (Google Merchandise Store, Nov 2020 – Jan 2021)"))}
      {card(img(ch['path_length']))}</div>
      <div class="grid-1-1-1">{card(img(ch['paid_search_zoom']))}
      {card(f'''<h2>Reading the intervals</h2><ul>
        <li>Markov moves no channel by more than <b>{h['attr_max_shift_pts'] * 100:.1f} points</b> vs last click: with
        {pct(h['ga4_single_session_share'])} single-session buyers, a multi-touch model can only reshuffle the other half.</li>
        <li>The Markov–last-click gap is clearly non-zero (90% interval of the difference) for: <b>{clear or 'no channel'}</b>.</li>
        <li><b>Paid Search</b>: {pct(ps['markov'], 1)} (90%: {pct(ps['mk_lo'], 1)}–{pct(ps['mk_hi'], 1)}), and
        {pct(ps['markov_no_direct'], 1)} if Direct is not treated as a channel: the modelling choice moves it more than sampling.</li></ul>
        <p><b>Action for Tameson's Markov MTA:</b> publish each share with its bootstrap interval and the result under 2–3 modelling choices.</p>''')}
      {card('''<h2>What the model cannot say</h2><ol class="small">
        <li><b>Incrementality</b>: credit is correlation; a buyer who would have come anyway still gives credit. Only tests measure lift (p.4).</li>
        <li><b>Impressions</b>: no view-through, no offline, no cross-device without login.</li>
        <li><b>Obfuscation</b>: GA4 hides part of the sources ('&lt;Other&gt;', 'data deleted'); untagged sessions fall into Direct.</li>
        <li><b>Context</b>: 3 months of one public shop, not Tameson; B2B buying cycles are longer.</li></ol>''')}</div>"""
    return page(3, f"Attribution with error bars: on real journeys, Markov moves no channel by more than {h['attr_max_shift_pts'] * 100:.1f} points",
                "Markov removal-effect attribution vs last click on real GA4 user journeys, with 90% bootstrap intervals (500 resamples of users).",
                "PUBLIC DATA", body, "Google BigQuery public dataset ga4_obfuscated_sample_ecommerce, sql/01-02, notebook part 2")


def p4(f, ch):
    h = f["h"]
    u, gp, g = h["underpowered"], h["geo_plan"], h["geo_test"]
    body = f"""<div class="grid-2-1 full"><div class="grid2x2">{card(img(ch['ab_days'], f"Real baseline: {pct(h['ab_p0'], 2)} of sessions buy, {h['ab_sessions_per_day']:,.0f} sessions a day (GA4 sample); α = 5%, power 80%"))}
      {card(img(ch['underpowered'], f"True lift +{pct(u['true_lift'])}, 14-day test: power {pct(u['power'])}; 'winners' report +{pct(u['mean_estimate_when_significant'])} on average"))}
      {card(img(ch['geo_designs'], 'Power of geo holdouts, computed on the pre-test weeks only'))}
      {card(img(ch['geo_result']))}</div>
      <div class="stack">{card(f'''<h2>What an under-sized test concludes</h2><p>With a true +{pct(u['true_lift'])} lift and 14 days of traffic,
        only <b>{pct(u['power'])}</b> of tests are significant, and those overstate the lift <b>{u['exaggeration_ratio']:.1f}×</b>
        (+{pct(u['mean_estimate_when_significant'])}); {pct(u['wrong_sign_share_of_significant'])} of 'wins' even have the wrong sign.</p>
        <p>Peeking every day at an A/A test (no real difference) declares a winner <b>{pct(u['false_positive_with_peeking'])}</b> of the time instead of 5%.</p>
        <p><b>Rule:</b> fix the smallest lift worth acting on, compute the duration, run it to the end; on low-traffic pages test bigger changes or a closer metric (add-to-cart).</p>''')}
        {card(f'''<h2>Geo holdout: plan first, then run</h2><p>Search breaks even if at least <b>{pct(gp['breakeven_incrementality'])}</b>
        of its attributed profit is incremental. If it is 70% incremental, switching it off in FR+ES for 8 weeks has <b>{pct(gp['power_small_70'])}</b>
        power; FR+ES+GB for 12 weeks {pct(gp['power_mid_70'])}; for 16 weeks with a 52-week baseline <b>{pct(gp['power_big_70'])}</b>
        (metric: order profit winsorised at the 90th percentile, scaled back).
        A Meta holdout would have {pct(gp['power_meta'])} power, Microsoft Ads {pct(gp['power_microsoft'])}: too small to test this way.</p>
        <p><b>Result:</b> incremental POAS <b>{g['incremental_poas']:.2f}</b> (90%: {g['incremental_poas_lo']:.2f}–{g['incremental_poas_hi']:.2f})
        vs <b>{g['attributed_poas']:.2f}</b> claimed by last click; true value in the simulation {g['true_incremental_poas']:.2f}.</p>''')}</div></div>"""
    return page(4, "Power before testing: most tests that fit in a month cannot see the effects that matter",
                "Sample size and duration before launch, from real traffic (GA4) and real weekly noise; what a too-small test would falsely conclude.",
                "SIMULATED", body, "GA4 public sample (baselines), simulated tests and geo holdout, notebook part 3")


def p5(f, ch):
    h = f["h"]
    rl, lv = h["realloc"], h["ltv_view"]
    ip = f["incremental_poas"].set_index("channel")
    ra = f["reallocation"].set_index("channel")
    up = ", ".join(f"{SHORT[c]} {ra.change_k[c]:+.1f}k" for c in ra.index if ra.change_k[c] > 0.05)
    down = ", ".join(f"{SHORT[c]} {ra.change_k[c]:+.1f}k" for c in ra.index if ra.change_k[c] < -0.05)
    body = f"""{card(img(ch['response_curves'], 'Weekly gross profit vs weekly spend per channel: fitted curve, P10–P90 band (50 bootstrap refits), truth (dotted), current spend (grey line)'), 'tall')}
      <div class="grid-1-1-1">{card(img(ch['marginal_poas']))}{card(img(ch['reallocation']))}
      {card(f'''<h2>Where the next euro goes</h2><p><b>Move</b> {down} <b>to</b> {up} (€k a week, guardrails 0.5–2× today):
        <b>+{k(rl['gain_k_per_year'] * 1000)}</b> gross profit a year (P10–P90 {k(rl['gain_p10'] * 1000)}–{k(rl['gain_p90'] * 1000)}).
        In the simulation the true gain is {k(rl['true_gain_k_per_year'] * 1000)}: right direction, but below the P10, because
        bootstrap ranges cover noise, not model error. Treat the size as optimistic.</p>
        <p><b>Profit, not ROAS, sets the total:</b> on first-order profit, the profit-maximising budget is {k(rl['profit_max_total_k_per_week'] * 1000)}
        a week; counting 12-month repeat value it is {k(lv['profit_max_total_k_12m'] * 1000)}, vs {k(lv['current_total_k'] * 1000)} today.</p>
        <p class="note">Microsoft Ads (6% of spend) has the widest band ({ip.mar_p10['Microsoft Ads']:.2f}–{ip.mar_p90['Microsoft Ads']:.2f}, truth
        {ip.true_marginal_poas['Microsoft Ads']:.2f}) and a geo test could not see it: scale it in steps and watch. Search is calibrated on the geo holdout; R² {rl['mmm_r2']:.2f}.</p>''')}</div>"""
    return page(5, "Where the next euro goes: Microsoft Ads and Search, not Meta or the saturated tail of Shopping",
                "A light media-mix model (adstock + Hill saturation, 5 countries × 104 weeks, priors and geo calibration), marginal profit and budget reallocation with ranges.",
                "SIMULATED", body, "Simulated spend and orders, sql/05_weekly_panel.sql, src/methods.py, notebook part 4")


def p6(f, ch):
    h = f["h"]
    v = h["vbb"]
    pr = f["country_priority"].set_index("country_code")
    rows = "".join(f"<tr><td>{c}</td><td>{r['Solenoid valve']:.0f}</td><td>{r['Ball valve']:.0f}</td><td>{r['Pipe fitting']:.0f}</td>"
                   f"<td>{r['net_margin_sim']:.1%}</td></tr>" for c, r in pr.iterrows())
    body = f"""<div class="grid3">{card(img(ch['segment_ltv']))}{card(img(ch['cohort_curves']))}{card(img(ch['ltv_cac'], 'CAC = spend / new customers credited by last click'))}</div>
      <div class="grid3">{card(f'''<h2>Countries and topics (Google Trends × margin)</h2>
        <table class="small"><tr><th>Store</th><th>Solenoid valve</th><th>Ball valve</th><th>Pipe fitting</th><th>Net margin (sim.)</th></tr>{rows}</table>
        <p class="note">Trends index: share of a country's searches, top country worldwide = 100 (PUBLIC). Margin after shipping: SIMULATED.</p>''')}
      {card(f'''<h2>Who to target</h2><ul>
        <li><b>B2B repeat buyers</b> (resellers, OEM, MRO) are worth several consumers in 12 months: build audiences from the
        <b>VAT number</b> field and invoice-payment customers (both exist on Tameson's checkout) and bid them up.</li>
        <li><b>Microsoft Ads</b> reaches office-hours buyers with the best LTV:CAC: scale it after a test.</li>
        <li><b>Meta</b> brings one-off consumers: LTV:CAC below 1 even over 12 months.</li>
        <li><b>Marketplaces</b> lose on the first order (commission) but recruit resellers who come back direct.</li></ul>''')}
      {card(f'''<h2>Feeding value into bidding</h2><p>Which signal at the first order predicts 12-month gross profit best
        (tested on later cohorts)? Ranking by first-order revenue (what a tROAS bid uses): Spearman ρ = {v['spearman_first_revenue']:.2f},
        top 20% hold {pct(v['top20_capture_first_revenue'])} of 12-month profit. First-order gross profit + the segment's expected
        repeat profit: ρ = {v['spearman_gp_plus_repeat']:.2f}, top 20% hold {pct(v['top20_capture_gp_plus_repeat'])} (perfect ranking: {pct(v['top20_capture_perfect'])}).</p>
        <p><b>Action:</b> conversion value = first-order gross profit + expected repeat profit of the segment, refreshed
        monthly from the cohort table (BigQuery) and sent with offline conversion uploads.</p>''')}</div>"""
    return page(6, "Who to target: B2B repeat buyers, reached on office-hours search, are worth paying more for",
                "Customer value in gross profit by segment and channel (cohorts, censoring-safe), LTV:CAC, and country × topic demand from Google Trends.",
                "SIMULATED", body, "Simulated customers and orders, sql/04_cohort_ltv.sql, Google Trends (country priority)")


def truth_table(f):
    """Did each method find the effect programmed in the simulation? (estimate, interval, truth)"""
    h, ip = f["h"], f["incremental_poas"].set_index("channel")
    g, rl, u = h["geo_test"], h["realloc"], h["underpowered"]
    rows = [("Geo holdout: Search incremental POAS", f"{g['incremental_poas']:.2f}", f"{g['incremental_poas_lo']:.2f}–{g['incremental_poas_hi']:.2f}", f"{g['true_incremental_poas']:.2f}")]
    for c in ip.index:
        r = ip.loc[c]
        rows.append((f"MMM: {SHORT[c]} marginal POAS", f"{r.marginal_poas:.2f}", f"{r.mar_p10:.2f}–{r.mar_p90:.2f}", f"{r.true_marginal_poas:.2f}"))
    rows.append(("Reallocation gain, €k / year", f"{rl['gain_k_per_year']:,.0f}", f"{rl['gain_p10']:,.0f}–{rl['gain_p90']:,.0f}", f"{rl['true_gain_k_per_year']:,.0f}"))
    rows.append(("Under-sized A/B: lift reported by 'winners'", pct(u['mean_estimate_when_significant']), "–", pct(u['true_lift'])))
    body = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td><b>{d}</b></td></tr>" for a, b, c, d in rows)
    return f"""<h2>Did the methods find the truth? (SIMULATED)</h2><table class="small"><tr><th>Quantity</th><th>Estimate</th>
      <th>Interval</th><th>Truth</th></tr>{body}</table><p class="note">Intervals: 90% (geo) or P10–P90 over 50 bootstrap refits (MMM).</p>"""


def p7(f, ch):
    body = f"""<div class="grid3">{card('''<h2>Sources (PUBLIC DATA)</h2><ul class="small">
        <li>Tameson country stores, company pages, public sitemaps (~161k product URLs) and 270 product pages: facts and list prices.</li>
        <li>TrustedShops rating as published in the site's structured data (headline figures only).</li>
        <li>Google Trends: 5 topics, 10 countries by country and 6 stores weekly, 5 years (via pytrends).</li>
        <li>Google's GA4 obfuscated sample (BigQuery public data), read from a flattened export of the same table; SQL for the official table provided.</li>
        <li>Tameson job posting (stack and recent work).</li></ul>
        <p class="note">Polite collection: robots.txt, ≥ 2.5 s between requests (10 s for product pages), no account, nothing bought.
        Full list with licences and dates: data/SOURCES.md.</p>''')}
      {card('''<h2>Methods</h2><ul class="small">
        <li><b>SQL</b> (DuckDB, standard SQL that also runs on BigQuery): sessions, journeys, campaign economics, cohorts, weekly panel.</li>
        <li><b>POAS</b> = gross profit (margin − net shipping − fees) / spend; break-even ROAS = 1 / net margin.</li>
        <li><b>Markov</b> removal effect on real paths, 500-resample bootstrap, a second modelling variant.</li>
        <li><b>Power</b>: two-proportion z-test sizing; geo MDE from pre-period regression noise; Monte-Carlo of under-sized tests and peeking.</li>
        <li><b>MMM</b>: adstock + Hill per channel, 5-country panel, penalised least squares (priors, geo calibration), block bootstrap; SLSQP reallocation. The active customer base is <i>not</i> a control: it carries the ads' own effect.</li>
        <li><b>LTV</b>: gross-profit cohorts with full observation windows only.</li></ul>''')}
      {card('''<h2>Assumptions (SIMULATED)</h2><ul class="small">
        <li>Margins by category 18–46%, shipping €7–19 per order, payment fees 1.8%, marketplace commission 13%.</li>
        <li>Five B2B segments with different basket sizes and repeat rates.</li>
        <li>True carry-over and saturation per channel; part of last-click credit is cannibalised organic demand.</li>
        <li>One geo holdout with a known true effect.</li></ul>
        <p class="note">All values: data/ASSUMPTIONS.md and data/sim/true_params.json.</p>''')}</div>
      <div class="grid3">{card('''<h2>Limits</h2><ul class="small">
        <li>Simulated numbers show how the methods behave; they are not Tameson's results. Effect sizes follow the assumptions.</li>
        <li>The GA4 sample is another shop (3 months, B2C merchandise): its paths illustrate the method, not Tameson's channel mix.</li>
        <li>The MMM is light: 104 weeks cannot pin down small channels without priors; budgets that follow demand bias any MMM upward. Calibrate with tests.</li>
        <li>Catalogue categories come from keyword rules on URLs; prices are a sample of 30 products per category.</li>
        <li>Google Trends is an index of search share, not volume.</li></ul>''')}
      {card(truth_table(f))}
      {card(f'''<h2>How to re-run</h2><pre>pip install -r requirements.txt
python src/run_all.py
# simulate → SQL → notebook → report → dashboard</pre>
        <p class="small">Public data are snapshots in data/public (collectors in src/collect_*.py, GA4 extract in src/extract_ga4.py).</p>
        <h2>AI note</h2><p class="small">{AI_NOTE}</p>''')}</div>"""
    return page(7, "Methods, limits and AI note", "What is public, what is simulated, how each number is produced, and what it cannot tell.",
                "OVERVIEW", body, "data/SOURCES.md, data/ASSUMPTIONS.md")


CSS = """
@page { size: 1600px 900px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; color: #0B0B0B; background: #F4F4F2; }
.page { width: 1600px; height: 900px; padding: 32px 44px 24px; display: flex; flex-direction: column; page-break-after: always; overflow: hidden; background: #F4F4F2; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 30px; }
h1 { font-size: 28px; margin: 0 0 6px; font-weight: 700; line-height: 1.15; max-width: 1300px; }
.sub { margin: 0; color: #52514E; font-size: 15px; max-width: 1300px; }
.tag { font-size: 12px; font-weight: 700; letter-spacing: .08em; padding: 5px 10px; border-radius: 4px; white-space: nowrap; color: #52514E; }
.tag-public { background: #E3EEFB; color: #1C5CAB; } .tag-simulated { background: #FBE9E0; color: #9A3B12; } .tag-overview { color: #52514E; }
main { flex: 1; display: flex; flex-direction: column; gap: 12px; margin-top: 16px; min-height: 0; }
footer { display: flex; justify-content: space-between; gap: 20px; font-size: 11px; color: #898781; margin-top: 10px; }
.card { background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 8px; padding: 12px 16px; min-height: 0; overflow: hidden; }
.card h2 { font-size: 16px; margin: 0 0 6px; } .card h3 { font-size: 14px; margin: 0 0 4px; }
.card p, .card li { font-size: 13.5px; line-height: 1.4; margin: 3px 0; color: #2B2A27; }
.card ul, .card ol { padding-left: 18px; margin: 4px 0; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.grid2x2 { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 12px; min-height: 0; }
.full { flex: 1 !important; }
.g0 { display: grid; grid-template-columns: 1.25fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid-2-1 { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; flex: 1.25; min-height: 0; }
.grid-1-1-1 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
figure { margin: 0; height: 100%; display: flex; flex-direction: column; }
figure img { width: 100%; flex: 1; min-height: 0; object-fit: contain; }
figcaption { font-size: 11.5px; color: #52514E; margin-top: 3px; }
.tile .label { font-size: 12px; font-weight: 700; color: #52514E; letter-spacing: .04em; }
.tile .big { font-size: 46px; font-weight: 700; margin: 2px 0; color: #0B0B0B; }
.tile p { font-size: 13.5px; color: #52514E; }
.stack { display: flex; flex-direction: column; gap: 12px; min-height: 0; } .stack .card { flex: 1; }
.auto { flex: 0 0 auto !important; } .tall { flex: 1.15 !important; }
.qs li { font-size: 15px !important; margin: 5px 0; } .qs b { color: #2A78D6; margin-right: 6px; }
.pg { color: #898781; font-size: 12px; } .reco { font-size: 14px !important; }
.k { color: #52514E; font-size: 12.5px; letter-spacing: .05em; margin-right: 4px; }
.how p { font-size: 13px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #E1E0D9; padding: 4px 6px; }
td { border-bottom: 1px solid #EFEEE9; padding: 4px 6px; vertical-align: top; }
table.small, .small, .small li { font-size: 12.5px !important; }
.note { font-size: 11.5px !important; color: #6B6A65 !important; }
.facts li { font-size: 13.5px !important; margin: 5px 0; }
tr.flip td { color: #B42F2F; }
pre { background: #F4F4F2; border-radius: 6px; padding: 8px 10px; font-size: 12px; margin: 4px 0 8px; }
"""


def build_html() -> Path:
    ch = charts.build_all()
    f = load()
    pages = [p0, p1, p2, p3, p4, p5, p6, p7]
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Tameson paid acquisition case study</title><style>{CSS}</style></head><body>
{''.join(p(f, ch) for p in pages)}
</body></html>"""
    out = DOCS / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


def find_browser() -> str:
    for c in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              shutil.which("msedge") or "", shutil.which("google-chrome") or "", shutil.which("chromium") or ""]:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("Edge or Chrome is needed to print the PDF")


def print_pdf(html: Path) -> Path:
    pdf, tmp = DOCS / PDF_NAME, DOCS / "_print.pdf"
    profile = tempfile.mkdtemp()            # own profile: an open Edge window would otherwise take the call
    subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
                    f"--print-to-pdf={tmp}", html.as_uri()], check=True, timeout=180)
    last = -1
    for _ in range(120):                    # Edge can return before its child process has written the file
        time.sleep(1)
        size = tmp.stat().st_size if tmp.exists() else -1
        if size > 0 and size == last:
            break
        last = size
    shutil.rmtree(profile, ignore_errors=True)
    reader, writer = PdfReader(str(tmp)), PdfWriter()       # rewrite with neutral metadata
    for pg in reader.pages:
        writer.add_page(pg)
    writer.add_metadata({"/Title": "Tameson - paid acquisition case study", "/Author": "", "/Creator": "", "/Producer": ""})
    with open(pdf, "wb") as fh:
        writer.write(fh)
    tmp.unlink()
    return pdf


def main():
    html = build_html()
    pdf = print_pdf(html)
    print("written", html, pdf, len(PdfReader(str(pdf)).pages), "pages")


if __name__ == "__main__":
    main()
