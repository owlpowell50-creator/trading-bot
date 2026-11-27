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
    (Path(__file__).resolve().parents[2] / "state" / "longterm_ideas.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
