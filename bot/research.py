"""
research.py - the full honest evaluation the bot publishes into the vault.

Everything the vault's "Guide - Backtesting" and Risk Committee notes ask for:
 * 1997-2026 incl. dot-com, 2008, 2020, 2022, 2025 crashes
 * costs, next-day execution, Italian tax, EUR view
 * crash-by-crash and year-by-year tables (the ups AND the downs)
 * parameter-neighbourhood robustness (is it one lucky setting?)
 * walk-forward selection using only past data
 * cost sensitivity, first half vs second half
 * block bootstrap: probability the edge is luck; drawdown you should expect
"""
from __future__ import annotations

import csv
from datetime import date
from typing import Dict, List, Optional

from . import backtest as bt
from . import strategies as st
from .data import ROOT, Series

START = "1997-06-01"

CRASHES = [
    ("Asia / LTCM 1998", "1998-07-17", "1998-10-08"),
    ("Dot-com bust 2000-02", "2000-03-24", "2002-10-09"),
    ("Financial crisis 2007-09", "2007-10-09", "2009-03-09"),
    ("Euro debt crisis 2011", "2011-04-29", "2011-10-03"),
    ("China / oil 2015-16", "2015-05-21", "2016-02-11"),
    ("Q4 2018 sell-off", "2018-09-20", "2018-12-24"),
    ("COVID crash 2020", "2020-02-19", "2020-03-23"),
    ("Inflation bear 2022", "2022-01-03", "2022-10-12"),
    ("Tariff crash 2025", "2025-02-19", "2025-04-08"),
]
RALLIES = [
    ("Dot-com mania 1997-2000", "1997-06-02", "2000-03-24"),
    ("Recovery 2002-07", "2002-10-09", "2007-10-09"),
    ("Post-crisis bull 2009-20", "2009-03-09", "2020-02-19"),
    ("COVID rebound 2020-21", "2020-03-23", "2022-01-03"),
    ("AI bull 2022-26", "2022-10-12", "2026-12-31"),
]


def load_eurusd() -> Dict[str, float]:
    p = ROOT / "data" / "eurusd.csv"
    if not p.exists():
        return {}
    with open(p) as f:
        return {r["date"]: float(r["eurusd"]) for r in csv.DictReader(f)}


def to_eur(r: bt.Result, fx: Dict[str, float], start: str = "2004-01-02") -> Optional[bt.Result]:
    if not fx:
        return None
    ks = sorted(fx)
    import bisect
    dates, eq = [], []
    for d, e in zip(r.dates, r.equity):
        if d < start:
            continue
        j = bisect.bisect_right(ks, d) - 1
        if j < 0:
            continue
        dates.append(d)
        eq.append(e / fx[ks[j]])
    return bt.Result(r.name + " (EUR)", dates, eq, [], 0, 0, 0)


class WalkForwardCore(st.Strategy):
    """Every January, pick the CORE settings with the best return/drawdown over
    ALL data before that January, then trade them for the next 12 months.
    Tests whether the method of choosing settings works out of sample."""
    name = "CORE-walkforward"
    description = "CORE with settings re-chosen each January from past data only"

    def __init__(self, s: Series, vol_cap: float, max_weight: float = 0.60):
        self.cands = [st.Core(top_k=k, vol_cap=vol_cap, lookbacks=lb, max_weight=max_weight)
                      for k in (2, 3, 4) for lb in ((1, 3, 6), (3, 6, 12), (6, 12), (12,))]
        self.universe = self.cands[0].universe
        self.runs = {c.name: bt.run(s, c, start="1990-01-01") for c in self.cands}
        self.choice: Dict[str, st.Core] = {}
        self.log: List[tuple] = []

    def _pick(self, d: str) -> st.Core:
        y = d[:4]
        if y not in self.choice:
            best, best_score = self.cands[4], None  # default = (3,6,12) top-3 until 5y of history
            for c in self.cands:
                r = self.runs[c.name]
                past = [k for k, x in enumerate(r.dates) if x < f"{y}-01-01"]
                if len(past) < 252 * 5:
                    continue
                sl = bt.Result(c.name, r.dates[: past[-1] + 1], r.equity[: past[-1] + 1], [], 0, 0, 0)
                m = bt.metrics(sl)
                score = m["calmar"]
                if best_score is None or score > best_score:
                    best, best_score = c, score
            self.choice[y] = best
            self.log.append((y, best.name))
        return self.choice[y]

    def target(self, s, me, i):
        return self._pick(s.dates[i]).target(s, me, i)


def evaluate(s: Series, vol_cap: float, cost_bps: float = 10.0, band: float = 0.10,
             bootstrap_sims: int = 2000, max_weight: float = 0.60,
             us_rates=(0.29, 0.20)) -> dict:
    core = st.Core(vol_cap=vol_cap, max_weight=max_weight)
    core.name = "CORE"
    lineup = [core, st.GEM(), st.Trend(), st.SpyTrend(),
              st.BuyHold({"US": 0.6, "BONDS": 0.4}, "60/40"), st.BuyHold({"US": 1.0}, "SPY")]
    cash = bt.run(s, st.BuyHold({"CASH": 1.0}, "CASH"), start=START)
    out: dict = {"generated": date.today().isoformat(), "start": START, "end": s.dates[-1],
                 "us_rates": us_rates,
                 "cost_bps": cost_bps, "band": band, "vol_cap": vol_cap, "strategies": {}}
    runs = {}
    for x in lineup:
        kw = {"band": band} if x.name == "CORE" else {}
        r = bt.run(s, x, start=START, cost_bps=cost_bps, **kw)
        runs[x.name] = r
        c = cash.slice(r.dates[0], r.dates[-1])
        m = bt.metrics(r, c if len(c.equity) == len(r.equity) else None)
        yrs = len(r.equity) / 252
        rt = bt.run(s, x, start=START, cost_bps=cost_bps, tax=bt.ItalianTax(), **kw)
        m["after_tax_cagr"] = rt.after_tax_final ** (1 / yrs) - 1          # Italy
        m["after_tax_multiple"] = rt.after_tax_final
        ru = bt.run(s, x, start=START, cost_bps=cost_bps, tax=bt.USTax(*us_rates), **kw)
        m["after_tax_us_cagr"] = ru.after_tax_final ** (1 / yrs) - 1
        m["after_tax_us_multiple"] = ru.after_tax_final
        m["description"] = x.description
        out["strategies"][x.name] = m
    out["runs"] = runs  # not serialised; used for charts/tables

    # ups and downs
    out["crashes"] = [{"name": n, "start": a, "end": b,
                       **{k: bt.window_return(r, a, b) for k, r in runs.items()}}
                      for n, a, b in CRASHES]
    out["rallies"] = [{"name": n, "start": a, "end": b,
                       **{k: bt.window_return(r, a, b) for k, r in runs.items()}}
                      for n, a, b in RALLIES]
    years = {}
    for k, r in runs.items():
        for y, x in r.yearly():
            years.setdefault(y, {})[k] = x
    out["years"] = years

    # first half / second half
    mid = "2012-01-01"
    out["halves"] = {}
    for k, r in runs.items():
        a = bt.metrics(r.slice(START, "2011-12-31"))
        b = bt.metrics(r.slice(mid, "2099-12-31"))
        out["halves"][k] = {"first": (a["cagr"], a["max_dd"]), "second": (b["cagr"], b["max_dd"])}

    # cost sensitivity for CORE
    out["cost_sensitivity"] = {}
    for c in (0, 10, 25, 50):
        r = bt.run(s, core, start=START, cost_bps=c, band=band)
        m = bt.metrics(r)
        out["cost_sensitivity"][c] = (m["cagr"], m["max_dd"])

    # robustness grid (neighbourhood of the chosen settings)
    grid = []
    for k in (2, 3, 4):
        for lb in ((1, 3, 6), (3, 6, 12), (6, 12), (12,)):
            for vc in (vol_cap * 0.75, vol_cap, vol_cap * 1.25):
                c = st.Core(top_k=k, vol_cap=vc, lookbacks=lb, max_weight=max_weight)
                m = bt.metrics(bt.run(s, c, start=START, cost_bps=cost_bps, band=band))
                grid.append({"top_k": k, "lookbacks": "/".join(map(str, lb)), "vol_cap": vc,
                             "cagr": m["cagr"], "max_dd": m["max_dd"], "sharpe": m["sharpe"]})
    out["grid"] = grid

    # walk-forward
    wf = WalkForwardCore(s, vol_cap, max_weight)
    rwf = bt.run(s, wf, start=START, cost_bps=cost_bps, band=band)
    mwf = bt.metrics(rwf)
    out["walk_forward"] = {"cagr": mwf["cagr"], "max_dd": mwf["max_dd"], "sharpe": mwf["sharpe"],
                           "choices": wf.log}
    runs["CORE-walkforward"] = rwf

    # bootstrap
    out["bootstrap_vs_6040"] = bt.block_bootstrap_beat(runs["CORE"], runs["60/40"], n_sims=bootstrap_sims)
    out["bootstrap_vs_spy"] = bt.block_bootstrap_beat(runs["CORE"], runs["SPY"], n_sims=bootstrap_sims)
    out["expected_drawdowns_10y"] = {k: bt.bootstrap_drawdowns(runs[k], n_sims=bootstrap_sims)
                                     for k in ("CORE", "SPY", "60/40")}

    # EUR investor view
    fx = load_eurusd()
    out["eur"] = {}
    for k in ("CORE", "SPY", "60/40"):
        re_ = to_eur(runs[k], fx)
        if re_ and len(re_.equity) > 252:
            m = bt.metrics(re_)
            out["eur"][k] = {"start": m["start"], "cagr": m["cagr"], "max_dd": m["max_dd"],
                             "vol": m["vol"]}
    return out
