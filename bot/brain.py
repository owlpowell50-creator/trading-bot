"""The bot's brain: a daily self-review that thinks ahead instead of just reporting.

Runs after the daily job. Reads the price history, the live paper account, the day trader's record and the
crisis study, and writes:
  * state/brain.json            - thoughts and alerts (the Obsidian HUD types these out)
  * "16 - Bot Brain.md"         - today's thinking
  * Brain/Brain YYYY-MM-DD.md   - one note per day, so the vault keeps a diary of the bot's reasoning

What it works out:
  1. If the month ended today, what would the bot hold - and what changes vs now (a preview of the rebalance)
  2. How close each asset is to entering or leaving (the price move that would flip it)
  3. Volatility now vs normal, and the portfolio's volatility vs the cap
  4. The live account's drawdown, and what the stress scenarios would do to today's holdings
  5. The day trader's recent record (win rate, average R, risk used) and why the skill pack skipped trades
  6. Alerts: anything unusual, ranked
It never trades and never changes a rule - it only thinks and writes.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config as cfgmod, data, strategies as st
from .data import ROOT
from .vault import _write

STATE = ROOT / "state"
OUT_JSON = STATE / "brain.json"
NOTE = ROOT / "16 - Bot Brain.md"
DIARY = ROOT / "Brain"
SHORT = {"US": "US stocks", "INTL": "foreign stocks", "BONDS": "7-10y Treasuries", "LONGBONDS": "20y+ Treasuries",
         "REIT": "real estate", "GOLD": "gold", "COMMOD": "commodities", "CASH": "cash"}
ETF = {"VOO": "US", "SPY": "US", "IEFA": "INTL", "IEF": "BONDS", "TLT": "LONGBONDS", "VNQ": "REIT", "GLD": "GOLD", "IAU": "GOLD",
       "PDBC": "COMMOD", "DBC": "COMMOD", "BIL": "CASH", "SGOV": "CASH"}
# hypothetical one-month shocks (see Independent Risk Committee/26 - Stress Scenario Library)
SCENARIOS = {
    "Equity crash": {"US": -.25, "INTL": -.20, "LONGBONDS": .08, "BONDS": .03, "REIT": -.25, "GOLD": -.03, "COMMOD": -.15},
    "Credit crisis": {"US": -.17, "INTL": -.20, "LONGBONDS": .05, "BONDS": .03, "REIT": -.30, "GOLD": -.15, "COMMOD": -.25},
    "Inflation shock": {"US": -.10, "INTL": -.10, "LONGBONDS": -.10, "BONDS": -.05, "REIT": -.12, "GOLD": 0, "COMMOD": .10},
    "Rate shock": {"US": -.05, "INTL": -.05, "LONGBONDS": -.12, "BONDS": -.05, "REIT": -.08, "GOLD": -.03, "COMMOD": 0},
    "Everything falls": {"US": -.15, "INTL": -.15, "LONGBONDS": -.05, "BONDS": -.02, "REIT": -.20, "GOLD": -.08, "COMMOD": -.10},
}


def _load(name, default=None):
    p = STATE / name
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return default


def pct(x, d=1):
    return "—" if x is None else f"{x * 100:+.{d}f}%"


def preview(s, strat):
    """Score every asset as if today were a month-end; return scores, target weights and per-asset helpers."""
    me = st.MonthEnds(s)
    i = len(s.dates) - 1
    if i not in me.pos:                       # treat today as a pseudo month-end
        me.me = list(me.me) + [i]
        me.pos[i] = len(me.me) - 1
    scores = strat.scores(s, me, i) or {}
    target = strat.target(s, me, i) or {}
    # price ratio sum: score = mean(P/P_m) - 1  ->  a move x in today's price changes it to (1+x)*(1+score) - 1
    return i, scores, target


def flips(scores, top_k=3):
    """For each asset, the price move (relative to the others standing still) that changes its in/out status."""
    if "CASH" not in scores:
        return []
    cash = scores["CASH"]
    risky = sorted(((a, v) for a, v in scores.items() if a != "CASH"), key=lambda kv: -kv[1])
    inside = [a for a, v in risky[:top_k] if v > cash]
    bar_in = max(cash, risky[top_k][1] if len(risky) > top_k else -1)        # what an outsider must beat
    out = []
    for rank, (a, v) in enumerate(risky):
        if a in inside:
            # to drop out: fall below cash, or below the best outsider
            nxt = max(cash, risky[top_k][1] if len(risky) > top_k else cash)
            x = (1 + nxt) / (1 + v) - 1
            out.append({"asset": a, "status": "held", "score": v, "move": x, "to": "drop out"})
        else:
            need = max(cash, risky[min(top_k, len(risky)) - 1][1] if len(inside) >= top_k else cash)
            x = (1 + need) / (1 + v) - 1
            out.append({"asset": a, "status": "out", "score": v, "move": x, "to": "get in"})
    return out


def vols(s, i):
    out = {}
    for a in s.assets:
        if a == "CASH":
            continue
        v1, v3 = st.realized_vol(s, a, i, 21), st.realized_vol(s, a, i, 63)
        v12 = st.realized_vol(s, a, i, 252)
        if v3:
            out[a] = {"1m": v1, "3m": v3, "1y": v12}
    return out


def account_weights(snap):
    if not snap:
        return {}, None
    eq = float(snap["account"]["equity"])
    w = {}
    for p in snap.get("positions", []):
        a = ETF.get(p["symbol"])
        if a:
            w[a] = w.get(a, 0) + float(p["market_value"]) / eq
    w["CASH"] = max(0.0, 1 - sum(w.values()))
    return w, eq


def equity_curve():
    p = STATE / "equity.csv"
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0][:2] == "20":
            try:
                rows.append((parts[0], float(parts[1])))
            except ValueError:
                pass
    return rows


def day_trader_view(dt, n_days=10):
    if not dt:
        return None
    trades = dt.get("trades", [])
    days = sorted({t["date"] for t in trades})[-n_days:]
    rec = [t for t in trades if t["date"] in days]
    closed = [t for t in rec if t.get("exit") is not None]
    open_ = [t for t in rec if t.get("exit") is None]
    rs = [t["r"] for t in closed if t.get("r") is not None]
    sk = [x for x in dt.get("skill_log", []) if x.get("date") in set(days) or not days]
    reasons = Counter((x.get("skip") or "bought").split(":")[0].split("(")[0].strip() for x in sk)
    eq = dt.get("days", [])
    return {"days": days, "trades": len(rec), "closed": len(closed), "unclosed": open_, "wins": sum(1 for t in closed if t["pnl"] > 0),
            "pnl": sum(t["pnl"] for t in closed), "avg_r": (sum(rs) / len(rs)) if rs else None,
            "skill_seen": len(sk), "skill_reasons": reasons.most_common(5),
            "equity": eq[-1]["equity"] if eq else None, "start_equity": dt.get("start_equity")}


RULES_SINCE = "2026-11-30"          # first session under the pair + 20-day trend + 3x target rules
EXPECTED_ROW = "Live rule now, target 3.0x range"


def edge_check(dt, research, since=RULES_SINCE):
    """Live trades under the current day-trading rules vs what 2016-2026 says to expect.
    Returns [("thought", text)] / [("alert", level, text)]."""
    out = []
    if not research:
        return out
    row = next((r for r in research.get("rows", []) if r.get("name") == EXPECTED_ROW), None)
    if not row:
        return out
    exp = row["second"]["avg"]                  # recent-half average: the most relevant expectation
    rs = [t["r"] for t in (dt or {}).get("trades", []) if t["date"] >= since and t.get("strategy", "ORB") == "ORB"
          and t.get("exit") is not None and t.get("r") is not None]
    n = len(rs)
    if n == 0:
        out.append(("thought", f"day trader's current rules expect about {exp:+.2f}R a trade (2021-now) - no live trades under them yet"))
        return out
    avg = sum(rs) / n
    sd = (sum((x - avg) ** 2 for x in rs) / max(1, n - 1)) ** 0.5 or 1.0
    z = (avg - exp) / (sd / n ** 0.5)
    out.append(("thought", f"day trader under the current rules: {n} trades, average {avg:+.2f}R vs {exp:+.2f}R expected"
                           + (" - far too few trades to judge yet" if n < 30 else "")))
    if n >= 30 and z < -2:
        out.append(("alert", "red", f"day trader is running well below its tested results ({avg:+.2f}R vs {exp:+.2f}R over {n} trades, "
                                    f"{abs(z):.1f} standard errors) - the edge may have gone; consider pausing it"))
    elif n >= 15 and z < -1.5:
        out.append(("alert", "amber", f"day trader is behind its tested results ({avg:+.2f}R vs {exp:+.2f}R over {n} trades) - watch it"))
    recent = research.get("years_adopted") or {}
    yrs = sorted(recent)[-2:]
    if yrs and all(recent[y].get("avg", 0) < 0 for y in yrs):
        out.append(("alert", "amber", f"the day-trading research shows the current rules losing in {' and '.join(yrs)} - the edge may be fading"))
    return out


def tracking_check(s, strat, curve, trial):
    """Is the live account doing what the rules should have produced? Compares the live equity change since the
    trial started with the same period for the month's target mix, using the bot's own price series.
    A gap of more than 1.5 points usually means an execution problem (missed trade, wrong fills, cash left idle)."""
    if not curve or not trial or len(curve) < 3:
        return None
    d0, e0 = curve[0]; d1, e1 = curve[-1]
    if d0 not in s.idx or d1 not in s.idx:
        return None
    i0, i1 = s.idx[d0], s.idx[d1]
    me = st.MonthEnds(s)
    k = max((m for m in me.me if m < i0), default=None)
    if k is None:
        return None
    tgt = strat.target(s, me, k)
    if not tgt:
        return None
    tot = sum(tgt.values()); tgt = {a: w / tot for a, w in tgt.items()}
    model = sum(w * (s.levels[a][i1] / s.levels[a][i0] - 1) for a, w in tgt.items() if s.levels[a][i0] and s.levels[a][i1])
    live = e1 / e0 - 1
    return dict(start=d0, end=d1, live=live, model=model, gap=live - model, mix=tgt)


def context_check(s, strat, cfg, curve):
    """Is the live result normal? Looks at every stretch of the same length in the 1987-2026 backtest when US
    stocks moved about as much as they did live, and reports how the bot did in those stretches."""
    if not curve or len(curve) < 5:
        return None
    d0, d1 = curve[0][0], curve[-1][0]
    if d0 not in s.idx or d1 not in s.idx:
        return None
    n = s.idx[d1] - s.idx[d0]
    us = s.levels["US"]
    mkt = us[s.idx[d1]] / us[s.idx[d0]] - 1
    from . import backtest as bt
    r = bt.run(s, strat, start="1987-06-01", cost_bps=cfg["cost_bps"], band=cfg["no_trade_band"])
    eq = dict(zip(r.dates, r.equity))
    ds = [d for d in r.dates if d in s.idx]
    outs = []
    for j in range(0, len(ds) - n):
        a, b = ds[j], ds[j + n]
        ia, ib = s.idx[a], s.idx[b]
        if us[ia] and us[ib] and abs((us[ib] / us[ia] - 1) - mkt) <= 0.02:
            outs.append(eq[b] / eq[a] - 1)
    if len(outs) < 30:
        return None
    outs.sort()
    q = lambda f: outs[int(f * (len(outs) - 1))]  # noqa: E731
    live = curve[-1][1] / curve[0][1] - 1
    rank = sum(1 for x in outs if x <= live) / len(outs)
    return dict(days=n, market=mkt, live=live, n=len(outs), p10=q(0.10), p50=q(0.5), p90=q(0.90), rank=rank)


def hist_var_es(s, weights, i, horizon=1, start=252, confs=(0.95, 0.99)):
    """Historical-simulation VaR and expected shortfall for a FIXED mix, using every overlapping
    `horizon`-day window of the bot's own total-return series up to day i (1987 onwards).
    Losses are positive numbers (0.05 = a 5% loss)."""
    w = {a: x for a, x in weights.items() if x > 1e-6}
    rets = []
    for k in range(max(start, horizon), i + 1, 1 if horizon == 1 else 5):
        r = 0.0
        for a, x in w.items():
            lv = s.levels[a]
            if lv[k] is None or lv[k - horizon] is None:
                r = None
                break
            r += x * (lv[k] / lv[k - horizon] - 1)
        if r is not None:
            rets.append(r)
    if len(rets) < 250:
        return None
    rets.sort()
    out = {"n": len(rets), "horizon": horizon}
    for c in confs:
        k = int((1 - c) * len(rets))
        tail = rets[:max(1, k)]
        out[f"var{int(c * 100)}"] = -rets[k]
        out[f"es{int(c * 100)}"] = -sum(tail) / len(tail)
    out["worst"] = -rets[0]
    return out


def risk_contrib(s, weights, i, n=252):
    """Share of portfolio variance from each holding (sums to 1), from the last n days of daily returns."""
    w = {a: x for a, x in weights.items() if a != "CASH" and x > 1e-6}
    if not w:
        return {}
    series = {}
    for a in w:
        lv = s.levels[a]
        r = [lv[k] / lv[k - 1] - 1 for k in range(i - n + 1, i + 1) if lv[k] and lv[k - 1]]
        if len(r) < n * 0.9:
            return {}
        series[a] = r[-min(len(v) for v in [r]):]
    m = min(len(v) for v in series.values())
    series = {a: v[-m:] for a, v in series.items()}
    mean = {a: sum(v) / m for a, v in series.items()}
    cov = {(a, b): sum((series[a][t] - mean[a]) * (series[b][t] - mean[b]) for t in range(m)) / (m - 1) for a in w for b in w}
    pvar = sum(w[a] * w[b] * cov[(a, b)] for a in w for b in w)
    if pvar <= 0:
        return {}
    return {a: w[a] * sum(w[b] * cov[(a, b)] for b in w) / pvar for a in w}


def attribution(snap):
    """Unrealised P&L by asset class from the broker snapshot (cost basis vs market value)."""
    out = {}
    for p in (snap or {}).get("positions", []):
        a = ETF.get(p["symbol"], p["symbol"])
        out[a] = out.get(a, 0.0) + float(p.get("unrealized_pl") or 0)
    return out


def think(today: str | None = None):
    cfg = cfgmod.load()
    s = data.build_series()
    strat = st.by_name(cfg["strategy"], cfg["vol_cap"], cfg["max_single_asset"])
    i, scores, target = preview(s, strat)
    target, _ = __import__("bot.risk", fromlist=["clamp_weights"]).clamp_weights(target, cfg["max_single_asset"]) if target else ({}, [])
    snap = _load("alpaca_snapshot.json")
    held, eq = account_weights(snap)
    vol = vols(s, i)
    pv_target = st.portfolio_vol(s, {a: w for a, w in target.items() if a != "CASH"}, i) if target else None
    pv_now = st.portfolio_vol(s, {a: w for a, w in held.items() if a != "CASH"}, i) if held else None
    fl = flips(scores)
    curve = equity_curve()
    peak = max((v for _, v in curve), default=None); last = curve[-1][1] if curve else None
    dd = (last / peak - 1) if (peak and last) else None
    stress = {k: sum(held.get(a, 0) * x for a, x in sc.items()) for k, sc in SCENARIOS.items()} if held else {}
    dt = day_trader_view(_load("daytrade_live.json"))
    crisis = _load("crisis.json", {})
    us = s.levels["US"]; lastp = us[i]
    ma200 = sum(us[i - 199:i + 1]) / 200 if i >= 200 and all(x is not None for x in us[i - 199:i + 1]) else None
    hi52 = max(x for x in us[max(0, i - 251):i + 1] if x is not None)
    today = today or s.dates[i]
    nxt_month = (date.fromisoformat(s.dates[i]).replace(day=1) + timedelta(days=32)).replace(day=1)

    thoughts, alerts = [], []
    # 1 rebalance preview
    chg = []
    for a in sorted(set(target) | set(held), key=lambda a: -(target.get(a, 0))):
        d = target.get(a, 0) - held.get(a, 0)
        if abs(d) >= 0.03:
            chg.append((a, held.get(a, 0), target.get(a, 0)))
    tgt_txt = ", ".join(f"{SHORT[a]} {w * 100:.0f}%" for a, w in sorted(target.items(), key=lambda kv: -kv[1]) if w >= 0.01)
    thoughts.append(f"if the month ended today I would hold {tgt_txt}")
    if chg:
        thoughts.append("that would mean " + "; ".join(f"{SHORT[a]} {o * 100:.0f}% → {n * 100:.0f}%" for a, o, n in chg[:4]) +
                        f" at the next rebalance ({nxt_month:%-d %b})")
    else:
        thoughts.append(f"no big changes expected at the next rebalance ({nxt_month:%-d %b})")
    # 2 closest flips
    close = sorted(fl, key=lambda f: abs(f["move"]))[:3]
    for f in close:
        verb = "would drop out" if f["status"] == "held" else "would get in"
        thoughts.append(f"{SHORT[f['asset']]} {verb} after a {abs(f['move']) * 100:.1f}% {'fall' if f['move'] < 0 else 'rise'} (others unchanged)")
        if abs(f["move"]) < 0.02:
            alerts.append(("amber", f"{SHORT[f['asset']]} is within {abs(f['move']) * 100:.1f}% of {'leaving' if f['status'] == 'held' else 'entering'} the portfolio"))
    # 3 volatility
    for a, v in vol.items():
        if v["1m"] and v["1y"] and v["1m"] > 1.6 * v["1y"] and (held.get(a, 0) > 0.05 or target.get(a, 0) > 0.05):
            alerts.append(("amber", f"{SHORT[a]} volatility {v['1m'] * 100:.0f}% (1 month) vs {v['1y'] * 100:.0f}% normal"))
    if pv_now is not None:
        thoughts.append(f"portfolio volatility {pv_now * 100:.1f}% against a cap of {cfg['vol_cap'] * 100:.1f}%")
        if pv_now > cfg["vol_cap"]:
            alerts.append(("red", f"live portfolio volatility {pv_now * 100:.1f}% is above the {cfg['vol_cap'] * 100:.1f}% cap"))
    # 4 market + account
    if ma200:
        thoughts.append(f"S&P 500 is {pct(lastp / ma200 - 1)} vs its 200-day average and {pct(lastp / hi52 - 1)} from its 1-year high")
    if dd is not None:
        thoughts.append(f"live account {pct(dd)} from its high")
        if dd < -0.08:
            alerts.append(("amber", f"live long-term account is {pct(dd)} below its high — the backtest's worst was −17.6% at month-end and −14% to −29% depending on the rebalance day (see 18 - Long-Term Research)"))
    if stress:
        worst = min(stress.items(), key=lambda kv: kv[1])
        thoughts.append(f"worst stress scenario for today's holdings: {worst[0].lower()} {pct(worst[1])}")
    # 4b is the live result normal, and is the account doing what the rules say?
    try:
        ctx = context_check(s, strat, cfg, curve)
        if ctx:
            where = ("better than most" if ctx["rank"] > 0.75 else "worse than most" if ctx["rank"] < 0.25 else "normal")
            thoughts.append(f"since {curve[0][0]} the live account is {pct(ctx['live'])} with US stocks {pct(ctx['market'])}; in the 40-year backtest, "
                            f"{ctx['days']}-day stretches with a similar market move left the bot between {pct(ctx['p10'])} and {pct(ctx['p90'])} "
                            f"(middle {pct(ctx['p50'])}) - today's result is {where}")
            if ctx["rank"] < 0.05:
                alerts.append(("amber", f"live result {pct(ctx['live'])} is in the worst 5% of similar stretches in the backtest - check execution"))
        trk = tracking_check(s, strat, curve, _load("trial.json"))
        if trk:
            thoughts.append(f"tracking: live {pct(trk['live'])} vs {pct(trk['model'])} for the rules' own mix over the same days (gap {pct(trk['gap'])})")
            if abs(trk["gap"]) > 0.015:
                alerts.append(("amber", f"live account is {pct(trk['gap'])} away from what the rules' mix returned since {trk['start']} - "
                                        "look for a missed trade, odd fills or idle cash"))
    except Exception as e:  # noqa: BLE001
        thoughts.append(f"performance context unavailable ({e})")
    # 4c tail risk, risk contribution and P&L attribution
    try:
        held_risky = {a: x for a, x in held.items() if x > 0.001}
        v1 = hist_var_es(s, held_risky, i, 1) if held else None
        v21 = hist_var_es(s, held_risky, i, 21) if held else None
        t21 = hist_var_es(s, target, i, 21) if target else None
        if v1 and v21:
            thoughts.append(f"tail risk of today's holdings (history since 1987): a 1-in-20 bad day loses {pct(-v1['var95'])}, "
                            f"a 1-in-20 bad month {pct(-v21['var95'])}; the average of the worst 1% of months is {pct(-v21['es99'])}")
            if t21:
                thoughts.append(f"after the next rebalance the 1-in-20 bad month would be {pct(-t21['var95'])} "
                                f"(worst 1% of months {pct(-t21['es99'])})")
            if v21["es99"] > 0.20:
                alerts.append(("amber", f"today's holdings could lose about {pct(v21['es99'])} in a very bad month (worst 1% average) - above 20%"))
        rc = risk_contrib(s, held, i)
        if rc:
            top = sorted(rc.items(), key=lambda kv: -kv[1])
            thoughts.append("where the risk comes from: " + ", ".join(f"{SHORT.get(a, a)} {x * 100:.0f}%" for a, x in top) +
                            " of the portfolio's swings (last year of data)")
        att = attribution(snap)
        if att:
            tot = sum(att.values())
            thoughts.append(f"unrealised P&L {tot:+,.0f} USD: " + ", ".join(f"{SHORT.get(a, a)} {v:+,.0f}" for a, v in sorted(att.items(), key=lambda kv: kv[1])))
        doc_risk = {"var_1d": v1, "var_21d": v21, "var_21d_target": t21, "risk_contrib": rc, "attribution": att}
    except Exception as e:  # noqa: BLE001
        thoughts.append(f"tail-risk analytics unavailable ({e})"); doc_risk = {}
    # 5 day trader
    if dt:
        if dt["unclosed"]:
            alerts.append(("red", "day trader has trades with no recorded exit: " + ", ".join(f"{t['symbol']} {t['date']}" for t in dt["unclosed"]) +
                           " — check the day-trading account is flat"))
        if dt["closed"]:
            thoughts.append(f"day trader last {len(dt['days'])} sessions: {dt['closed']} closed trades, {dt['wins']} winners, "
                            f"avg R {dt['avg_r']:+.2f}" if dt["avg_r"] is not None else "day trader: no closed trades yet")
        if dt["skill_reasons"]:
            r0 = dt["skill_reasons"][0]
            thoughts.append(f"skill pack looked at {dt['skill_seen']} breakouts; most common decision: {r0[0]} ({r0[1]})")
    # 5b is the day trader's edge holding up? compare trades under the current rules with the research
    try:
        for t_ in edge_check(_load("daytrade_live.json"), _load("orb_research.json")):
            (alerts.append(t_[1:]) if t_[0] == "alert" else thoughts.append(t_[1]))
    except Exception as e:  # noqa: BLE001
        thoughts.append(f"day-trader edge check unavailable ({e})")
    # 6 data freshness
    age = (date.fromisoformat(today) - date.fromisoformat(s.dates[i])).days
    if age > 4:
        alerts.append(("red", f"price data is {age} days old — the daily job may not be running"))

    doc = {"date": today, "data_through": s.dates[i], "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
           "thoughts": thoughts, "alerts": [{"level": l, "text": t} for l, t in alerts], "risk": doc_risk,
           "preview": {"target": target, "held": held, "changes": chg}, "scores": scores,
           "flips": fl, "vol": vol, "stress": stress, "drawdown": dd,
           "portfolio_vol": {"now": pv_now, "target": pv_target, "cap": cfg["vol_cap"]}}
    OUT_JSON.write_text(json.dumps(doc, indent=1, default=float))
    note = render(doc, cfg, dt, crisis)
    _write(NOTE, note)
    _write(DIARY / f"Brain {today}.md", note.replace("# 16 - Bot Brain", f"# Brain {today}", 1)
           .replace("type: bot-brain", "type: bot-brain-diary", 1))
    return doc


def render(doc, cfg, dt, crisis):
    sc = doc["scores"]; cash = sc.get("CASH")
    L = ["---", "type: bot-brain", "department: trading", 'department_color: "#22C55E"', "cssclasses:", "  - dept-trading",
         "generated: trading-bot", f"updated: {doc['date']}", "tags:", "  - type/bot-note", "  - trading-bot", "  - brain", "---",
         "# 16 - Bot Brain", "",
         f"> [!abstract] What the bot is thinking — {doc['date']} (prices through {doc['data_through']})",
         "> The bot reviews itself after every daily run: it previews the next rebalance, measures how close each decision is "
         "to flipping, checks volatility, stress and the day trader, and flags anything unusual. It never trades from here.", "",
         "## Thoughts", ""] + [f"- {t}" for t in doc["thoughts"]] + ["", "## Alerts", ""]
    if doc["alerts"]:
        icon = {"red": "🔴", "amber": "🟠"}
        L += [f"- {icon.get(a['level'], '•')} {a['text']}" for a in doc["alerts"]]
    else:
        L.append("- 🟢 Nothing unusual.")
    L += ["", "## If the month ended today", "", "| Asset | Score (avg 3/6/12-month return) | Held now | Would hold | Move that flips it |", "|---|---|---|---|---|"]
    fl = {f["asset"]: f for f in doc["flips"]}
    for a, v in sorted(sc.items(), key=lambda kv: -kv[1]):
        if a == "CASH":
            continue
        f = fl.get(a)
        mv = f"{abs(f['move']) * 100:.1f}% {'fall' if f['move'] < 0 else 'rise'} → {f['to']}" if f else "—"
        L.append(f"| {SHORT[a]} | {pct(v)}{' (beats T-bills)' if cash is not None and v > cash else ''} | "
                 f"{doc['preview']['held'].get(a, 0) * 100:.0f}% | {doc['preview']['target'].get(a, 0) * 100:.0f}% | {mv} |")
    L += [f"| cash (T-bills) | {pct(cash)} | {doc['preview']['held'].get('CASH', 0) * 100:.0f}% | {doc['preview']['target'].get('CASH', 0) * 100:.0f}% | — |", "",
          "*Flip moves assume the other assets stand still; the score is the average of the 3-, 6- and 12-month returns, and the bot holds up to three assets that beat T-bills.*", "",
          "## Volatility", "", "| Asset | 1 month | 3 months | 1 year |", "|---|---|---|---|"]
    for a, v in doc["vol"].items():
        f = lambda x: "—" if not x else f"{x * 100:.0f}%"  # noqa: E731
        L.append(f"| {SHORT[a]} | {f(v['1m'])} | {f(v['3m'])} | {f(v['1y'])} |")
    pv = doc["portfolio_vol"]
    L += ["", f"Portfolio volatility now **{pct(pv['now']).lstrip('+')}**, planned **{pct(pv['target']).lstrip('+')}**, cap {cfg['vol_cap'] * 100:.1f}%.", "",
          "## Stress test on today's holdings", "", "| Scenario | One-month loss |", "|---|---|"]
    L += [f"| {k} | {pct(v)} |" for k, v in sorted(doc["stress"].items(), key=lambda kv: kv[1])]
    L += ["", "*Scenarios from [[26 - Stress Scenario Library]].*", ""]
    if dt:
        L += ["## Day trader", "", f"- Sessions reviewed: {', '.join(dt['days'][-5:]) or '—'}",
              f"- Closed trades {dt['closed']}, winners {dt['wins']}, P&L ${dt['pnl']:,.2f}, average R {('%+.2f' % dt['avg_r']) if dt['avg_r'] is not None else '—'}",
              f"- Skill pack decisions: " + (", ".join(f"{k} ({n})" for k, n in dt["skill_reasons"]) or "none"), ""]
    L += ["---", "", "[[00 - Bot Dashboard]] · [[12 - Live Day Trading]] · [[15 - Crisis Simulation]] · [[39 - The Monthly Rebalance, Step by Step]] · [[18 - Daily Risk Dashboard and Checks]]", ""]
    return "\n".join(L)


if __name__ == "__main__":
    d = think()
    print("\n".join(d["thoughts"]))
    print(d["alerts"])
