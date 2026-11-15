# Assumptions of the simulation (SIMULATED data)

All values live in `src/simulate.py` and are saved with the true effects in `data/sim/true_params.json`.
They are plausible orders of magnitude for a European industrial e-commerce, **not Tameson's figures**.

## What is real (read from data/public)
- The 5 countries simulated = Tameson's EU/UK stores: NL (also serves BE), DE, GB, FR, ES.
- The 9 product categories and their unit prices: a log-normal fitted to the public list prices of each category,
  shifted half a log-sd down because buyers order cheap consumables more often than expensive items (demand tilt).
- Weekly demand seasonality per country: Google Trends (sum of the Solenoid valve, Ball valve and Pipe fitting topics).

## Business
| Assumption | Value | Why |
|---|---|---|
| Period | 104 weeks, 4 Nov 2024 - 26 Oct 2026 | 24 months |
| Demand share by country | NL 30%, DE 25%, GB 18%, FR 15%, ES 12% | Home market first; Google Trends interest |
| Gross margin by category | Fittings 46%, Sealing/tools/MRO 45%, Solenoid valves 40%, Measurement 38%, Pneumatics 36%, Ball & process valves 35%, Hoses 33%, Hydraulics 28%, Electrical & automation 18% | Private-label / technical parts earn more than branded, price-compared electrical items |
| Shipping cost per order (to Tameson) | NL €7, DE €9, FR €11, ES €13, GB €19 (+15% hydraulics, hoses) | Parcel rates from NL; GB after Brexit |
| Shipping fee charged | €9.95 below €150, free above | Common threshold |
| Payment fees | 1.8% of revenue | Card / PayPal / iDEAL mix |
| Marketplace commission | 13% of revenue | Typical B2B marketplace fee |
| Volume discount | OEM 6%, reseller 10%, installer 3% | Reduces margin |

## Customers (B2B segments)
| Segment | Units per order | Repeat orders / year | Mean active life |
|---|---|---|---|
| MRO / maintenance | 1.8 | 1.8 | 90 weeks |
| OEM / machine builder | 3.5 | 2.4 | 110 weeks |
| Installer / contractor | 1.5 | 0.9 | 60 weeks |
| Reseller | 5 | 3.0 | 80 weeks |
| Consumer / hobby | 1.1 | 0.15 | 30 weeks |

Each channel brings a different mix of segments (e.g. Microsoft Ads skews to office-hours MRO and OEM buyers,
Meta to consumers, marketplaces to resellers and consumers) and of categories (Google Shopping and marketplaces
skew to big-ticket electrical and hydraulics). Customer heterogeneity: Gamma(1.5) multiplier on repeat rates.

## Media (true effects the methods must recover)
| Channel | Planned weekly spend (all countries) | Carry-over λ | Hill shape S | Elasticity at plan | True average POAS at plan |
|---|---|---|---|---|---|
| Google Search | €20,000 | 0.30 | 1.2 | 0.45 | 1.60 |
| Google Shopping | €16,000 | 0.20 | 1.2 | 0.35 | 1.15 |
| Microsoft Ads | €3,000 | 0.30 | 1.4 | 0.80 | 2.20 |
| Meta | €5,000 | 0.60 | 1.0 | 0.50 | 0.55 |
| Marketplaces | €4,000 | 0.10 | 1.2 | 0.50 | 0.95 |

- Response: incremental orders = β · Hill(adstock(spend)); K and β are derived from the elasticity and the POAS.
  Marginal POAS = average POAS × elasticity (e.g. Shopping: €0.40 of gross profit for the next euro).
- Spend: quarterly budget steps (×0.55 to ×1.5), weekly noise (log-normal σ 0.30), two 3-week pushes a year,
  4% dark weeks, mild seasonality. This variation is what lets a media-mix model learn the curves.
- Baseline (organic, direct, brand): 650 new orders a week before seasonality, slowly growing.
- Resulting scale: ~€61M revenue and ~112k orders a year, €2.8M ad spend (4.5% of revenue), average order €548 (median €133).
- 25% of ad-driven orders are placed by existing customers (an ad platform still counts them as conversions).
- Last click: 12% of ad-driven orders end on an organic click; 4% of organic orders end on a Google Search ad and
  2.5% on a Shopping ad (they would have happened anyway); 2.5% of repeat orders end on a Search ad.
- Campaign budgets inside a channel follow a revenue-chasing (tROAS) logic: budget share = revenue share /
  ROAS tilt (big-ticket electrical ×1.35, hydraulics ×1.2 are allowed a higher ROAS; fittings and sealing ×0.8).

## Geo holdout
Google Search switched off in FR, ES and GB for 16 weeks from 6 Apr 2026. The orders that disappear are computed
from the true curve (counterfactual spend vs zero); the customers not acquired also miss their first repeat orders
inside the measurement window (test + 4 weeks), estimated by Monte Carlo on the true segment behaviour. Both give the
true lost gross profit (`true_params.json` → `geo_test`). The design was chosen with a power calculation (notebook,
part 3); the test metric is order gross profit winsorised at the 90th percentile, scaled back to full profit.
