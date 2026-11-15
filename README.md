# Tameson: steering paid acquisition on profit, with honest uncertainty

POAS-first measurement, uncertainty-aware attribution, power-planned experiments and saturation curves for a
multi-country industrial e-commerce.

**[Read the report (PDF, 8 pages)](docs/Tameson_PaidAcquisition_CaseStudy.pdf)** ·
**[Interactive dashboard (live)](https://albt-france.github.io/tameson-paid-acquisition-case-study/docs/dashboard.html)**
([file](docs/dashboard.html): one HTML file, works offline) ·
[Notebook](notebooks/analysis.ipynb) · [SQL](sql/)

> Independent case study based on public data · not affiliated with or endorsed by Tameson.
> Every number is tagged **PUBLIC DATA** (real, sourced) or **SIMULATED** (generated, with known true effects).
> Simulated numbers are never Tameson's numbers.

## Four results

1. **ROAS lies, POAS decides** (SIMULATED): 32% of the budget a ROAS rule would scale goes to campaigns with POAS below 1; 22 of 45 campaigns get a different decision once margin, shipping and fees are counted.
2. **Attribution with error bars** (PUBLIC DATA, real GA4 journeys): Markov moves no channel by more than 1.3 points vs last click (47% of buyers convert in one session); Paid Search gets 1.2% (90% interval 1.0%–1.4%) from only 37 last-click conversions.
3. **Power before testing**: a 14-day A/B test on a true +5% lift has 10% power and its "winners" overstate the lift 3.9×; a Search geo holdout goes from 48% power (2 countries × 8 weeks) to 93% (3 countries × 16 weeks), and its estimate (incremental POAS 1.03, 90% 0.63–1.44) contains the truth (1.42).
4. **Where the next euro goes** (SIMULATED): moving budget from Meta and the saturated tail of Shopping to Microsoft Ads and Search adds €334k gross profit a year by the model (P10–P90 €162k–€520k); the true gain is €143k: right direction, optimistic size.

## What is in it

| Page | Question | Data |
|---|---|---|
| 1 · Tameson in public data | Stores, catalogue, prices, rating, demand by country | PUBLIC |
| 2 · ROAS lies, POAS decides | Where do ROAS and POAS give opposite budget decisions? | SIMULATED |
| 3 · Attribution with error bars | Markov vs last click on real GA4 journeys, with bootstrap intervals | PUBLIC |
| 4 · Power before testing | Minimum size and duration of A/B and geo tests; what an under-sized test concludes | PUBLIC baselines + SIMULATED |
| 5 · Saturation & the next euro | Light MMM (adstock + Hill), marginal POAS, reallocation with ranges | SIMULATED |
| 6 · Who to target | B2B segment value (cohort LTV), LTV:CAC, value-based bidding, countries × topics | SIMULATED + PUBLIC |
| 7 · Methods, limits & AI note | Sources, assumptions, truth checks, limits | — |

## Methods

- **SQL** (`sql/`): DuckDB, written in standard SQL that also runs on BigQuery (conditional aggregation, window
  functions, `STRING_AGG ... ORDER BY`). `sql/bigquery/ga4_markov_paths.sql` builds the journey table directly from
  Google's official public GA4 table.
- **POAS**: gross profit (product margin − net shipping − payment and marketplace fees) / ad spend.
  Break-even ROAS = 1 / net margin.
- **Attribution**: first-order Markov chain, removal effect, on real GA4 user journeys; 500-resample bootstrap of users
  for 90% intervals; a second modelling variant (Direct not treated as a channel).
- **Power**: two-proportion z-test sizing on the real GA4 conversion rate; Monte-Carlo of under-sized tests (power,
  exaggeration, wrong sign) and of daily peeking; geo-test MDE from pre-period regression noise (real Google Trends noise
  per country, simulated profit for the holdout design).
- **Media-mix model** (`src/methods.py`): geometric adstock + Hill saturation per channel, panel of 5 countries × 104 weeks,
  penalised non-linear least squares (SciPy) with weak priors, ROI priors and calibration on the geo holdout; residual
  block bootstrap for ranges; SLSQP reallocation under a fixed budget with 0.5–2× guardrails.
- **Customer value**: gross-profit LTV by cohort, only on cohorts observed for the full window (no censoring bias).
- AI-assisted workflow: I used Claude, mainly to write scripts faster. I drove the project: I defined the questions, chose and validated the data sources, made the analytical decisions and checked every result.

## Re-run

```bash
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python src/run_all.py      # simulate -> SQL -> notebook (executed) -> PDF report -> dashboard
```

The PDF is printed with headless Edge or Chrome. Public data are snapshots in `data/public/`; the collectors are
`src/collect_public.py`, `src/collect_catalog.py`, `src/collect_trends.py` and `src/extract_ga4.py` (real GA4 events,
streamed from the export with DuckDB; not committed because of size — the GA4 aggregates are in `data/output/`).

```
src/       collectors, simulate.py, run_sql.py, methods.py, build_notebook.py, charts.py, build_report.py, build_dashboard.py
sql/       01-02 real GA4 journeys · 03 channel & campaign economics · 04 cohort LTV · 05 weekly panel & geo test
data/      public/ (real snapshots) · sim/ (simulated) · output/ (results) · SOURCES.md · ASSUMPTIONS.md
docs/      PDF report, dashboard, chart images
```

## Sources

Tameson's country stores, company pages, public sitemaps and product pages (facts and list prices, collected politely:
robots.txt, ≥ 2.5 s between requests, no account, nothing bought); the TrustedShops rating shown in the site's
structured data; Google Trends; Google's public GA4 obfuscated sample (BigQuery). Licences and dates:
[data/SOURCES.md](data/SOURCES.md). Simulation assumptions: [data/ASSUMPTIONS.md](data/ASSUMPTIONS.md).

## Limits

- Simulated numbers show how the methods behave; they are not Tameson's results, and effect sizes follow the assumptions.
- The GA4 sample is another shop (Google Merchandise Store, 3 months): it illustrates the method on real paths, not Tameson's channel mix.
- The MMM is light: 104 weeks cannot pin down small channels without priors and experiments; its reallocation gain is overstated (bootstrap ranges cover noise, not model error).
- Catalogue categories come from keyword rules on URLs; prices are a sample of 30 products per category; Google Trends is an index of search share, not volume.
