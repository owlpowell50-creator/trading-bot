"""
daytrade.py - the $25,000 day-trading simulator from 'Day Traders/12', run on REAL
intraday prices.

Every trading day it downloads that day's real 5-minute bars for SPY and QQQ from
Alpaca's market-data API and applies the playbook's Opening Range Breakout rules
exactly as written in 'Day Traders/05 - Intraday Setups' and '12 - Day Trading Simulator':

  opening range   09:30-09:45 New York (first three 5-minute bars)
  entry           first 5-minute close above the range high (long) / below the low (short),
                  filled at the NEXT bar's open + 1 bp slippage; no new entries after 15:00
  stop            opposite side of the range (filled at the gap price if a bar opens beyond it)
  target          1.5 x range height from entry
  time exit       flat at the 15:55 bar open, always
  sizing          risk 0.5% of equity per trade, position capped at 20% of equity, whole shares
  limits          1 trade per symbol per day, -$500 daily loss stop, 3 losses in a row = half size,
                  5 in a row = stop for the day, 10% drawdown = full stop
  same-bar rule   if a bar touches both stop and target, the STOP is assumed (conservative)

No orders are sent: the bot's only Alpaca paper account holds the long-term portfolio,
and intraday orders there would mix the two. The prices, times and fills are real
market data; the trades are what the written rules would have done with them.
"""
from __future__ import annotations

import json
import math
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001
    NY = None

from .data import ROOT
from .vault import FM, _write

STATE = ROOT / "state" / "daytrade.json"
SYMBOLS = ["SPY", "QQQ"]
START = "2026-10-26"
CAPITAL = 25_000.0
SLIP = 0.0001
RISK = 0.005
MAX_POS = 0.20
DAY_LOSS = 500.0
TARGET_X = 1.5


def _ny(ts: str) -> datetime:
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return t.astimezone(NY) if NY else t - timedelta(hours=5)


def fetch_bars(http: Callable, day_from: str, day_to: str) -> Dict[str, List[dict]]:
    """5-minute IEX bars for SYMBOLS between two dates (inclusive), all pages."""
    out: Dict[str, List[dict]] = {s: [] for s in SYMBOLS}
    q = {"symbols": ",".join(SYMBOLS), "timeframe": "5Min", "feed": "iex", "adjustment": "raw",
         "start": f"{day_from}T12:00:00Z", "end": f"{(date.fromisoformat(day_to) + timedelta(days=1)).isoformat()}T02:00:00Z",
         "limit": "10000", "sort": "asc"}
    token = None
    for _ in range(50):
        if token:
            q["page_token"] = token
        r = http("GET", "/v2/stocks/bars?" + urllib.parse.urlencode(q))
        for s, bars in (r.get("bars") or {}).items():
            out.setdefault(s, []).extend(bars)
        token = r.get("next_page_token")
        if not token:
            break
    return out


def session_bars(bars: List[dict]) -> Dict[str, List[dict]]:
    """Group regular-session bars (09:30-15:55 NY) by NY date, with hh:mm attached."""
    days: Dict[str, List[dict]] = {}
    for b in bars:
        t = _ny(b["t"])
        hm = t.strftime("%H:%M")
        if "09:30" <= hm <= "15:55":
            days.setdefault(t.date().isoformat(), []).append(dict(b, hm=hm))
    return days


def simulate_day(sym: str, bars: List[dict], equity: float, size_mult: float) -> Optional[dict]:
    """Opening-range breakout on one symbol for one day. Returns the trade or None."""
    if len(bars) < 10 or bars[0]["hm"] != "09:30":
        return None
    rng = [b for b in bars if b["hm"] < "09:45"]
    if len(rng) < 3:
        return None
    hi, lo = max(b["h"] for b in rng), min(b["l"] for b in rng)
    height = hi - lo
    if height <= 0:
        return None
    rest = [b for b in bars if b["hm"] >= "09:45"]
    for i, b in enumerate(rest[:-1]):
        if b["hm"] > "15:00":
            return None
        side = "LONG" if b["c"] > hi else "SHORT" if b["c"] < lo else None
        if not side:
            continue
        nb = rest[i + 1]
        if nb["hm"] >= "15:55":
            return None
        entry = nb["o"] * (1 + SLIP) if side == "LONG" else nb["o"] * (1 - SLIP)
        stop = lo if side == "LONG" else hi
        per_share = (entry - stop) if side == "LONG" else (stop - entry)
        if per_share <= 0:                       # opened beyond the stop: setup invalid
            return None
        target = entry + TARGET_X * height if side == "LONG" else entry - TARGET_X * height
        shares = min(math.floor(equity * RISK * size_mult / per_share), math.floor(equity * MAX_POS / entry))
        if shares < 1:
            return None
        exit_px, reason, exit_hm = None, None, None
        for x in rest[i + 1:]:
            if x["hm"] == "15:55":
                exit_px, reason, exit_hm = x["o"], "Time (15:55)", x["hm"]
                break
            first = x is rest[i + 1]
            if side == "LONG":
                if not first and x["o"] <= stop:
                    exit_px, reason = x["o"], "Stop (gap)"
                elif x["l"] <= stop:
                    exit_px, reason = stop, "Stop"
                elif not first and x["o"] >= target:
                    exit_px, reason = x["o"], "Target (gap)"
                elif x["h"] >= target:
                    exit_px, reason = target, "Target"
            else:
                if not first and x["o"] >= stop:
                    exit_px, reason = x["o"], "Stop (gap)"
                elif x["h"] >= stop:
                    exit_px, reason = stop, "Stop"
                elif not first and x["o"] <= target:
                    exit_px, reason = x["o"], "Target (gap)"
                elif x["l"] <= target:
                    exit_px, reason = target, "Target"
            if exit_px is not None:
                exit_hm = x["hm"]
                break
        if exit_px is None:                      # data ended early: close at last bar's close
            exit_px, reason, exit_hm = rest[-1]["c"], "Time (last bar)", rest[-1]["hm"]
        exit_px = exit_px * (1 - SLIP) if side == "LONG" else exit_px * (1 + SLIP)
        pnl = (exit_px - entry) * shares if side == "LONG" else (entry - exit_px) * shares
        return {"symbol": sym, "side": side, "entry_time": nb["hm"], "exit_time": exit_hm,
                "range_high": round(hi, 4), "range_low": round(lo, 4), "entry": round(entry, 4),
                "stop": round(stop, 4), "target": round(target, 4), "exit": round(exit_px, 4),
                "shares": shares, "risk": round(per_share * shares, 2), "pnl": round(pnl, 2),
                "r": round(pnl / (per_share * shares), 2), "reason": reason}
    return None


def load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"start": START, "capital": CAPITAL, "equity": CAPITAL, "last_day": None, "trades": [],
            "days": [], "stopped": False, "source": "Alpaca market data, IEX feed, 5-minute bars"}


def run(http: Callable, today: str) -> dict:
    """Process every complete trading day since the last one processed."""
    st = load()
    first = (date.fromisoformat(st["last_day"]) + timedelta(days=1)).isoformat() if st["last_day"] else st["start"]
    last = (date.fromisoformat(today) - timedelta(days=1)).isoformat()   # only finished sessions
    if first > last or st.get("stopped"):
        return st
    bars = fetch_bars(http, first, last)
    per = {s: session_bars(b) for s, b in bars.items()}
    days = sorted(set().union(*[set(d) for d in per.values()]))
    peak = max([CAPITAL] + [d["equity"] for d in st["days"]])
    for d in days:
        if d < first or d > last:
            continue
        if not all(len(per[s].get(d, [])) >= 70 for s in SYMBOLS):   # half day / missing data: skip
            st["days"].append({"date": d, "equity": round(st["equity"], 2), "trades": 0, "pnl": 0.0,
                               "note": "skipped - incomplete session data"})
            continue
        day_pnl, n = 0.0, 0
        for s in SYMBOLS:
            if day_pnl <= -DAY_LOSS:
                break
            streak = 0
            for t in reversed(st["trades"]):
                if t["pnl"] < 0:
                    streak += 1
                else:
                    break
            if streak >= 5 and any(t["date"] == d for t in st["trades"]):
                break
            t = simulate_day(s, per[s][d], st["equity"], 0.5 if streak >= 3 else 1.0)
            if t:
                t["date"] = d
                t["n"] = len(st["trades"]) + 1
                st["trades"].append(t)
                st["equity"] += t["pnl"]
                day_pnl += t["pnl"]
                n += 1
        peak = max(peak, st["equity"])
        st["days"].append({"date": d, "equity": round(st["equity"], 2), "trades": n, "pnl": round(day_pnl, 2)})
        if st["equity"] / peak - 1 <= -0.10:
            st["stopped"] = True
            st["stopped_note"] = f"10% drawdown reached on {d} - full stop, review everything"
            break
    st["last_day"] = last
    st["equity"] = round(st["equity"], 2)
    STATE.write_text(json.dumps(st, indent=1))
    return st


def scorecard(st: dict) -> dict:
    tr = st["trades"]
    wins = [t for t in tr if t["pnl"] > 0]
    losses = [t for t in tr if t["pnl"] <= 0]
    peak, mdd = CAPITAL, 0.0
    for d in st["days"]:
        peak = max(peak, d["equity"])
        mdd = min(mdd, d["equity"] / peak - 1)
    gl = abs(sum(t["pnl"] for t in losses))
    return {"n": len(tr), "exp": (sum(t["r"] for t in tr) / len(tr)) if tr else None,
            "win": (len(wins) / len(tr)) if tr else None,
            "aw": (sum(t["pnl"] for t in wins) / len(wins)) if wins else None,
            "al": (sum(t["pnl"] for t in losses) / len(losses)) if losses else None,
            "pf": (sum(t["pnl"] for t in wins) / gl) if gl else None,
            "mdd": mdd, "days": sum(1 for d in st["days"] if "note" not in d),
            "tdays": sum(1 for d in st["days"] if d["trades"])}


def write_note(st: dict, today: str):
    sc = scorecard(st)
    eq = st["equity"]
    f2 = lambda x, fmt: "—" if x is None else fmt % x   # noqa: E731
    L = [FM.format(type="day-trading-simulator", updated=today, extra_tags="\n  - day-trading\n  - simulator"),
         "# 11 - Day Trading Simulator", "",
         "> [!success] Real market data — written automatically after every bot run",
         f"> Source: {st['source']}. Each finished trading day since {st['start']} is replayed bar by bar with the "
         "Opening Range Breakout rules from [[05 - Intraday Setups]] and the limits in [[12 - Day Trading Simulator]]. "
         "Prices and times are real; no orders are sent (the $25,000 is practice money).", ""]
    if st.get("stopped"):
        L += [f"> [!danger] {st['stopped_note']}", ""]
    L += ["## Account", "", "| | |", "|---|---|",
          f"| Started with | ${CAPITAL:,.2f} on {st['start']} |",
          f"| **Equity now** | **${eq:,.2f}** ({(eq / CAPITAL - 1) * 100:+.2f}%) |",
          f"| Days processed through | {st.get('last_day') or '—'} |",
          f"| Instruments | {', '.join(SYMBOLS)} |", "",
          "## Ledger", ""]
    if not st["trades"]:
        L.append("No trades yet — no breakout met the rules, or no finished sessions processed yet.")
    else:
        L += ["| # | Date | Sym | Dir | Range | Entry (time) | Stop | Target | Exit (time) | Shares | P&L $ | R | Exit reason |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for t in reversed(st["trades"]):
            L.append(f"| {t['n']} | {t['date']} | {t['symbol']} | {'🟢 Long' if t['side'] == 'LONG' else '🔴 Short'} | "
                     f"{t['range_low']:.2f}–{t['range_high']:.2f} | {t['entry']:.2f} ({t['entry_time']}) | {t['stop']:.2f} | "
                     f"{t['target']:.2f} | {t['exit']:.2f} ({t['exit_time']}) | {t['shares']} | {t['pnl']:+,.2f} | "
                     f"{t['r']:+.2f} | {t['reason']} |")
    L += ["", "## Scorecard", "", "| Metric | Target | Actual |", "|---|---|---|",
          f"| Trades logged | 100+ | {sc['n']} |",
          f"| Expectancy (R) | > 0.15 | {f2(sc['exp'], '%+.2f')} |",
          f"| Win rate | > 40% | {f2(None if sc['win'] is None else sc['win'] * 100, '%.0f%%')} |",
          f"| Average win : average loss | > 1.5 | {f2(None if not (sc['aw'] and sc['al']) else sc['aw'] / abs(sc['al']), '%.2f')} |",
          f"| Profit factor | > 1.3 | {f2(sc['pf'], '%.2f')} |",
          f"| Max drawdown | < 10% | {sc['mdd'] * 100:.2f}% |",
          "| Rule violations | 0 | 0 (rules are applied by code) |",
          f"| Days processed / days with a trade | — | {sc['days']} / {sc['tdays']} |",
          f"| Equity | — | ${eq:,.2f} |", "",
          "> [!important] Sample size", f"> {sc['n']} trades. Under 30 is noise; under 100 is a hint. Judge it at 100.", "",
          "## Equity by day", "", "| Date | Trades | Day P&L | Equity |", "|---|---|---|---|"]
    for d in reversed(st["days"][-60:]):
        L.append(f"| {d['date']} | {d['trades']} | {d['pnl']:+,.2f} | ${d['equity']:,.2f} |"
                 + (f" {d['note']}" if d.get("note") else ""))
    L += ["", "Back to [[00 - Bot Dashboard]] · rules: [[12 - Day Trading Simulator]]", ""]
    _write(ROOT / "11 - Day Trading Simulator.md", "\n".join(L))
