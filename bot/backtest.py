"""
backtest.py - daily simulation with honest execution.

Timing (no look-ahead):
  * the signal is computed from the close of the LAST trading day of a month;
  * trades are filled at the close of the NEXT trading day (one full day of
    delay - the live bot trades at the next open, so this is slightly
    conservative);
  * every unit of turnover pays `cost_bps` (spread + commission + slippage),
    including moves into and out of the T-bill ETF;
  * weights drift with prices between rebalances;
  * cash earns the 13-week T-bill yield minus an ETF fee.

This file replaces the broken engine in Company/_build/portfolio_backtest.py
(where trading costs were overwritten and never charged).
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

from .data import Series
from .strategies import MonthEnds, Strategy


class Result:
    def __init__(self, name, dates, equity, weights_log, trades, turnover, costs_paid):
        self.name = name
        self.dates = dates            # list[str]
        self.equity = equity          # list[float], same length as dates
        self.weights_log = weights_log  # list[(date, weights)] at each rebalance
        self.trades = trades          # number of rebalances that traded
        self.turnover = turnover      # sum of one-way turnover
        self.costs_paid = costs_paid  # fraction of equity paid in costs (sum)

    # ---------------------------------------------------------- helpers
    def slice(self, start: str, end: str) -> "Result":
        ix = [k for k, d in enumerate(self.dates) if start <= d <= end]
        if not ix:
            return Result(self.name, [], [], [], 0, 0, 0)
        a, b = ix[0], ix[-1] + 1
        return Result(self.name, self.dates[a:b], self.equity[a:b], [], 0, 0, 0)

    def daily_returns(self) -> List[float]:
        e = self.equity
        return [e[k] / e[k - 1] - 1 for k in range(1, len(e))]

    def monthly(self) -> List[Tuple[str, float]]:
        out, last_e, last_m = [], None, None
        for d, e in zip(self.dates, self.equity):
            m = d[:7]
            if last_m is not None and m != last_m:
                out.append((last_m, last_close / last_e - 1))
                last_e = last_close
            if last_e is None:
                last_e = e
            last_m, last_close = m, e
        if last_m is not None and last_e:
            out.append((last_m, last_close / last_e - 1))
        return out

    def yearly(self) -> List[Tuple[str, float]]:
        out, start_e, cur_y, prev_e = [], None, None, None
        for d, e in zip(self.dates, self.equity):
            y = d[:4]
            if cur_y is None:
                cur_y, start_e = y, e
            elif y != cur_y:
                out.append((cur_y, prev_e / start_e - 1))
                cur_y, start_e = y, prev_e
            prev_e = e
        if cur_y:
            out.append((cur_y, prev_e / start_e - 1))
        return out


def apply_band(current: Dict[str, float], target: Dict[str, float], band: float) -> Dict[str, float]:
    """No-trade band: leave an asset alone unless its weight is off by more than
    `band` (or it must be fully sold/bought). Saves costs and - in Italy - tax,
    because every trim of a winning ETF realises a taxable gain.
    Any difference is absorbed by cash."""
    out = {}
    for a in set(current) | set(target):
        if a == "CASH":
            continue
        c, t = current.get(a, 0.0), target.get(a, 0.0)
        if t == 0.0 or c == 0.0 or abs(t - c) > band:
            out[a] = t
        else:
            out[a] = c
    risky = sum(out.values())
    if risky > 1.0:
        out = {a: x / risky for a, x in out.items()}
        risky = 1.0
    out["CASH"] = max(0.0, 1.0 - risky)
    return {a: x for a, x in out.items() if x > 1e-9}


ETC_ASSETS = {"GOLD"}   # exchange-traded commodities: gains are "redditi diversi" in Italy


class ItalianTax:
    """26% Italian tax, simplified but honest about the ETF trap:
    * a gain on selling a UCITS ETF is 'reddito di capitale' -> taxed, and it
      can NOT be reduced by earlier losses;
    * a loss on any ETF/ETC is 'reddito diverso' -> banked for 4 years and can
      only offset gains on ETCs (e.g. physical gold), stocks, bonds;
    * tax is charged immediately when a gain is realised (with a foreign broker
      you actually pay it the following June - charging it now is conservative).
    Average-cost basis per asset."""

    def __init__(self, rate: float = 0.26):
        self.rate = rate
        self.basis: Dict[str, float] = {}
        self.bank: List[Tuple[int, float]] = []   # (year, loss amount)
        self.paid = 0.0

    def _use_bank(self, gain: float, year: int) -> float:
        self.bank = [(y, a) for y, a in self.bank if year - y <= 4 and a > 0]
        rem = gain
        new = []
        for y, a in self.bank:
            use = min(a, rem)
            rem -= use
            if a - use > 1e-12:
                new.append((y, a - use))
        self.bank = new
        return rem

    def realise(self, asset: str, value_before: float, value_after: float, year: int) -> float:
        """Adjust basis for a trade; return tax owed now."""
        b = self.basis.get(asset, 0.0)
        tax = 0.0
        if value_after < value_before - 1e-12 and value_before > 0:
            f = (value_before - value_after) / value_before
            gain = f * (value_before - b)
            self.basis[asset] = b * (1 - f)
            if gain > 0:
                taxable = self._use_bank(gain, year) if asset in ETC_ASSETS else gain
                tax = self.rate * taxable
            elif gain < 0:
                self.bank.append((year, -gain))
        elif value_after > value_before:
            self.basis[asset] = b + (value_after - value_before)
        if value_after <= 1e-12:
            self.basis.pop(asset, None)
        self.paid += tax
        return tax

    def liquidation_tax(self, values: Dict[str, float], year: int) -> float:
        tax = 0.0
        for a, v in values.items():
            gain = v - self.basis.get(a, 0.0)
            if gain > 0:
                taxable = self._use_bank(gain, year) if a in ETC_ASSETS else gain
                tax += self.rate * taxable
        return tax


class USTax:
    """US taxable brokerage account, simplified:
    * FIFO lots; gains on lots held > 1 year are long-term, otherwise short-term;
    * each calendar year: short- and long-term results are netted against each
      other and against carried-forward losses; net losses carry forward forever
      (the $3,000/yr offset against salary is ignored - conservative);
    * dividends and interest are taxed every year (stock dividends at the
      long-term rate as 'qualified', bond/cash/REIT/commodity income at the
      short-term = ordinary rate);
    * tax is paid on the first trading day of the next year.
    Wash-sale rules are ignored (the bot does not sell to harvest losses)."""
    QUALIFIED = {"US", "INTL"}

    def __init__(self, st_rate: float = 0.29, lt_rate: float = 0.20):
        self.st_rate, self.lt_rate = st_rate, lt_rate
        self.lots: Dict[str, List[list]] = {}     # asset -> [[date, units, cost], ...]
        self.year_st = self.year_lt = 0.0
        self.year_income_q = self.year_income_o = 0.0
        self.carry = 0.0                          # carried-forward net capital loss (>= 0)
        self.paid = 0.0

    def buy(self, asset, value, price, d):
        if value > 1e-12 and price:
            self.lots.setdefault(asset, []).append([d, value / price, value])

    def sell(self, asset, value, price, d):
        units = value / price if price else 0.0
        lots = self.lots.get(asset, [])
        while units > 1e-12 and lots:
            lot = lots[0]
            take = min(units, lot[1])
            cost = lot[2] * take / lot[1]
            gain = take * price - cost
            if _days(lot[0], d) > 365:
                self.year_lt += gain
            else:
                self.year_st += gain
            lot[1] -= take
            lot[2] -= cost
            units -= take
            if lot[1] <= 1e-12:
                lots.pop(0)

    def trade(self, asset, value_before, value_after, price, d):
        if value_after > value_before:
            self.buy(asset, value_after - value_before, price, d)
        elif value_after < value_before:
            self.sell(asset, value_before - value_after, price, d)
        return 0.0                                  # paid at year end

    def income(self, asset, amount):
        if amount <= 0:
            return
        if asset in self.QUALIFIED:
            self.year_income_q += amount
        else:
            self.year_income_o += amount
        # reinvested income raises the cost basis of what is held
        lots = self.lots.get(asset)
        if lots:
            tot = sum(l[1] for l in lots)
            for l in lots:
                l[2] += amount * l[1] / tot

    def year_end(self) -> float:
        st, lt = self.year_st, self.year_lt
        # net short against long
        if st < 0 < lt:
            lt, st = lt + st, 0.0
        elif lt < 0 < st:
            st, lt = st + lt, 0.0
        # apply carried losses, short-term first
        for name in ("st", "lt"):
            val = st if name == "st" else lt
            if val > 0 and self.carry > 0:
                use = min(val, self.carry)
                val -= use
                self.carry -= use
            if name == "st":
                st = val
            else:
                lt = val
        net = st + lt
        if net < 0:
            self.carry += -net
            st = lt = 0.0
        tax = self.st_rate * max(st, 0) + self.lt_rate * max(lt, 0) \
            + self.lt_rate * self.year_income_q + self.st_rate * self.year_income_o
        self.year_st = self.year_lt = self.year_income_q = self.year_income_o = 0.0
        self.paid += tax
        return tax

    def liquidation_tax(self, values: Dict[str, float], prices: Dict[str, float], d: str) -> float:
        for a, v in values.items():
            if v > 0 and prices.get(a):
                self.sell(a, v, prices[a], d)
        return self.year_end()


def crash_brake_hit(s: Series, asset: str, i: int, n: int) -> bool:
    lv = s.levels[asset]
    if i - n < 0 or lv[i - n] is None:
        return False
    avg = sum(lv[k] for k in range(i - n + 1, i + 1)) / n
    return lv[i] < avg


def run(s: Series, strat: Strategy, start: str = "1997-06-01", end: Optional[str] = None,
        cost_bps: float = 10.0, min_trade: float = 0.02, capital: float = 1.0,
        tax: Optional["ItalianTax"] = None, band: float = 0.0, brake: int = 0) -> Result:
    me = MonthEnds(s)
    month_ends = set(me.me)
    n = len(s.dates)
    end = end or s.dates[-1]
    i0 = next(i for i, d in enumerate(s.dates) if d >= start)
    # wait until the strategy can produce a signal
    first_sig = next((i for i in me.me if i >= i0 - 1 and strat.target(s, me, i) is not None), None)
    if first_sig is None:
        raise ValueError(f"{strat.name}: never ready")
    w: Dict[str, float] = {"CASH": 1.0}
    equity = capital
    us_tax = isinstance(tax, USTax)
    if tax is not None and not us_tax:
        tax.basis["CASH"] = capital
    prev_date = None
    dates, eq, wlog = [], [], []
    pending: Optional[Dict[str, float]] = None
    pending_from: Optional[int] = None
    trades = 0
    turnover_sum = 0.0
    costs = 0.0
    started = False
    for i in range(first_sig, n):
        d = s.dates[i]
        if d > end:
            break
        if started:
            if us_tax:
                if prev_date and d[:4] != prev_date[:4]:
                    equity -= tax.year_end()            # last year's bill
                for a, wt in w.items():
                    tax.income(a, wt * equity * s.income(a, i))
            # 1) earn today's returns on yesterday's weights
            gross = sum(wt * s.ret(a, i) for a, wt in w.items())
            equity *= 1 + gross
            if 1 + gross > 0:
                w = {a: wt * (1 + s.ret(a, i)) / (1 + gross) for a, wt in w.items()}
            # 2) execute yesterday's signal at today's close
            if pending is not None and pending_from == i - 1:
                if band > 0 and wlog:
                    pending = apply_band(w, pending, band)
                assets = set(w) | set(pending)
                turn = sum(abs(pending.get(a, 0) - w.get(a, 0)) for a in assets)
                if turn >= min_trade or not wlog:
                    c = turn * cost_bps / 10000.0
                    equity *= 1 - c
                    costs += c
                    turnover_sum += turn / 2
                    trades += 1
                    if us_tax:
                        if not wlog:
                            tax.buy("CASH", w.get("CASH", 0) * equity, s.levels["CASH"][i], d)
                        for a in assets:
                            tax.trade(a, w.get(a, 0) * equity, pending.get(a, 0) * equity,
                                      s.levels[a][i], d)
                    elif tax is not None:
                        owed = 0.0
                        yr = int(d[:4])
                        for a in assets:
                            owed += tax.realise(a, w.get(a, 0) * equity, pending.get(a, 0) * equity, yr)
                        equity -= owed
                    w = {a: x for a, x in pending.items() if x > 1e-9}
                    wlog.append((d, dict(w)))
                pending = None
        # 2b) crash brake: a held risky asset that closes below its `brake`-day average
        #     is sold to cash tomorrow; it can only come back at the next month-end
        if brake and started and pending is None and i not in month_ends:
            hit = [a for a, x in w.items() if a != "CASH" and x > 0.001 and crash_brake_hit(s, a, i, brake)]
            if hit:
                pending = {a: x for a, x in w.items() if a not in hit}
                pending["CASH"] = pending.get("CASH", 0.0) + sum(w[a] for a in hit)
                pending_from = i
        # 3) on a month-end, compute tomorrow's target from today's close
        if i in month_ends:
            tgt = strat.target(s, me, i)
            if tgt is not None:
                tot = sum(tgt.values())
                pending = {a: x / tot for a, x in tgt.items()}
                pending_from = i
                if not started:
                    started = True
        if started:
            dates.append(d)
            eq.append(equity)
            prev_date = d
    res = Result(strat.name, dates, eq, wlog, trades, turnover_sum, costs)
    if tax is not None and eq:
        res.tax_paid = tax.paid                 # paid during the run (before cashing out)
        vals = {a: x * eq[-1] for a, x in w.items()}
        if us_tax:
            last = len(dates) - 1 + s.idx[dates[0]]
            res.liquidation_tax = tax.liquidation_tax(vals, {a: s.levels[a][last] for a in vals}, dates[-1])
        else:
            res.liquidation_tax = tax.liquidation_tax(vals, int(dates[-1][:4]))
        res.after_tax_final = eq[-1] - res.liquidation_tax
    return res


# ------------------------------------------------------------------ metrics
def metrics(r: Result, cash: Optional[Result] = None) -> Dict[str, float]:
    if len(r.equity) < 30:
        return {}
    e = r.equity
    years = len(e) / 252.0
    cagr = (e[-1] / e[0]) ** (1 / years) - 1
    dr = r.daily_returns()
    mu = sum(dr) / len(dr)
    sd = math.sqrt(sum((x - mu) ** 2 for x in dr) / (len(dr) - 1))
    vol = sd * math.sqrt(252)
    # excess over cash for Sharpe
    if cash is not None and len(cash.equity) == len(e):
        cr = cash.daily_returns()
        ex = [a - b for a, b in zip(dr, cr)]
    else:
        ex = dr
    mex = sum(ex) / len(ex)
    sdx = math.sqrt(sum((x - mex) ** 2 for x in ex) / (len(ex) - 1))
    sharpe = mex / sdx * math.sqrt(252) if sdx else 0.0
    down = [x for x in ex if x < 0]
    dd_sd = math.sqrt(sum(x * x for x in down) / len(ex)) if down else 0
    sortino = mex / dd_sd * math.sqrt(252) if dd_sd else 0.0
    peak, mdd, peak_d, trough_d, cur_peak_d = e[0], 0.0, r.dates[0], r.dates[0], r.dates[0]
    under_start, longest, longest_span = None, 0, ("", "")
    for d, x in zip(r.dates, e):
        if x >= peak:
            if under_start is not None:
                days = _days(under_start, d)
                if days > longest:
                    longest, longest_span = days, (under_start, d)
            peak, cur_peak_d, under_start = x, d, None
        else:
            if under_start is None:
                under_start = cur_peak_d
            dd = x / peak - 1
            if dd < mdd:
                mdd, peak_d, trough_d = dd, cur_peak_d, d
    if under_start is not None:
        days = _days(under_start, r.dates[-1])
        if days > longest:
            longest, longest_span = days, (under_start, r.dates[-1] + " (still under)")
    mon = [x for _, x in r.monthly()]
    yrs = r.yearly()
    full_years = [x for y, x in yrs if y not in (r.dates[0][:4], r.dates[-1][:4])]
    return {
        "start": r.dates[0], "end": r.dates[-1], "years": years,
        "cagr": cagr, "vol": vol, "sharpe": sharpe, "sortino": sortino,
        "max_dd": mdd, "dd_peak": peak_d, "dd_trough": trough_d,
        "longest_underwater_days": longest, "underwater_span": longest_span,
        "calmar": cagr / abs(mdd) if mdd < 0 else float("inf"),
        "worst_month": min(mon) if mon else 0, "best_month": max(mon) if mon else 0,
        "pct_up_months": sum(1 for x in mon if x > 0) / len(mon) if mon else 0,
        "worst_year": min(full_years) if full_years else 0,
        "best_year": max(full_years) if full_years else 0,
        "final_multiple": e[-1] / e[0],
        "trades_per_year": r.trades / years if r.trades else 0,
        "turnover_per_year": r.turnover / years if r.turnover else 0,
        "cost_drag_per_year": r.costs_paid / years if r.costs_paid else 0,
    }


def _days(a: str, b: str) -> int:
    from datetime import date
    return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days


def window_return(r: Result, start: str, end: str) -> Optional[float]:
    sl = r.slice(start, end)
    if len(sl.equity) < 2:
        return None
    return sl.equity[-1] / sl.equity[0] - 1


def window_max_dd(r: Result, start: str, end: str) -> Optional[float]:
    sl = r.slice(start, end)
    if len(sl.equity) < 2:
        return None
    peak, mdd = sl.equity[0], 0.0
    for x in sl.equity:
        peak = max(peak, x)
        mdd = min(mdd, x / peak - 1)
    return mdd


def block_bootstrap_beat(a: Result, b: Result, n_sims: int = 2000, block: int = 12,
                         seed: int = 7) -> Dict[str, float]:
    """Probability that strategy `a` beats `b` on compounded return over a
    random history of the same length, resampling 12-month blocks of monthly
    returns (keeps crashes and their recoveries together)."""
    ma = dict(a.monthly())
    mb = dict(b.monthly())
    months = [m for m in ma if m in mb]
    ra = [ma[m] for m in months]
    rb = [mb[m] for m in months]
    n = len(months)
    rng = random.Random(seed)
    wins, diffs = 0, []
    for _ in range(n_sims):
        ga = gb = 1.0
        k = 0
        while k < n:
            st = rng.randrange(0, n - block)
            for j in range(st, st + block):
                if k >= n:
                    break
                ga *= 1 + ra[j]
                gb *= 1 + rb[j]
                k += 1
        yrs = n / 12
        da = ga ** (1 / yrs) - gb ** (1 / yrs)
        diffs.append(da)
        wins += da > 0
    diffs.sort()
    return {"p_beat": wins / n_sims, "cagr_diff_p5": diffs[int(0.05 * n_sims)],
            "cagr_diff_p50": diffs[n_sims // 2], "cagr_diff_p95": diffs[int(0.95 * n_sims)]}


def bootstrap_drawdowns(a: Result, n_sims: int = 2000, block: int = 12, seed: int = 11,
                        horizon_months: int = 120) -> Dict[str, float]:
    """Distribution of the worst drawdown over a 10-year stretch, resampled."""
    ra = [x for _, x in a.monthly()]
    n = len(ra)
    rng = random.Random(seed)
    worst = []
    for _ in range(n_sims):
        g = peak = 1.0
        mdd = 0.0
        k = 0
        while k < horizon_months:
            st = rng.randrange(0, n - block)
            for j in range(st, st + block):
                if k >= horizon_months:
                    break
                g *= 1 + ra[j]
                peak = max(peak, g)
                mdd = min(mdd, g / peak - 1)
                k += 1
        worst.append(mdd)
    worst.sort()
    return {"median": worst[n_sims // 2], "p10": worst[int(0.10 * n_sims)],
            "p5": worst[int(0.05 * n_sims)], "p1": worst[int(0.01 * n_sims)]}
