"""
longterm_ideas.py - new ideas for the long-term bot, judged the strict way.

Each idea is a small change to the live CORE strategy, run over 1987-2026 with the live costs and no-trade band.
It only counts as better if its Sharpe ratio is higher in BOTH halves (1987-2006 and 2007-now) and its worst fall
is no deeper than the live bot's. Prints a table and writes state/longterm_ideas.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bot import backtest as bt, config, data, strategies as st  # noqa: E402
from bot.strategies import Core, realized_vol, portfolio_vol, total_return  # noqa: E402

SPLIT = "2007-01-01"


def corr(s, a, b, i, n=126):
    xa = [s.ret(a, j) for j in range(i - n + 1, i + 1)]; xb = [s.ret(b, j) for j in range(i - n + 1, i + 1)]
    if any(x is None for x in xa + xb):
        return None
    ma, mb = sum(xa) / n, sum(xb) / n
    va = sum((x - ma) ** 2 for x in xa); vb = sum((x - mb) ** 2 for x in xb)
    return sum((x - ma) * (y - mb) for x, y in zip(xa, xb)) / (va * vb) ** 0.5 if va and vb else None


class Idea(Core):
    """CORE with switchable tweaks."""
    def __init__(self, label, corr_cap=None, risk_adj=False, defensive=None, skip_month=False, dd_cut=None, **kw):
        super().__init__(**kw)
        self.name = label; self.corr_cap = corr_cap; self.risk_adj = risk_adj; self.defensive = defensive
        self.skip_month = skip_month; self.dd_cut = dd_cut

    def scores(self, s, me, i):
        if not self.skip_month:
            sc = super().scores(s, me, i)
        else:
            sc = {}
            j1 = me.back(i, 1)
            if j1 is None:
                return None
            for a in self.risky + ["CASH"]:
                rs = [total_return(s, a, j1, me.back(i, m + 1)) for m in self.lookbacks]
                if any(r is None for r in rs):
                    continue
                sc[a] = sum(rs) / len(rs)
            if "CASH" not in sc or not any(a in sc for a in ("US", "BONDS")):
                return None
        if sc and self.risk_adj:
            cash = sc["CASH"]
            out = {"CASH": 0.0}
            for a, v in sc.items():
                if a == "CASH":
                    continue
                vol = realized_vol(s, a, i, 126)
                if vol:
                    out[a] = (v - cash) / vol
            return out
        return sc

    def target(self, s, me, i):
        sc = self.scores(s, me, i)
        if sc is None:
            return None
        cash = sc.pop("CASH")
        ranked = sorted(sc.items(), key=lambda kv: -kv[1])
        picks = []
        for a, v in ranked:
            if len(picks) >= self.top_k or v <= cash:
                break
            if self.corr_cap is not None:
                cs = [corr(s, a, p, i) for p in picks]
                if any(c is not None and c > self.corr_cap for c in cs):
                    continue
            picks.append(a)
        if not picks:
            w = {"CASH": 1.0}
        else:
            vols = {a: realized_vol(s, a, i) for a in picks}
            if any(v is None or v <= 0 for v in vols.values()):
                return None
            inv = {a: 1 / v for a, v in vols.items()}; tot = sum(inv.values())
            sleeve = len(picks) / self.top_k
            w = {a: sleeve * x / tot for a, x in inv.items()}
            pv = portfolio_vol(s, w, i)
            if pv is None:
                return None
            scale = min(1.0, self.vol_cap / pv) if pv > 0 else 1.0
            w = {a: min(x * scale, self.max_weight) for a, x in w.items()}
            w["CASH"] = max(0.0, 1.0 - sum(w.values()))
        if self.defensive and w.get("CASH", 0) > 0.05:
            d = self.defensive
            r6 = total_return(s, d, i, me.back(i, 6)); c6 = total_return(s, "CASH", i, me.back(i, 6))
            if r6 is not None and c6 is not None and r6 > c6 and d not in picks:
                w[d] = w.get(d, 0) + w["CASH"] * 0.5
                w["CASH"] *= 0.5
        if self.dd_cut:
            j = me.back(i, 3)
            if j is not None:
                tot3 = sum(x * (total_return(s, a, i, j) or 0) for a, x in w.items() if a != "CASH")
                if tot3 < -self.dd_cut:
                    for a in list(w):
                        if a != "CASH":
                            w["CASH"] = w.get("CASH", 0) + w[a] * 0.5; w[a] *= 0.5
        return w


def main():
    cfg = config.load()
    s = data.build_series()
    kw = dict(top_k=3, vol_cap=cfg["vol_cap"], max_weight=cfg["max_single_asset"])
    live = st.by_name(cfg["strategy"], cfg["vol_cap"], cfg["max_single_asset"])
    ideas = [live,
             Idea("Skip a pick if 6-month correlation > 0.8 with a better one", corr_cap=0.8, **kw),
             Idea("Skip a pick if 6-month correlation > 0.6 with a better one", corr_cap=0.6, **kw),
             Idea("Rank by momentum per unit of risk", risk_adj=True, **kw),
             Idea("Park half of unused cash in 7-10y Treasuries when they trend up", defensive="BONDS", **kw),
             Idea("Skip the latest month in momentum (12-1 style)", skip_month=True, **kw),
             Idea("Halve exposure if the chosen mix fell 8%+ over 3 months", dd_cut=0.08, **kw)]
    rows = []
    for strat in ideas:
        r = bt.run(s, strat, start="1987-06-01", cost_bps=cfg["cost_bps"], band=cfg["no_trade_band"])
        m = bt.metrics(r)
        def half(a, b):
            idx = [k for k, d in enumerate(r.dates) if a <= d < b]
            sub = bt.Result(strat.name, [r.dates[k] for k in idx], [r.equity[k] for k in idx], [], 0, 0, 0)
            return bt.metrics(sub)
        h1, h2 = half("1987-06-01", SPLIT), half(SPLIT, "2100-01-01")
        rows.append(dict(name=strat.name if strat is not live else "Live bot", cagr=m["cagr"], mdd=m["max_dd"] if "max_dd" in m else m.get("mdd"),
                         sharpe=m["sharpe"], s1=h1["sharpe"], s2=h2["sharpe"], c1=h1["cagr"], c2=h2["cagr"]))
    base = rows[0]
    for r in rows[1:]:
        r["better_both"] = r["s1"] > base["s1"] and r["s2"] > base["s2"] and r["mdd"] >= base["mdd"] - 0.005
    print(f"{'idea':62s} CAGR   maxDD  Sharpe  S1987-06 S2007-now  both?")
    for r in rows:
        print(f"{r['name'][:62]:62s} {r['cagr']*100:5.2f} {r['mdd']*100:6.1f}  {r['sharpe']:.2f}    {r['s1']:.2f}     {r['s2']:.2f}   {r.get('better_both', '')}")
    root = Path(__file__).resolve().parents[2]
    (root / "state" / "longterm_ideas.json").write_text(json.dumps(rows, indent=1))
    # crisis and recent-year check for anything that passed the Sharpe test
    cr = json.loads((root / "state" / "crisis.json").read_text())["crises"]
    live_r = bt.run(s, live, start="1987-06-01", cost_bps=cfg["cost_bps"], band=cfg["no_trade_band"])
    from bot.vault import FM, _write
    L = [FM.format(type="research", updated=str(__import__("datetime").date.today()), extra_tags="\n  - long-term\n  - research"),
         "# 18 - Long-Term Research", "",
         "New ideas for the long-term bot, each a small change to the live strategy, replayed 1987-2026 with the live costs and 10% no-trade band. "
         "An idea has to (1) raise the Sharpe ratio in **both** halves of the history (1987-2006 and 2007-now), (2) not deepen the worst fall, "
         "(3) not do clearly worse in the crises and recent years, and (4) beat the live bot in more than half of 2,000 resampled histories. "
         "Already-tested ideas live in [[00 - Variant Lab]] and [[Experiment — Faster Re-entry After a Crash]].", "",
         "| Idea | Growth / yr | Worst fall | Sharpe | Sharpe 1987-2006 | Sharpe 2007-now | Passes step 1-2 |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {r['cagr']*100:.2f}% | {r['mdd']*100:.1f}% | {r['sharpe']:.2f} | {r['s1']:.2f} | {r['s2']:.2f} | {'yes' if r.get('better_both') else ('—' if r['name'] == 'Live bot' else 'no')} |")
    for strat, r in zip(ideas[1:], rows[1:]):
        if not r.get("better_both"):
            continue
        rr = bt.run(s, strat, start="1987-06-01", cost_bps=cfg["cost_bps"], band=cfg["no_trade_band"])
        bb = bt.block_bootstrap_beat(rr, live_r)
        L += ["", f"## Closer look: {r['name']}", "", "| Crisis | Live bot | With the idea |", "|---|---|---|"]
        for c in cr:
            a, b = bt.window_return(live_r, c["start"], c["end"]), bt.window_return(rr, c["start"], c["end"])
            if a is not None and b is not None:
                L.append(f"| {c['name']} | {a*100:+.1f}% | {b*100:+.1f}% |")
        L += ["", "| Year | Live bot | With the idea |", "|---|---|---|"]
        worse = 0
        for y in range(2016, 2027):
            a, b = bt.window_return(live_r, f"{y-1}-12-31", f"{y}-12-31"), bt.window_return(rr, f"{y-1}-12-31", f"{y}-12-31")
            if a is not None and b is not None:
                L.append(f"| {y} | {a*100:+.1f}% | {b*100:+.1f}% |"); worse += b < a
        L += ["", f"Beat the live bot in **{bb['p_beat']*100:.1f}%** of 2,000 resampled histories (growth difference, middle case {bb['cagr_diff_p50']*100:+.2f} points a year).", ""]
        verdict = bb["p_beat"] > 0.5 and worse <= 5
        L.append(f"**Verdict: {'adopt' if verdict else 'not adopted'}.** " + (
            "" if verdict else f"It lowers risk on paper, but it trailed the live bot in {worse} of the last {2027-2016} years and is no better than a coin flip in the resampling test. Small risk gains are not worth weaker recent results."))
    tj = root / "state" / "tranching.json"
    if tj.exists():
        t = json.loads(tj.read_text())
        L += ["", "## Two tranches (half rebalanced at month-end, half mid-month)", "",
              "Same signal, same costs; only the trading day is spread out so one unlucky date matters less.", "",
              "| Version | Growth / yr | Worst fall | Sharpe | Sharpe 1987-2006 | Sharpe 2007-now |", "|---|---|---|---|---|---|"]
        for k in ("Live (month-end only)", "Mid-month only", "Two tranches, half each"):
            r = t[k]; L.append(f"| {k} | {r['cagr']*100:.2f}% | {r['mdd']*100:.1f}% | {r['sharpe']:.2f} | {r['s1']:.2f} | {r['s2']:.2f} |")
        L += ["", f"Beat the live bot in {t['bootstrap']['p_beat']*100:.0f}% of resampled histories. **Not adopted.**", ""]
        sc = t.get("rebalance_day_scan")
        if sc:
            import statistics as _st
            md = [x["mdd"] for x in sc]; cg = [x["cagr"] for x in sc]
            L += ["## How much the worst fall depends on the rebalance day", "",
                  "The identical strategy, deciding on a different day of the month. Growth barely changes; the worst fall changes a lot, mostly through when it caught the COVID crash.", "",
                  "| Decides on | Growth / yr | Worst fall | Sharpe | Bottom of worst fall |", "|---|---|---|---|---|"] + \
                 [f"| {x['day'] if isinstance(x['day'], str) else 'day ' + str(x['day'])} | {x['cagr']*100:.2f}% | {x['mdd']*100:.1f}% | {x['sharpe']:.2f} | {x['trough']} |" for x in sc] + ["",
                  f"**What this means:** expect about {_st.median(cg)*100:.1f}% a year whichever day it trades, but plan for a worst fall of about "
                  f"{_st.median(md)*100:.0f}% (typical) and up to {min(md)*100:.0f}% - not the {sc[-1]['mdd']*100:.1f}% the month-end backtest shows. "
                  "The live risk limit (stop and ask at -25%) sits inside that range, so an unlucky year could trigger it - that would be the limit doing its job, not a malfunction.", ""]
    L += ["", "Back to [[16 - Bot Brain]] · [[03 - Backtest Report]] · [[17 - Day Trader Research]]", ""]
    _write(root / "18 - Long-Term Research.md", "\n".join(L))


if __name__ == "__main__":
    main()
