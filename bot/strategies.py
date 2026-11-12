"""
strategies.py - the rule sets the bot can run, plus the benchmarks they must beat.

All rules look only at month-end closes up to and including the signal date.
Nothing here can see the future: the backtest calls `target(series, i)` with
the index of the signal day and the function only reads levels[0..i].

Rules (all published, none invented or tuned here):
  GEM      Dual momentum (Antonacci, 2014). If US stocks beat T-bills over 12
           months, hold whichever of US / world ex-US did better; otherwise
           hold Treasuries.
  TREND    Trend-filtered diversification (Faber, 2007). Equal slices of US,
           ex-US, Treasuries, real estate, commodities/gold; each slice is held
           only while its price is above its 10-month average, else T-bills.
  CORE     The bot's main strategy, built from the vault's own rules:
           diversified momentum (average of 3/6/12-month returns), keep the
           top 3 assets that also beat cash (absolute momentum = crash filter,
           see "02 - Momentum and Trend Following"), weight by inverse
           volatility, then scale the whole book to the volatility cap derived
           in "08 - Risk Limits and Escalation". Never levered (Kelly note:
           size below the optimum when estimates are noisy).
Benchmarks:
  SPY      100% US stocks, buy and hold.
  60/40    60% US stocks / 40% Treasuries, rebalanced monthly.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from .data import Series

MONTH = 21  # trading days


def month_end_indices(s: Series, today: Optional[str] = None) -> List[int]:
    """Indices of the last trading day of each month. The final bar counts as a
    month-end only if `today` (YYYY-MM-DD) is already in a later month."""
    out = []
    for i in range(len(s.dates) - 1):
        if s.dates[i][:7] != s.dates[i + 1][:7]:
            out.append(i)
    if today and s.dates and today[:7] > s.dates[-1][:7]:
        out.append(len(s.dates) - 1)
    return out


class MonthEnds:
    """Month-end lookup that only exposes month-ends at or before a given day."""

    def __init__(self, s: Series, today: Optional[str] = None):
        self.s = s
        self.me = month_end_indices(s, today)
        self.pos = {idx: k for k, idx in enumerate(self.me)}

    def back(self, i: int, months: int) -> Optional[int]:
        """Index of the month-end `months` before signal day i (i must be a month-end)."""
        k = self.pos.get(i)
        if k is None or k - months < 0:
            return None
        return self.me[k - months]


def total_return(s: Series, asset: str, i: int, j: Optional[int]) -> Optional[float]:
    if j is None:
        return None
    a, b = s.levels[asset][j], s.levels[asset][i]
    if a is None or b is None:
        return None
    return b / a - 1.0


def realized_vol(s: Series, asset: str, i: int, n: int = 63) -> Optional[float]:
    if i - n < 1 or s.levels[asset][i - n] is None:
        return None
    rs = [s.ret(asset, k) for k in range(i - n + 1, i + 1)]
    m = sum(rs) / n
    v = sum((r - m) ** 2 for r in rs) / (n - 1)
    return math.sqrt(v * 252)


def portfolio_vol(s: Series, weights: Dict[str, float], i: int, n: int = 63) -> Optional[float]:
    names = [a for a, w in weights.items() if w and a != "CASH"]
    if not names:
        return 0.0
    if i - n < 1:
        return None
    series = []
    for k in range(i - n + 1, i + 1):
        series.append(sum(weights[a] * s.ret(a, k) for a in names))
    m = sum(series) / n
    v = sum((r - m) ** 2 for r in series) / (n - 1)
    return math.sqrt(v * 252)


# ------------------------------------------------------------------ rules
class Strategy:
    name = "base"
    description = ""
    universe: List[str] = []

    def target(self, s: Series, me: MonthEnds, i: int) -> Optional[Dict[str, float]]:
        raise NotImplementedError

    def ready(self, s: Series, me: MonthEnds, i: int) -> bool:
        return self.target(s, me, i) is not None


class BuyHold(Strategy):
    def __init__(self, weights: Dict[str, float], name: str):
        self.weights = weights
        self.name = name
        self.description = " / ".join(f"{int(w*100)}% {a}" for a, w in weights.items())
        self.universe = list(weights)

    def target(self, s, me, i):
        if all(s.available(a, i) for a in self.weights):
            return dict(self.weights)
        return None


class GEM(Strategy):
    name = "GEM"
    description = "Dual momentum: best of US/ex-US if US beats T-bills over the lookback, else Treasuries"

    def __init__(self, lookback: int = 12):
        self.lookback = lookback
        self.universe = ["US", "INTL", "BONDS", "CASH"]
        if lookback != 12:
            self.name = f"GEM-{lookback}m"

    def target(self, s, me, i):
        j = me.back(i, self.lookback)
        us, intl, cash = (total_return(s, a, i, j) for a in ("US", "INTL", "CASH"))
        if None in (us, intl, cash) or not s.available("BONDS", i):
            return None
        if us > cash:
            return {"US": 1.0} if us >= intl else {"INTL": 1.0}
        return {"BONDS": 1.0}


class Trend(Strategy):
    name = "TREND"
    description = "Equal slices of 5 asset classes, each held only above its 10-month average"

    def __init__(self, sma_months: int = 10, real_assets=("COMMOD", "GOLD")):
        self.sma = sma_months
        self.real_assets = real_assets
        self.universe = ["US", "INTL", "BONDS", "REIT", "COMMOD", "GOLD", "CASH"]
        if sma_months != 10:
            self.name = f"TREND-{sma_months}m"

    def target(self, s, me, i):
        sleeves = ["US", "INTL", "BONDS", "REIT"]
        real = next((a for a in self.real_assets if s.available(a, i)
                     and me.back(i, self.sma) is not None
                     and s.levels[a][me.back(i, self.sma)] is not None), None)
        if real:
            sleeves.append(real)
        if me.back(i, self.sma) is None:
            return None
        w = {}
        for a in sleeves:
            pts = [me.back(i, k) for k in range(self.sma)]
            if any(p is None or s.levels[a][p] is None for p in pts):
                return None
            sma = sum(s.levels[a][p] for p in pts) / self.sma
            if s.levels[a][i] > sma:
                w[a] = w.get(a, 0) + 1 / len(sleeves)
            else:
                w["CASH"] = w.get("CASH", 0) + 1 / len(sleeves)
        return w


class Core(Strategy):
    name = "CORE"
    description = ("Top-3 diversified momentum (avg 3/6/12m), must beat T-bills, "
                   "inverse-vol weights, scaled to the vol cap, never levered")

    def __init__(self, top_k: int = 3, vol_cap: float = 0.119, lookbacks=(3, 6, 12),
                 universe=("US", "INTL", "BONDS", "LONGBONDS", "REIT", "GOLD", "COMMOD"),
                 max_weight: float = 0.60):
        self.max_weight = max_weight
        self.top_k = top_k
        self.vol_cap = vol_cap
        self.lookbacks = lookbacks
        self.universe = list(universe) + ["CASH"]
        self.risky = list(universe)
        tag = []
        if top_k != 3:
            tag.append(f"top{top_k}")
        if abs(vol_cap - 0.119) > 0.002:
            tag.append(f"vol{int(round(vol_cap*100))}")
        if tuple(lookbacks) != (3, 6, 12):
            tag.append("lb" + "-".join(map(str, lookbacks)))
        if tag:
            self.name = "CORE-" + "-".join(tag)

    def scores(self, s, me, i) -> Optional[Dict[str, float]]:
        out = {}
        for a in self.risky + ["CASH"]:
            rs = [total_return(s, a, i, me.back(i, m)) for m in self.lookbacks]
            if any(r is None for r in rs):
                continue
            out[a] = sum(rs) / len(rs)
        if "CASH" not in out or not any(a in out for a in ("US", "BONDS")):
            return None
        return out

    def target(self, s, me, i):
        sc = self.scores(s, me, i)
        if sc is None:
            return None
        cash = sc.pop("CASH")
        ranked = sorted(sc.items(), key=lambda kv: -kv[1])
        picks = [a for a, v in ranked[: self.top_k] if v > cash]
        if not picks:
            return {"CASH": 1.0}
        vols = {a: realized_vol(s, a, i) for a in picks}
        if any(v is None or v <= 0 for v in vols.values()):
            return None
        inv = {a: 1 / v for a, v in vols.items()}
        tot = sum(inv.values())
        # each pick gets its inverse-vol share of the sleeve it won (1/top_k each),
        # so unfilled sleeves stay in cash - fewer winners means less exposure
        sleeve = len(picks) / self.top_k
        w = {a: sleeve * x / tot for a, x in inv.items()}
        pv = portfolio_vol(s, w, i)
        if pv is None:
            return None
        scale = min(1.0, self.vol_cap / pv) if pv > 0 else 1.0
        w = {a: min(x * scale, self.max_weight) for a, x in w.items()}
        w["CASH"] = max(0.0, 1.0 - sum(w.values()))
        return w


class SpyTrend(Strategy):
    name = "SPY-TREND"
    description = "S&P 500 while it is above its 10-month average, otherwise Treasuries (Faber 2007 / Zweig)"
    universe = ["US", "BONDS", "CASH"]

    def __init__(self, sma_months: int = 10):
        self.sma = sma_months
        if sma_months != 10:
            self.name = f"SPY-TREND-{sma_months}m"

    def target(self, s, me, i):
        pts = [me.back(i, k) for k in range(self.sma)]
        if any(p is None for p in pts) or not s.available("BONDS", i):
            return None
        sma = sum(s.levels["US"][p] for p in pts) / self.sma
        return {"US": 1.0} if s.levels["US"][i] > sma else {"BONDS": 1.0}


def default_strategies(vol_cap: float = 0.119, max_weight: float = 0.60):
    core = Core(vol_cap=vol_cap, max_weight=max_weight)
    core.name = "CORE"
    return [
        core,
        GEM(),
        Trend(),
        BuyHold({"US": 0.6, "BONDS": 0.4}, "60/40"),
        BuyHold({"US": 1.0}, "SPY"),
        SpyTrend(),
    ]


def by_name(name: str, vol_cap: float = 0.119, max_weight: float = 0.60) -> Strategy:
    for st in default_strategies(vol_cap, max_weight):
        if st.name.upper() == name.upper():
            return st
    raise KeyError(name)
