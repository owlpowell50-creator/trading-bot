"""
crash_guard.py - a mid-month exit that only reacts to real crashes.

The plain crash brake (sell below the 200-day average) was rejected in "09 - Upgrades Tested": it whipsawed.
These guards only fire on a deep, fast fall, sell that one asset to cash, and let it back only at the next
regular rebalance. Three pre-declared rules (no tuning after seeing results):

  G1  down 10%+ from its 63-day high AND below its 100-day average
  G2  down 15%+ from its 63-day high
  G3  down 10%+ in the last 10 trading days

Each is judged on 12 rebalance days (the live month-end + 11 days of the month) so that no result depends on
calendar luck. To be adopted a guard must: raise the median Sharpe across those days, raise the Sharpe in both
halves (1987-2006, 2007-now) at month-end, shrink the median worst fall, and beat the live bot in more than
half of the resampled histories.
"""
from __future__ import annotations

import json
import statistics as stt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot import backtest as bt, config, data, strategies as st  # noqa: E402
import tranching as T  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def g1(s, a, i, n):
    lv = s.levels[a]
    if i < 100 or lv[i - 100] is None:
        return False
    hi = max(lv[i - 62:i + 1]); avg = sum(lv[i - 99:i + 1]) / 100
    return lv[i] <= 0.90 * hi and lv[i] < avg


def g2(s, a, i, n):
    lv = s.levels[a]
    if i < 63 or lv[i - 62] is None:
        return False
    return lv[i] <= 0.85 * max(lv[i - 62:i + 1])


def g3(s, a, i, n):
    lv = s.levels[a]
    if i < 10 or lv[i - 10] is None:
        return False
    return lv[i] <= 0.90 * lv[i - 10]


GUARDS = {"G1: 10% off 3-month high and below 100-day average": g1,
          "G2: 15% off 3-month high": g2,
          "G3: 10% fall in 10 trading days": g3}
DAYS = (3, 5, 8, 10, 12, 15, 18, 20, 22, 25, 27)


def run_one(s, strat, cfg, me_cls, guard):
    orig_me, orig_hit = bt.MonthEnds, bt.crash_brake_hit
    bt.MonthEnds = me_cls
    if guard:
        bt.crash_brake_hit = guard
    try:
        r = bt.run(s, strat, start="1987-06-01", cost_bps=cfg["cost_bps"], band=cfg["no_trade_band"], brake=1 if guard else 0)
    finally:
        bt.MonthEnds, bt.crash_brake_hit = orig_me, orig_hit
    return T.cut(r, "1988-01-01", "2100")


def summary(r):
    m = bt.metrics(r)
    return dict(cagr=m["cagr"], mdd=m["max_dd"], sharpe=m["sharpe"],
                s1=bt.metrics(T.cut(r, "1900", "2007-01-01"))["sharpe"], s2=bt.metrics(T.cut(r, "2007-01-01", "2100"))["sharpe"])


def main():
    cfg = config.load(); s = data.build_series()
    strat = st.by_name(cfg["strategy"], cfg["vol_cap"], cfg["max_single_asset"])
    cr = json.loads((ROOT / "state" / "crisis.json").read_text())["crises"]
    out = {}
    base_me = run_one(s, strat, cfg, st.MonthEnds, None)
    for name, g in [("Live (no guard)", None)] + list(GUARDS.items()):
        r_me = base_me if g is None else run_one(s, strat, cfg, st.MonthEnds, g)
        scan = [summary(r_me)]
        for day in DAYS:
            scan.append(summary(run_one(s, strat, cfg, lambda s_, today=None, day=day: T.MidMonth(s_, today, day), g)))
        me = scan[0]
        row = dict(month_end=me, med_sharpe=stt.median(x["sharpe"] for x in scan), med_mdd=stt.median(x["mdd"] for x in scan),
                   worst_mdd=min(x["mdd"] for x in scan), med_cagr=stt.median(x["cagr"] for x in scan),
                   trades=len(r_me.weights_log))
        row["crises"] = {c["name"]: bt.window_return(r_me, c["start"], c["end"]) for c in cr}
        if g is not None:
            row["bootstrap"] = bt.block_bootstrap_beat(r_me, base_me)
        out[name] = row
        print(f"{name[:52]:52s} CAGR {me['cagr']*100:5.2f}%  MDD {me['mdd']*100:6.1f}%  Sh {me['sharpe']:.2f} ({me['s1']:.2f}/{me['s2']:.2f})  "
              f"median over days: Sh {row['med_sharpe']:.2f} MDD {row['med_mdd']*100:.1f}% worst {row['worst_mdd']*100:.1f}% CAGR {row['med_cagr']*100:.2f}%"
              + (f"  beat {row['bootstrap']['p_beat']*100:.0f}%" if g else ""), flush=True)
    base = out["Live (no guard)"]
    for name, row in out.items():
        if name == "Live (no guard)":
            continue
        me = row["month_end"]; b = base["month_end"]
        row["adopt"] = (row["med_sharpe"] > base["med_sharpe"] and me["s1"] > b["s1"] and me["s2"] > b["s2"]
                        and row["med_mdd"] > base["med_mdd"] and row["bootstrap"]["p_beat"] > 0.5)
    (ROOT / "state" / "crash_guard.json").write_text(json.dumps(out, indent=1, default=float))
    for name, row in out.items():
        print(name, "ADOPT" if row.get("adopt") else "")
    return out


if __name__ == "__main__":
    main()
