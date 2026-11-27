"""
tranching.py - does splitting the long-term bot into two halves that rebalance on different days help?

Tranche A rebalances at month-end (the live bot). Tranche B runs the identical strategy but decides on the
last trading day on or before the 15th of each month. The combined portfolio is half of each, never
re-mixed. Same signal, same costs - only the timing luck is spread out. Judged with the both-halves rule.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bot import backtest as bt, config, data, strategies as st  # noqa: E402


class MidMonth(st.MonthEnds):
    def __init__(self, s, today=None, day=15):
        self.s = s
        self.me = []
        for i in range(len(s.dates) - 1):
            d, n = s.dates[i], s.dates[i + 1]
            if int(d[8:10]) <= day < int(n[8:10]) or (d[:7] != n[:7] and int(d[8:10]) <= day):
                self.me.append(i)
        self.pos = {idx: k for k, idx in enumerate(self.me)}


def run_with(s, strat, me_cls, cfg, start):
    orig = bt.MonthEnds
    bt.MonthEnds = me_cls
    try:
        return bt.run(s, strat, start=start, cost_bps=cfg["cost_bps"], band=cfg["no_trade_band"])
    finally:
        bt.MonthEnds = orig


def combine(ra, rb, weights=(0.5, 0.5)):
    da, db = dict(zip(ra.dates, ra.equity)), dict(zip(rb.dates, rb.equity))
    ds = sorted(set(da) & set(db))
    a0, b0 = da[ds[0]], db[ds[0]]
    eq = [weights[0] * da[d] / a0 + weights[1] * db[d] / b0 for d in ds]
    return bt.Result("tranched", ds, eq, [], 0, 0, 0)


def cut(r, a, b):
    idx = [k for k, d in enumerate(r.dates) if a <= d < b]
    return bt.Result(r.name, [r.dates[k] for k in idx], [r.equity[k] for k in idx], [], 0, 0, 0)


def main():
    cfg = config.load(); s = data.build_series()
    strat = st.by_name(cfg["strategy"], cfg["vol_cap"], cfg["max_single_asset"])
    A = run_with(s, strat, st.MonthEnds, cfg, "1987-06-01")
    B = run_with(s, strat, MidMonth, cfg, "1987-06-01")
    T = combine(A, B)
    A2 = cut(A, T.dates[0], "2100")
    out = {}
    for name, r in (("Live (month-end only)", A2), ("Mid-month only", cut(B, T.dates[0], "2100")), ("Two tranches, half each", T)):
        m = bt.metrics(r); h1 = bt.metrics(cut(r, "1900", "2007-01-01")); h2 = bt.metrics(cut(r, "2007-01-01", "2100"))
        out[name] = dict(cagr=m["cagr"], mdd=m["max_dd"], sharpe=m["sharpe"], s1=h1["sharpe"], s2=h2["sharpe"], c1=h1["cagr"], c2=h2["cagr"])
        print(f"{name:28s} {m['cagr']*100:5.2f}% {m['max_dd']*100:6.1f}%  Sharpe {m['sharpe']:.2f}  {h1['sharpe']:.2f} / {h2['sharpe']:.2f}")
    cr = json.loads((Path(__file__).resolve().parents[2] / "state" / "crisis.json").read_text())["crises"]
    out["crises"] = {c["name"]: [bt.window_return(A2, c["start"], c["end"]), bt.window_return(T, c["start"], c["end"])] for c in cr}
    for k, (a, b) in out["crises"].items():
        print(f"  {k:36s} {(a or 0)*100:+6.1f}% {(b or 0)*100:+6.1f}%")
    out["years"] = {y: [bt.window_return(A2, f"{y-1}-12-31", f"{y}-12-31"), bt.window_return(T, f"{y-1}-12-31", f"{y}-12-31")] for y in range(1989, 2027)}
    out["bootstrap"] = bt.block_bootstrap_beat(T, A2)
    print("bootstrap", out["bootstrap"])
    scan = []
    for day in (3, 5, 8, 10, 12, 15, 18, 20, 22, 25, 27):
        r = cut(run_with(s, strat, lambda s_, today=None, day=day: MidMonth(s_, today, day), cfg, "1987-06-01"), "1988-01-01", "2100")
        m = bt.metrics(r); scan.append(dict(day=day, cagr=m["cagr"], mdd=m["max_dd"], sharpe=m["sharpe"], trough=m["dd_trough"]))
    m = bt.metrics(cut(A, "1988-01-01", "2100"))
    scan.append(dict(day="month-end (live)", cagr=m["cagr"], mdd=m["max_dd"], sharpe=m["sharpe"], trough=m["dd_trough"]))
    out["rebalance_day_scan"] = scan
    (Path(__file__).resolve().parents[2] / "state" / "tranching.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    main()
