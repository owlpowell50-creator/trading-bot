"""
daytrade_month.py - one-month simulation of the live day-trader on REAL 5-minute bars.

Same rules and the same account size as the live paper account ('12 - Live Day Trading'):
Opening Range Breakout on SPY and QQQ, 0.5% risk per trade, positions <= 20% of equity,
one trade per symbol per day, stop for the day after a 2% loss, flat by 15:55.
Fills: next bar's open + 1 bp; stops filled at the gap price if a bar opens through them.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from .daytrade import SYMBOLS, fetch_bars, session_bars, simulate_day
from .data import ROOT
from .vault import FM, _write

STATE = ROOT / "state" / "daytrade_month.json"


def simulate(http, start: str, end: str, capital: float = 100_000.0, day_loss_pct: float = 0.02,
             feed: str = "iex", save: bool = True) -> dict:
    bars = fetch_bars(http, start, end, feed)
    per = {s: session_bars(b) for s, b in bars.items()}
    days = sorted(set().union(*[set(d) for d in per.values()]))
    eq, trades, out = capital, [], []
    for d in days:
        if d < start or d > end:
            continue
        if not all(len(per.get(s, {}).get(d, [])) >= 70 for s in SYMBOLS):
            out.append({"date": d, "equity": round(eq, 2), "trades": 0, "pnl": 0.0, "note": "half day / incomplete data"}); continue
        start_eq, n = eq, 0
        for s in SYMBOLS:
            if eq - start_eq <= -day_loss_pct * start_eq:
                break
            streak = 0
            for t in reversed(trades):
                if t["pnl"] < 0: streak += 1
                else: break
            t = simulate_day(s, per[s][d], eq, 0.5 if streak >= 3 else 1.0)
            if t:
                t.update(date=d, n=len(trades) + 1); trades.append(t); eq += t["pnl"]; n += 1
        out.append({"date": d, "equity": round(eq, 2), "trades": n, "pnl": round(eq - start_eq, 2)})
    st = {"start": start, "end": end, "capital": capital, "equity": round(eq, 2), "trades": trades, "days": out,
          "source": f"Alpaca market data, {feed.upper()} feed, 5-minute bars"}
    if save:
        STATE.write_text(json.dumps(st, indent=1))
    return st


def write_note(st: dict, today: str):
    tr, days, cap, eq = st["trades"], st["days"], st["capital"], st["equity"]
    wins = [t for t in tr if t["pnl"] > 0]; losses = [t for t in tr if t["pnl"] <= 0]
    gl = abs(sum(t["pnl"] for t in losses)); pf = sum(t["pnl"] for t in wins) / gl if gl else None
    exp = sum(t["r"] for t in tr) / len(tr) if tr else None
    peak, mdd = cap, 0.0
    for d in days:
        peak = max(peak, d["equity"]); mdd = min(mdd, d["equity"] / peak - 1)
    best = max(days, key=lambda d: d["pnl"]) if days else None; worst = min(days, key=lambda d: d["pnl"]) if days else None
    f = lambda x, s: "—" if x is None else s % x   # noqa: E731
    L = [FM.format(type="day-trading-month", updated=today, extra_tags="\n  - day-trading\n  - simulation"),
         "# 13 - Day Trading Month Simulation", "",
         f"> [!info] One month of the live day-trader's rules on real market data ({st['start']} → {st['end']})",
         f"> {st['source']}. Same rules and the same ${cap:,.0f} account as [[12 - Live Day Trading]]. "
         "Prices are real; the trades are what the rules would have done. No orders were sent.", "",
         "## Result", "", "| | |", "|---|---|",
         f"| Start → end | ${cap:,.2f} → **${eq:,.2f}** ({(eq / cap - 1) * 100:+.2f}%) |",
         f"| Trading days | {sum(1 for d in days if 'note' not in d)} ({sum(1 for d in days if d['trades'])} with a trade) |",
         f"| Trades | {len(tr)} — {len(wins)} winners, {len(losses)} losers |",
         f"| Win rate | {f(len(wins) / len(tr) * 100 if tr else None, '%.0f%%')} |",
         f"| Expectancy | {f(exp, '%+.2f R per trade')} |",
         f"| Profit factor | {f(pf, '%.2f')} |",
         f"| Max drawdown | {mdd * 100:.2f}% |",
         f"| Best day | {best['date']} {best['pnl']:+,.2f} |" if best else "| Best day | — |",
         f"| Worst day | {worst['date']} {worst['pnl']:+,.2f} |" if worst else "| Worst day | — |", "",
         "> [!important] Read it honestly",
         f"> {len(tr)} trades is a small sample — under 30 is noise, under 100 a hint. One month says little about whether the edge is real.", ""]
    if len(days) >= 2:
        eqs = [cap] + [d["equity"] for d in days]
        L += ["## Equity curve", "", "```mermaid", "xychart-beta", '  title "Day-trading account (simulated month)"',
              "  x-axis [" + ", ".join(['"start"'] + [f'"{d["date"][5:]}"' for d in days]) + "]",
              f"  y-axis \"$\" {min(eqs) * 0.998:.0f} --> {max(eqs) * 1.002:.0f}",
              "  line [" + ", ".join(f"{v:.0f}" for v in eqs) + "]", "```", ""]
    L += ["## Day by day", "", "| Date | Trades | Day P&L | Equity |", "|---|---|---|---|"]
    for d in days:
        L.append(f"| {d['date']} | {d['trades']} | {d['pnl']:+,.2f} | ${d['equity']:,.2f} |" + (f" {d['note']}" if d.get("note") else ""))
    L += ["", "## Every trade", ""]
    if tr:
        L += ["| # | Date | Sym | Dir | Entry (time) | Stop | Target | Exit (time) | Shares | P&L $ | R | Exit |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for t in tr:
            L.append(f"| {t['n']} | {t['date']} | {t['symbol']} | {'Long' if t['side'] == 'LONG' else 'Short'} | {t['entry']:.2f} ({t['entry_time']}) | "
                     f"{t['stop']:.2f} | {t['target']:.2f} | {t['exit']:.2f} ({t['exit_time']}) | {t['shares']} | {t['pnl']:+,.2f} | {t['r']:+.2f} | {t['reason']} |")
    else:
        L.append("No trades — no breakout met the rules.")
    L += ["", "Live results: [[12 - Live Day Trading]] · rules: [[12 - Day Trading Simulator]] · [[00 - Bot Dashboard]]", ""]
    _write(ROOT / "13 - Day Trading Month Simulation.md", "\n".join(L))
