"""The statistical methods used in the notebook, in one place, written to be read line by line.

1. Markov attribution (removal effect) + bootstrap confidence intervals
2. Power: sample size of an A/B test, minimum detectable effect of a geo test
3. Media-mix model: adstock (carry-over) + Hill (saturation), fitted with scipy
4. Budget reallocation under a budget constraint
"""
import numpy as np
import pandas as pd
from scipy import optimize, signal, stats

# ============================================================== 1. Markov attribution


def transition_counts(paths: pd.DataFrame):
    """For every path, count its transitions Start -> c1 -> ... -> Conversion/Null.
    Returns (states, pair_index, unit_matrix, unit_weights):
    one 'unit' = one path that converted, or the same path that did not convert;
    unit_matrix[u, j] = how many times unit u makes transition j (pair_index[j] = (from, to))."""
    pairs, rows, weights = {}, [], []
    for path, conv, null in paths[["path", "conversions", "non_conversions"]].itertuples(index=False):
        steps = ["Start"] + path.split(" > ")
        for outcome, n in (("Conversion", conv), ("Null", null)):
            if n <= 0:
                continue
            seq = steps + [outcome]
            row = {}
            for a, b in zip(seq[:-1], seq[1:]):
                j = pairs.setdefault((a, b), len(pairs))
                row[j] = row.get(j, 0) + 1
            rows.append(row)
            weights.append(n)
    M = np.zeros((len(rows), len(pairs)))
    for u, row in enumerate(rows):
        for j, k in row.items():
            M[u, j] = k
    states = sorted({s for p in pairs for s in p} - {"Start", "Conversion", "Null"})
    return states, list(pairs), M, np.array(weights, dtype=float)


def removal_effects(channels, pair_index, pair_counts):
    """Markov chain from transition counts -> conversion probability, then the removal effect of each
    channel = share of conversions lost if the channel disappears (whoever reaches it is lost)."""
    states = ["Start"] + list(channels) + ["Conversion", "Null"]
    idx = {s: i for i, s in enumerate(states)}
    P = np.zeros((len(states), len(states)))
    for (a, b), n in zip(pair_index, pair_counts):
        P[idx[a], idx[b]] += n
    P[idx["Conversion"], idx["Conversion"]] = P[idx["Null"], idx["Null"]] = 1   # absorbing states
    P = P / P.sum(axis=1, keepdims=True)
    transient = [idx["Start"]] + [idx[c] for c in channels]

    def p_conv(Pm):
        # absorbing chain: B = (I - Q)^-1 R gives the probability of ending in Conversion
        Q = Pm[np.ix_(transient, transient)]
        R = Pm[np.ix_(transient, [idx["Conversion"]])]
        return np.linalg.solve(np.eye(len(transient)) - Q, R)[0, 0]

    base = p_conv(P)
    eff = {}
    for c in channels:
        Pr = P.copy()
        Pr[idx[c], :] = 0
        Pr[idx[c], idx["Null"]] = 1
        eff[c] = 1 - p_conv(Pr) / base
    eff = pd.Series(eff)
    return base, eff, eff / eff.sum()


def markov_with_bootstrap(paths: pd.DataFrame, n_boot=500, seed=42):
    """Markov shares on the observed paths + n_boot bootstrap replicates.
    Bootstrap = draw the same number of users again, with replacement (multinomial on the units),
    rebuild the transition counts and the Markov shares. The spread of the replicates = sampling error."""
    channels, pair_index, M, w = transition_counts(paths)
    base, eff, share = removal_effects(channels, pair_index, w @ M)
    rng = np.random.default_rng(seed)
    n, p = int(w.sum()), w / w.sum()
    boot = []
    for _ in range(n_boot):
        wb = rng.multinomial(n, p).astype(float)
        boot.append(removal_effects(channels, pair_index, wb @ M)[2])
    return base, eff, share, pd.DataFrame(boot)


def last_click_with_bootstrap(last_click: pd.Series, n_boot=500, seed=42):
    """Last-click share of conversions per channel and its bootstrap replicates (multinomial)."""
    share = last_click / last_click.sum()
    rng = np.random.default_rng(seed)
    boot = rng.multinomial(int(last_click.sum()), share.values, size=n_boot) / last_click.sum()
    return share, pd.DataFrame(boot, columns=share.index)


# ============================================================== 2. Power


def n_per_arm(p0, rel_mde, alpha=0.05, power=0.8):
    """Users per arm to detect a relative lift `rel_mde` on a conversion rate p0
    (two-sided z-test for two proportions)."""
    p1 = p0 * (1 + rel_mde)
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    pbar = (p0 + p1) / 2
    num = (z_a * np.sqrt(2 * pbar * (1 - pbar)) + z_b * np.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
    return int(np.ceil(num / (p1 - p0) ** 2))


def ar1(x):
    """Lag-1 autocorrelation (weekly series are not independent: it inflates the variance)."""
    x = np.asarray(x) - np.mean(x)
    return float(np.sum(x[1:] * x[:-1]) / np.sum(x * x))


def geo_mde(sd_weekly, n_pre, n_test, rho=0.0, alpha=0.05, power=0.8):
    """Minimum detectable effect (relative) of a pre/post test-vs-control geo test.
    sd_weekly = std of the weekly log-ratio test/control (noise), rho = its autocorrelation.
    SE of (mean test period - mean pre period) = sd * sqrt(1/n_pre + 1/n_test), inflated by the
    autocorrelation factor sqrt((1+rho)/(1-rho))."""
    infl = np.sqrt((1 + max(rho, 0)) / (1 - max(rho, 0)))
    se = sd_weekly * np.sqrt(1 / n_pre + 1 / n_test) * infl
    return (stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) * se


# ============================================================== 3. Media-mix model


def adstock(x, lam):
    """Geometric carry-over, normalised: a constant spend x gives an adstocked value of x.
    carry[t] = x[t] + lam * carry[t-1]; adstock = (1 - lam) * carry. lfilter runs this recursion in C."""
    return (1 - lam) * signal.lfilter([1.0], [1.0, -lam], np.asarray(x, dtype=float))


def hill(x, K, S):
    """Saturation: 0 at no spend, 0.5 at spend K (half-saturation), towards 1 at high spend; S = shape."""
    x = np.maximum(x, 0)
    return x ** S / (x ** S + K ** S)


class MMM:
    """y[k,t] = a_k * (1 + g * (season[k,t] - 1)) + Z[k,t] @ gamma + sum_c beta_c * Hill(adstock(x[c,k,t], lam_c), K_c, S_c)

    y = weekly gross profit of country k divided by its size (its share of total gross profit), in kEUR;
    x = weekly spend divided by the same size, in kEUR. Dividing by size lets the 5 countries share
    one response curve per channel (5 x more data to learn it). Z = linear controls (trend, active
    customer base that drives repeat orders). Fitted by penalised non-linear least squares."""

    def __init__(self, channels):
        self.channels = list(channels)

    def _unpack(self, theta, n_k):
        C = len(self.channels)
        beta, lam, K, S = theta[:C], theta[C:2 * C], theta[2 * C:3 * C], theta[3 * C:4 * C]
        a, g, gamma = theta[4 * C:4 * C + n_k], theta[4 * C + n_k], theta[4 * C + n_k + 1:]
        return beta, lam, K, S, a, g, gamma

    def media(self, X, lam, K, S, beta, groups):
        """Contribution of each channel, row by row (adstock runs inside each country)."""
        out = np.zeros_like(X)
        for gidx in groups:
            for c in range(X.shape[1]):
                out[gidx, c] = beta[c] * hill(adstock(X[gidx, c], lam[c]), K[c], S[c])
        return out

    def predict(self, theta, X, season, Z, kidx, groups):
        beta, lam, K, S, a, g, gamma = self._unpack(theta, len(groups))
        base = a[kidx] * (1 + g * (season - 1)) + Z @ gamma
        return base + self.media(X, lam, K, S, beta, groups).sum(axis=1)

    def fit(self, X, y, season, Z, kidx, theta0=None, sigma=None, calib=None,
            lam_prior=(0.3, 0.2), s_prior=(1.2, 0.3), max_nfev=1500):
        """Penalised least squares (a light Bayesian MMM, like Robyn / Meridian do with priors):
        - weak priors: carry-over lam ~ N(0.3, 0.2), Hill shape S ~ N(1.2, 0.3);
        - K (half-saturation) kept between 0.3x and 3x the average spend: outside the observed spend
          range the data cannot tell where saturation starts;
        - calib = {channel: (poas, sd)}: average POAS at current spend measured by an experiment
          (e.g. the geo holdout) pulls that channel's curve towards the experiment (calibration).
        sigma = typical weekly residual, used to weigh each prior like observations."""
        groups = [np.where(kidx == k)[0] for k in range(kidx.max() + 1)]
        C, n_k = len(self.channels), len(groups)
        xm = X.mean(axis=0)
        if theta0 is None:
            theta0 = np.r_[np.full(C, y.mean() * 0.1), np.full(C, 0.3), xm, np.full(C, 1.2),
                           np.full(n_k, y.mean() * 0.6), 0.5, np.zeros(Z.shape[1])]
        q = Z.shape[1]
        lo = np.r_[np.zeros(C), np.zeros(C), 0.3 * xm, np.full(C, 0.5), np.full(n_k, -np.inf), -2, np.full(q, -np.inf)]
        hi = np.r_[np.full(C, np.inf), np.full(C, 0.85), 3.0 * xm, np.full(C, 3.0), np.full(n_k, np.inf), 3, np.full(q, np.inf)]
        sigma = np.std(y) * 0.15 if sigma is None else sigma
        calib = calib or {}

        def residuals(th):
            r = self.predict(th, X, season, Z, kidx, groups) - y
            beta, lam, K, S = th[:C], th[C:2 * C], th[2 * C:3 * C], th[3 * C:4 * C]
            pri = [(lam - lam_prior[0]) / lam_prior[1], (S - s_prior[0]) / s_prior[1]]
            for ch, (poas, sd) in calib.items():
                c = self.channels.index(ch)
                pri.append(np.atleast_1d((beta[c] * hill(xm[c], K[c], S[c]) / xm[c] - poas) / sd))
            return np.r_[r, np.concatenate(pri) * sigma]

        res = optimize.least_squares(residuals, np.clip(theta0, lo + 1e-9, hi - 1e-9), bounds=(lo, hi),
                                     loss="soft_l1", f_scale=sigma, x_scale="jac", max_nfev=max_nfev)
        self.theta, self.groups, self.res = res.x, groups, res
        self.fitted = self.predict(res.x, X, season, Z, kidx, groups)
        return self

    def params(self, theta=None):
        beta, lam, K, S, a, g, gamma = self._unpack(self.theta if theta is None else theta, len(self.groups))
        return pd.DataFrame({"beta": beta, "lam": lam, "K": K, "S": S}, index=self.channels)


def response(params: pd.DataFrame, channel, spend_k):
    """Steady-state weekly gross profit (kEUR) from a constant weekly spend (kEUR) on one channel."""
    p = params.loc[channel]
    return p.beta * hill(np.asarray(spend_k, dtype=float), p.K, p.S)


def marginal(params: pd.DataFrame, channel, spend_k, h=1e-3):
    """Marginal POAS: extra gross profit from one more euro at this spend level (numerical derivative)."""
    return (response(params, channel, np.asarray(spend_k) + h) - response(params, channel, np.asarray(spend_k) - h)) / (2 * h)


# ============================================================== 4. Budget reallocation


def reallocate(params: pd.DataFrame, current_k: pd.Series, lo=0.5, hi=2.0, total=None):
    """Maximise total gross profit with the same total budget (or `total`), each channel kept between
    lo x and hi x its current spend (guardrails: a model is not trusted far outside the data)."""
    ch = list(current_k.index)
    total = current_k.sum() if total is None else total
    f = lambda x: -sum(response(params, c, xi) for c, xi in zip(ch, x))
    cons = [{"type": "eq", "fun": lambda x: x.sum() - total}]
    bnds = [(lo * current_k[c], hi * current_k[c]) for c in ch]
    r = optimize.minimize(f, current_k.values, method="SLSQP", bounds=bnds, constraints=cons)
    return pd.Series(r.x, index=ch)


def profit_max_total(params: pd.DataFrame, current_k: pd.Series, hi=3.0):
    """Budget per channel that maximises gross profit minus ad spend (each extra euro must return
    at least one euro of gross profit): the profit-maximising total, not a ROAS target."""
    ch = list(current_k.index)
    f = lambda x: -(sum(response(params, c, xi) for c, xi in zip(ch, x)) - x.sum())
    bnds = [(0, hi * current_k[c]) for c in ch]
    r = optimize.minimize(f, current_k.values, method="L-BFGS-B", bounds=bnds)
    return pd.Series(r.x, index=ch)
