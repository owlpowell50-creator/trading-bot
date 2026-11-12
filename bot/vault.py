"""
vault.py - writes the bot's output into your Obsidian vault as notes.

  Bot/00 - Bot Dashboard.md        live status, holdings, equity, last decision
  Bot/03 - Backtest Report.md      the full 1997-2026 evaluation (regenerated)
  Bot/Journal/YYYY-MM-DD.md        one note per run: data check, signal, risk, orders
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, List

from .config import INSTRUMENTS as _EU, US_INSTRUMENTS as _US
from .data import ASSET_NAMES, ROOT

FM = """---
type: {type}
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: {updated}
tags:
  - type/{type}
  - department/trading
  - trading-bot{extra_tags}
---
"""


def pct(x, d=1):
    return "–" if x is None else f"{x * 100:+.{d}f}%"


def pct0(x, d=1):
    return "–" if x is None else f"{x * 100:.{d}f}%"


def money(x):
    return f"{x:,.0f}"


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


_CUR = {"map": _US}


def _ins(a: str) -> dict:
    return _CUR["map"].get(a, {"symbol": a, "name": a, "isin": ""})


def _id(ins: dict) -> str:
    return f"`{ins['isin']}`" if ins.get("isin") else "US-listed"


def asset_label(a: str) -> str:
    ins = _ins(a)
    return f"{ASSET_NAMES.get(a, a)} — {ins.get('symbol', '')}"


# ------------------------------------------------------------------ journal
def write_journal(run: dict) -> Path:
    _CUR["map"] = run.get("instruments") or _US
    d = run["date"]
    lines = [FM.format(type="trade-journal", updated=d, extra_tags="\n  - bot-journal"),
             f"# Bot run {d}", "",
             f"**Mode:** `{run['mode']}` · **Strategy:** `{run['strategy']}` · "
             f"**Data through:** {run['data_through']}", ""]
    status = run["status"]
    icon = {"TRADED": "success", "NO CHANGE": "info", "BLOCKED": "danger", "HALTED": "danger",
            "HOLD": "info"}.get(status, "note")
    lines += [f"> [!{icon}] {status}", f"> {run['headline']}", ""]
    if run.get("problems"):
        lines += ["## Problems that stopped trading", ""] + [f"- {p}" for p in run["problems"]] + [""]
    lines += ["## Account", "",
              "| | |", "|---|---|",
              f"| Equity | {money(run['equity'])} |",
              f"| Peak | {money(run['peak'])} |",
              f"| Drawdown from peak | {pct(run['drawdown'])} (halt at {pct0(-run['halt_at'], 0)}) |",
              ""]
    if run.get("signal"):
        sig = run["signal"]
        lines += ["## Signal", "",
                  f"Signal date (month-end close): **{sig['date']}**", "",
                  "| Asset | Momentum score (avg 3/6/12m) | Beats T-bills? |", "|---|---|---|"]
        cash = sig["scores"].get("CASH")
        for a, v in sorted(sig["scores"].items(), key=lambda kv: -kv[1]):
            if a == "CASH":
                continue
            lines.append(f"| {asset_label(a)} | {pct(v)} | {'yes' if cash is not None and v > cash else 'no'} |")
        if cash is not None:
            lines.append(f"| *T-bills (hurdle)* | {pct(cash)} | – |")
        lines.append("")
    lines += ["## Holdings: before → target", "", "| Asset | Before | Target |", "|---|---|---|"]
    for a in sorted(set(run["weights_before"]) | set(run["weights_target"]),
                    key=lambda x: -run["weights_target"].get(x, 0)):
        lines.append(f"| {asset_label(a)} | {pct0(run['weights_before'].get(a, 0))} | "
                     f"{pct0(run['weights_target'].get(a, 0))} |")
    lines.append("")
    if run.get("risk_notes"):
        lines += ["## Risk adjustments", ""] + [f"- {n}" for n in run["risk_notes"]] + [""]
    if run.get("orders"):
        lines += ["## Orders", "", "| Side | Instrument | ID | Value |", "|---|---|---|---|"]
        for o in run["orders"]:
            ins = _ins(o["asset"])
            lines.append(f"| {o['side']} | {ins['symbol']} ({ins['name']}) | {_id(ins)} | {money(o['value'])} |")
        lines.append("")
    if run.get("fills"):
        lines += ["## Fills", "", "| Side | Asset | Units | Price | Value | Fee |", "|---|---|---|---|---|---|"]
        for f in run["fills"]:
            lines.append(f"| {f['side']} | {f['asset']} | {f['units']:.4f} | {f['price']:.4f} | "
                         f"{money(f['value'])} | {f.get('fee', 0):.2f} |")
        lines.append("")
    if run.get("scenarios"):
        lines += ["## How much could I lose? (today's holdings)", "",
                  "Actual asset moves from past crashes applied to the target book. "
                  "Scenarios are not limits: gaps and illiquidity can make real losses bigger. "
                  "See [[13 - How Much Could I Lose?]].", "",
                  "| Scenario | Return | Loss |", "|---|---|---|"]
        for sc in run["scenarios"]:
            lines.append(f"| {sc['scenario']} | {pct(sc['return'])} | {money(sc['loss_value'])} |")
        lines.append("")
    lines += ["---", "Rules behind this run: [[01 - How the Bot Works]] · Limits: [[02 - Risk Limits]] · "
              "Evidence: [[03 - Backtest Report]]", ""]
    p = ROOT / "Journal" / f"{d}.md"
    k = 2
    while p.exists():            # never overwrite an earlier run's record
        p = ROOT / "Journal" / f"{d} (run {k}).md"
        k += 1
    if run.get("dry_run"):
        p = ROOT / "Journal" / f"{d} dry-run.md"
    _write(p, "\n".join(lines))
    return p


# ------------------------------------------------------------------ dashboard
def write_dashboard(run: dict, history: List[tuple], recent: List[dict]):
    _CUR["map"] = run.get("instruments") or _US
    d = run["date"]
    lines = [FM.format(type="dashboard", updated=d, extra_tags="\n  - type/dashboard"),
             "# Trading Bot — Dashboard", "",
             f"> [!{'danger' if run['status'] in ('BLOCKED', 'HALTED') else 'success' if run['status'] == 'TRADED' else 'info'}] "
             f"🤖 Bot is {'PAUSED' if run['status'] in ('BLOCKED', 'HALTED') else 'ACTIVE'} — last run {d} at {run.get('time', '')}: **{run['status']}**",
             f"> {run['headline']}",
             f"> Next scheduled rebalance: **{next_rebalance(d)}** (first trading day of the month). "
             f"Every other weekday it checks prices and risk, and writes a journal.", "",
             f"**Mode:** `{run['mode']}` · **Region:** `{run.get('region', 'us')}` · "
             f"**Strategy:** `{run['strategy']}` · **Data through:** {run['data_through']}", "",
             "## Account", "", "| | |", "|---|---|",
             f"| Equity | {money(run['equity'])} |",
             f"| Started with | {money(run.get('start_capital', 0))} |",
             f"| Return since start | {pct(run['equity'] / run['start_capital'] - 1 if run.get('start_capital') else None)} |",
             f"| Peak | {money(run['peak'])} |",
             f"| Drawdown | {pct(run['drawdown'])} (halt at {pct0(-run['halt_at'], 0)}) |", "",
             "## Holdings now", "", "| Asset | Weight | Instrument |", "|---|---|---|"]
    for a, w in sorted(run["weights_after"].items(), key=lambda kv: -kv[1]):
        if w < 0.001:
            continue
        ins = _ins(a)
        lines.append(f"| {ASSET_NAMES.get(a, a)} | {pct0(w)} | {ins['symbol']} ({_id(ins)}) |")
    lines += [""] + mermaid_pie("What the bot holds now", run["weights_after"])
    lines += ["", "## Recent runs", "", "| Date | Status | Equity |", "|---|---|---|"]
    for r in recent[-12:][::-1]:
        lines.append(f"| [[{r['date']}]] | {r['status']} | {money(r['equity'])} |")
    if len(history) > 1:
        h = history[-60:]
        lines += ["", "## Equity"] + mermaid_lines("Paper account value", [x[0][5:] for x in h],
                                                    {"Equity": [x[1] for x in h]}, "Value")
    lines += ["", "## Notes", "",
              "- [[06 - One-Month Trial]] — **live paper trial vs the S&P 500**",
              "- [[07 - Trade Log]] — every buy and sell",
              "- [[08 - Last 12 Months Replay]] — every trade it would have made in the past year",
              "- [[09 - Upgrades Tested]] — ideas tested to make it smarter, and why most were rejected",
              "- [[01 - How the Bot Works]] — the rules, in plain words",
              "- [[02 - Risk Limits]] — **edit this to change the bot's settings**",
              "- [[03 - Backtest Report]] — 1997–2026 evidence incl. every crash",
              "- [[04 - How to Run It]] — commands, schedule, going live",
              "- [[05 - Fixes to the Old Engine]] — what was broken and what changed", ""]
    _write(ROOT / "00 - Bot Dashboard.md", "\n".join(lines))


# ------------------------------------------------------------------ backtest report
def write_backtest_report(res: dict, cfg: dict):
    S = res["strategies"]
    order = ["CORE", "GEM", "TREND", "SPY-TREND", "60/40", "SPY"]
    order = [k for k in order if k in S]
    L = [FM.format(type="backtest-report", updated=res["generated"], extra_tags="\n  - backtest"),
         "# Backtest Report — 1997 to today, every crash included", "",
         f"Period **{res['start']} → {res['end']}** · costs **{res['cost_bps']:.0f} bps** per unit traded · "
         f"signal at month-end close, filled at the **next day's** close · "
         f"vol cap **{res['vol_cap']:.1%}** (from a {cfg['worst_month_loss']:.0%} worst month, see [[08 - Risk Limits and Escalation]]) · "
         f"max **{cfg['max_single_asset']:.0%}** in one asset · no-trade band **{res['band']:.0%}**.", "",
         "Before an ETF existed its Vanguard mutual-fund twin is used (VFINX→SPY, VGTSX→EFA, VFITX→IEF, "
         "VUSTX→TLT, VGSIX→VNQ); cash earns the 3-month T-bill rate. Dividends are reinvested in every series.", "",
         "## The short version", ""]
    c, spy, s64 = S["CORE"], S["SPY"], S["60/40"]
    wf = res["walk_forward"]
    us = str(cfg.get("region", "us")).lower() == "us"
    st_r, lt_r = res.get("us_rates", (0.29, 0.20))
    L += [f"> [!summary] What the evidence says",
          f"> - **CORE made {pct0(c['cagr'])}/yr** vs **{pct0(spy['cagr'])}/yr** for the S&P 500 and "
          f"{pct0(s64['cagr'])}/yr for 60/40 — about the same return as stocks, with **half the volatility**.",
          f"> - **Worst fall: {pct(c['max_dd'])}** vs **{pct(spy['max_dd'])}** for the S&P 500 "
          f"(and {pct(s64['max_dd'])} for 60/40). That is the whole point of the bot."]
    if us:
        L += [f"> - **Taxes decide where to run it.** In an **IRA / Roth IRA** (no tax on trades) CORE keeps "
              f"**{pct0(c['cagr'])}/yr** vs {pct0(spy['cagr'])}/yr for the S&P 500. In a normal **taxable** account "
              f"(short-term gains and interest at {st_r:.0%}, long-term and dividends at {lt_r:.0%}) it drops to "
              f"**{pct0(c['after_tax_us_cagr'])}/yr** while buy-and-hold S&P keeps **{pct0(spy['after_tax_us_cagr'])}/yr**, "
              f"because the bot's gains are mostly short-term and its bond income is taxed every year."]
    else:
        L += [f"> - **After 26% Italian tax** (ETF gains taxed every time it sells; ETF losses can't offset ETF gains) "
              f"CORE drops to **{pct0(c['after_tax_cagr'])}/yr**, while buy-and-hold S&P 500 keeps **{pct0(spy['after_tax_cagr'])}/yr** "
              f"because it never sells. *If you can sit through a {pct0(-spy['max_dd'], 0)} crash without selling, "
              f"buy-and-hold made more money.* The bot is for not having to."]
    L += [f"> - **Honest forward estimate:** re-choosing the settings each year using only past data "
          f"(walk-forward) gave **{pct0(wf['cagr'])}/yr** with a **{pct(wf['max_dd'])}** worst fall. "
          f"Across 36 nearby settings the median was {pct0(_median([g['cagr'] for g in res['grid']]))}/yr. "
          f"Expect something in that range, not the best number above.",
          f"> - **Luck test:** in {res['bootstrap_vs_6040']['p_beat']:.0%} of 2,000 reshuffled histories CORE beat 60/40; "
          f"vs the S&P 500 it was a coin flip ({res['bootstrap_vs_spy']['p_beat']:.0%}). The edge is in "
          f"**risk**, not in raw return.", ""]
    L += ["## Head to head", "",
          "| | " + " | ".join(order) + " |", "|---|" + "---|" * len(order)]
    rows = [("Return per year (= in an IRA / Roth IRA)", "cagr", pct0),
            ("After tax, US taxable account", "after_tax_us_cagr", pct0),
            ("After tax, Italy", "after_tax_cagr", pct0),
            ("Volatility", "vol", pct0), ("Sharpe (vs T-bills)", "sharpe", lambda x: f"{x:.2f}"),
            ("Worst fall (max drawdown)", "max_dd", pct), ("Worst calendar year", "worst_year", pct),
            ("Best calendar year", "best_year", pct), ("Worst month", "worst_month", pct),
            ("Months up", "pct_up_months", pct0), ("Longest time below a previous peak (days)",
                                                   "longest_underwater_days", lambda x: f"{x:,}"),
            ("$1 grew to", "final_multiple", lambda x: f"${x:.2f}"),
            ("Trades per year", "trades_per_year", lambda x: f"{x:.1f}"),
            ("Cost drag per year", "cost_drag_per_year", lambda x: f"{x * 100:.2f}%")]
    for lab, k, f in rows:
        L.append(f"| {lab} | " + " | ".join(f(S[n][k]) for n in order) + " |")
    L += ["", "Strategies: " + "; ".join(f"**{n}** — {S[n]['description']}" for n in order), ""]

    L += ["## The downs — every crash", "", "| Crash | Dates | " + " | ".join(order) + " |",
          "|---|---|" + "---|" * len(order)]
    for cr in res["crashes"]:
        L.append(f"| {cr['name']} | {cr['start']} → {cr['end']} | " + " | ".join(pct(cr.get(n)) for n in order) + " |")
    L += ["", "> [!warning] Where CORE is weak",
          "> Fast sell-offs that start and finish between two month-ends (Q4 2018, April 2025) hit it "
          "before the month-end signal can react. Its protection comes from *slow* bear markets (2000-02, 2008, 2022).", ""]
    L += ["## The ups — every rally", "", "| Rally | Dates | " + " | ".join(order) + " |",
          "|---|---|" + "---|" * len(order)]
    for cr in res["rallies"]:
        L.append(f"| {cr['name']} | {cr['start']} → {cr['end'][:10]} | " + " | ".join(pct(cr.get(n)) for n in order) + " |")
    L += ["", "CORE gives up a lot in roaring bull markets (2009-2020 especially): it holds bonds, gold and cash "
          "alongside stocks. That is the price of the crash protection.", ""]
    L += ["## Year by year", "", "| Year | " + " | ".join(order) + " |", "|---|" + "---|" * len(order)]
    for y in sorted(res["years"]):
        L.append(f"| {y} | " + " | ".join(pct(res['years'][y].get(n)) for n in order) + " |")
    L += ["", "*(first and last years are partial)*", ""]
    L += ["## Is it one lucky setting? (robustness)", "",
          f"36 neighbouring settings (top 2/3/4 assets × 4 lookback sets × vol cap ±25%): return per year "
          f"min **{pct0(min(g['cagr'] for g in res['grid']))}**, median **{pct0(_median([g['cagr'] for g in res['grid']]))}**, "
          f"max **{pct0(max(g['cagr'] for g in res['grid']))}**; worst fall median **{pct(_median([g['max_dd'] for g in res['grid']]))}**, "
          f"worst **{pct(min(g['max_dd'] for g in res['grid']))}**.", "",
          "| Top | Lookbacks (months) | Vol cap | Return/yr | Worst fall | Sharpe |", "|---|---|---|---|---|---|"]
    for g in sorted(res["grid"], key=lambda g: -g["cagr"]):
        L.append(f"| {g['top_k']} | {g['lookbacks']} | {g['vol_cap']:.1%} | {pct0(g['cagr'])} | {pct(g['max_dd'])} | {g['sharpe']:.2f} |")
    L += ["", "The chosen setting (top 3, 3/6/12 months) is near the top of this table. It was picked from the "
          "published research before testing, but treat the median as the realistic number.", ""]
    L += ["## Walk-forward (settings chosen only from the past)", "",
          f"Return {pct0(wf['cagr'])}/yr · worst fall {pct(wf['max_dd'])} · Sharpe {wf['sharpe']:.2f}", "",
          "Choices made each January: " + ", ".join(f"{y}: `{n}`" for y, n in wf["choices"]), ""]
    L += ["## Costs", "", "| Cost per unit traded | Return/yr | Worst fall |", "|---|---|---|"]
    for k, (cg, dd) in res["cost_sensitivity"].items():
        L.append(f"| {k} bps | {pct0(cg)} | {pct(dd)} |")
    L += ["", "Real UCITS ETF spreads at IBKR are usually a few bps; 10 bps is a cautious all-in assumption. "
          "See [[11 - Is the Potential Edge Bigger Than the Costs?]].", ""]
    L += ["## First half vs second half", "", "| | 1997–2011 return | 1997–2011 worst fall | 2012–2026 return | 2012–2026 worst fall |",
          "|---|---|---|---|---|"]
    for n in order:
        h = res["halves"][n]
        L.append(f"| {n} | {pct0(h['first'][0])} | {pct(h['first'][1])} | {pct0(h['second'][0])} | {pct(h['second'][1])} |")
    L += ["", "Stocks were terrible in the first half and superb in the second; CORE was steadier in both.", ""]
    dd = res["expected_drawdowns_10y"]
    L += ["## What drawdown should I expect? (10-year bootstrap)", "",
          "| | Typical (median) | 1-in-10 | 1-in-20 | 1-in-100 |", "|---|---|---|---|---|"]
    for n in ("CORE", "60/40", "SPY"):
        x = dd[n]
        L.append(f"| {n} | {pct(x['median'])} | {pct(x['p10'])} | {pct(x['p5'])} | {pct(x['p1'])} |")
    L += ["", "Resampled 12-month blocks of real history. The 1-in-100 line is what to plan for, not the median.", ""]
    if res.get("eur"):
        L += ["## In euros (what you actually experience)", "",
              "| | From | Return/yr in EUR | Worst fall in EUR | Volatility |", "|---|---|---|---|---|"]
        for n, x in res["eur"].items():
            L.append(f"| {n} | {x['start']} | {pct0(x['cagr'])} | {pct(x['max_dd'])} | {pct0(x['vol'])} |")
        L += ["", "The ETFs hold US-dollar assets, so EUR/USD moves add to or subtract from your returns. "
              "Since 2004 the dollar's strength helped.", ""]
    L += ["## What this test cannot tell you", "",
          "- The future is not the past. Trend and momentum have long histories, but they can stop working for years.",
          "- Every number is from **one** history. The bootstrap above helps, but crashes nobody has seen before can happen.",
          "- Taxes are simplified. US: FIFO lots, 1-year short/long split, yearly netting and loss carry-forward, "
          "dividends/interest taxed yearly, wash-sale rule and state details ignored. Italy: 26%, average cost, "
          "losses banked 4 years. Check with a tax professional in the country that taxes you.",
          "- The ETFs it trades track the same indexes as the funds whose history drives the signal, but some are younger "
          "or cheaper share classes (VOO for SPY, IEFA for EFA, GLDM for GLD, PDBC for DBC).",
          "", "Related: [[Guide - Backtesting]] · [[07 - Model Risk and Assumption Failure]] · "
          "[[02 - Momentum and Trend Following]] · [[05 - Drawdowns and Recovery]]", ""]
    _write(ROOT / "03 - Backtest Report.md", "\n".join(L))


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


# ------------------------------------------------------------------ trial
def write_trial(t: dict):
    days = t["days"]
    last = days[-1] if days else None
    st = t["settings"]
    L = [FM.format(type="trial", updated=last["date"] if last else t["start"], extra_tags="\n  - paper-trial"),
         "# 06 - One-Month Paper Trial", "",
         f"**{t['start']} → {t['end']}** · account `{st.get('mode', 'paper')}` starting at {money(t['start_equity'])} · "
         f"settings: worst month {st['worst_month_loss']:.0%} (vol cap {t['vol_cap']:.1%}), "
         f"max {st['max_single_asset']:.0%} per ETF, region `{st['region']}`", ""]
    if last:
        diff = last["bot"] - last["spy"]
        state = "Finished" if t.get("finished") else f"Day {len(days)}"
        L += [f"> [!{'success' if diff >= 0 else 'warning'}] {state}: bot {pct(last['bot'])} vs S&P 500 {pct(last['spy'])}",
              f"> Equity {money(last['equity'])} · {'ahead' if diff >= 0 else 'behind'} by {abs(diff) * 100:.1f} points "
              f"(prices through {last['data_through']})", ""]
    L += ["## Daily log", "", "| Run | Prices through | Equity | Bot | S&P 500 | Difference |", "|---|---|---|---|---|---|"]
    for d in days:
        L.append(f"| [[{d['date']}]] | {d['data_through']} | {money(d['equity'])} | {pct(d['bot'])} | {pct(d['spy'])} | "
                 f"{pct(d['bot'] - d['spy'])} |")
    if len(days) > 1:
        L += [""] + mermaid_lines("Return since start (%)", [d["date"][5:] for d in days],
                                  {"Bot": [d["bot"] * 100 for d in days],
                                   "S&P 500": [d["spy"] * 100 for d in days]}, "%")
    L += ["", "## How to read this", "",
          "- One month is **noise**, not evidence. In the 30-year backtest the bot trailed the S&P 500 in about "
          "half of all months and still finished with similar returns and a third of the crash damage.",
          "- The bot rebalances once a month, on the first trading day after the month-end. Expect one rebalance "
          "inside this trial.",
          "- What to check: that it ran every weekday, followed its rules, and that the journal explains every trade. "
          "That is what this month can prove.", "",
          "Related: [[00 - Bot Dashboard]] · [[03 - Backtest Report]] · [[02 - Risk Limits]]", ""]
    _write(ROOT / "06 - One-Month Trial.md", "\n".join(L))


# ------------------------------------------------------------------ visuals (Mermaid is built into Obsidian)
def mermaid_pie(title: str, weights: Dict[str, float]) -> List[str]:
    out = ["```mermaid", f"pie showData title {title}"]
    for a, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        if w >= 0.005:
            out.append(f'    "{ASSET_NAMES.get(a, a)} ({_ins(a)["symbol"]})" : {w * 100:.1f}')
    return out + ["```"]


def mermaid_lines(title: str, labels: List[str], series: Dict[str, List[float]], y_label: str) -> List[str]:
    vals = [v for xs in series.values() for v in xs]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.1 or 1
    out = ["```mermaid", "xychart-beta", f'    title "{title}"',
           "    x-axis [" + ", ".join(f'"{l}"' for l in labels) + "]",
           f'    y-axis "{y_label}" {lo - pad:.0f} --> {hi + pad:.0f}']
    for name, xs in series.items():
        out.append("    line [" + ", ".join(f"{x:.1f}" for x in xs) + "]")
    out.append("```")
    names = list(series)
    if len(names) > 1:
        out.append("*Lines: " + " · ".join(f"{'first' if k == 0 else 'second' if k == 1 else str(k + 1)} = **{n}**"
                                          for k, n in enumerate(names)) + "*")
    return out


def next_rebalance(today: str) -> str:
    from datetime import date as _d, timedelta
    t = _d.fromisoformat(today)
    first = (t.replace(day=1) + timedelta(days=32)).replace(day=1)
    while first.weekday() >= 5:
        first += timedelta(days=1)
    return first.isoformat()


def write_trade_log(fills: List[dict], instruments: Dict[str, dict], updated: str):
    _CUR["map"] = instruments
    L = [FM.format(type="trade-log", updated=updated, extra_tags="\n  - trade-log"),
         "# 07 - Trade Log", "",
         "Every order the bot has filled in this account, newest first. Written automatically after each run.", ""]
    if not fills:
        L += ["> [!info] No trades yet"]
    else:
        buys = sum(f["value"] for f in fills if f["side"] == "BUY")
        sells = sum(f["value"] for f in fills if f["side"] == "SELL")
        fees = sum(f.get("fee", 0) for f in fills)
        L += [f"> [!success] {len(fills)} fills · bought {money(buys)} · sold {money(sells)} · costs paid {fees:,.2f}", "",
              "| Date | Side | ETF | What it is | Value | Cost | Account |", "|---|---|---|---|---|---|---|"]
        for f in sorted(fills, key=lambda f: f.get("at", f["date"]), reverse=True):
            ins = _ins(f["asset"])
            side = "🟢 BUY" if f["side"] == "BUY" else "🔴 SELL"
            L.append(f"| [[{f['date']}]] | {side} | **{ins['symbol']}** | {ASSET_NAMES.get(f['asset'], f['asset'])} | "
                     f"{money(f['value'])} | {f.get('fee', 0):.2f} | {f.get('environment', '')} |")
    L += ["", "Back to [[00 - Bot Dashboard]]", ""]
    _write(ROOT / "07 - Trade Log.md", "\n".join(L))


def write_replay(rep: dict, instruments: Dict[str, dict]):
    """What the bot would have done over the last 12 months (real prices, backtest)."""
    _CUR["map"] = instruments
    L = [FM.format(type="replay", updated=rep["generated"], extra_tags="\n  - backtest"),
         "# 08 - Last 12 Months: Every Trade the Bot Would Have Made", "",
         "> [!note] This is a replay, not live trading",
         "> The current rules run on real market prices from the past year, starting with 10,000 on "
         f"{rep['start']}. Costs included. The live paper account is in [[06 - One-Month Trial]] and [[07 - Trade Log]].", "",
         f"> [!{'success' if rep['bot_ret'] >= rep['spy_ret'] else 'warning'}] Result: bot {pct(rep['bot_ret'])} "
         f"(worst fall {pct(rep['bot_dd'])}) vs S&P 500 {pct(rep['spy_ret'])} (worst fall {pct(rep['spy_dd'])})", ""]
    L += mermaid_lines("10,000 invested: bot vs S&P 500", rep["labels"],
                       {"Bot": rep["bot_curve"], "S&P 500": rep["spy_curve"]}, "Value")
    L += ["", "## Month by month", ""]
    for m in rep["months"]:
        L += [f"### {m['date']} — rebalance", ""]
        if m["changes"]:
            L += ["| Action | ETF | Change | New weight |", "|---|---|---|---|"]
            for c in m["changes"]:
                ins = _ins(c["asset"])
                act = "🟢 BUY" if c["delta"] > 0 else "🔴 SELL"
                L.append(f"| {act} | **{ins['symbol']}** ({ASSET_NAMES.get(c['asset'], c['asset'])}) | "
                         f"{c['delta'] * 100:+.1f} pts | {c['new'] * 100:.1f}% |")
        else:
            L.append("No trades — holdings were already within the no-trade band.")
        L += ["", f"Holdings: " + ", ".join(f"{_ins(a)['symbol']} {w * 100:.0f}%" for a, w in
                                             sorted(m["weights"].items(), key=lambda kv: -kv[1]) if w >= 0.005),
              f"Until the next rebalance: **bot {pct(m['bot'])}** vs S&P 500 {pct(m['spy'])}", ""]
    L += ["Back to [[00 - Bot Dashboard]] · Full 30-year evidence: [[03 - Backtest Report]]", ""]
    _write(ROOT / "08 - Last 12 Months Replay.md", "\n".join(L))
