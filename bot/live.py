"""
live.py - the bot's REAL Alpaca paper account, written into Obsidian.

  snapshot(broker)            -> dict with account, positions, filled orders, daily equity
  write_live_account(snap)    -> Bot/10 - Live Paper Account.md

Every number in that note comes from Alpaca's API on the day of the run.
Sections have stable headings so other notes can embed them, e.g.
  ![[10 - Live Paper Account#Positions]]
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .data import ASSET_NAMES, ROOT
from .vault import FM, _write

STATE = ROOT / "state"
SNAP = STATE / "alpaca_snapshot.json"


def snapshot(broker) -> dict:
    """Pull everything worth showing from Alpaca. Read-only calls."""
    h = broker.http
    acct = h("GET", "/v2/account")
    positions = h("GET", "/v2/positions")
    orders = h("GET", "/v2/orders?status=closed&limit=500&direction=asc&nested=false")
    try:
        hist = h("GET", "/v2/account/portfolio/history?period=1A&timeframe=1D")
    except Exception:  # noqa: BLE001
        hist = {}
    snap = {"taken_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "environment": broker.cfg["mode"].upper(),
            "account": {k: acct.get(k) for k in ("account_number", "status", "currency", "equity", "last_equity",
                                                 "cash", "buying_power", "portfolio_value", "long_market_value",
                                                 "created_at", "pattern_day_trader", "daytrade_count")},
            "positions": [{k: p.get(k) for k in ("symbol", "qty", "avg_entry_price", "current_price", "market_value",
                                                 "cost_basis", "unrealized_pl", "unrealized_plpc",
                                                 "unrealized_intraday_pl", "change_today", "lastday_price")}
                          for p in positions],
            "orders": [{k: o.get(k) for k in ("id", "symbol", "side", "status", "filled_qty", "filled_avg_price",
                                              "filled_at", "submitted_at", "notional", "type")}
                       for o in orders if o.get("status") == "filled"],
            "history": {"timestamp": hist.get("timestamp") or [], "equity": hist.get("equity") or []}}
    if acct.get("account_number"):
        n = str(acct["account_number"])
        snap["account"]["account_number"] = "•••" + n[-4:]       # never write the full number
    SNAP.write_text(json.dumps(snap, indent=1))
    return snap


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def realized_pnl(orders: List[dict]) -> Dict[str, float]:
    """FIFO realised P&L per symbol from filled orders."""
    lots: Dict[str, List[list]] = {}
    out: Dict[str, float] = {}
    for o in sorted(orders, key=lambda o: o.get("filled_at") or ""):
        s, q, p = o["symbol"], _f(o["filled_qty"]), _f(o["filled_avg_price"])
        if o["side"] == "buy":
            lots.setdefault(s, []).append([q, p])
        else:
            pnl, left = 0.0, q
            while left > 1e-9 and lots.get(s):
                lq, lp = lots[s][0]
                take = min(lq, left)
                pnl += take * (p - lp)
                left -= take
                lots[s][0][0] -= take
                if lots[s][0][0] <= 1e-9:
                    lots[s].pop(0)
            out[s] = out.get(s, 0.0) + pnl
    return out


try:
    from zoneinfo import ZoneInfo
    _NY = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001
    _NY = timezone.utc


def equity_series(snap: dict, start_capital: float, local: List[tuple]) -> List[tuple]:
    """Daily equity: Alpaca's portfolio history, falling back to the bot's own log."""
    ts, eq = snap["history"]["timestamp"], snap["history"]["equity"]
    rows = []
    for t, e in zip(ts, eq):
        if e is None or e == 0:
            continue
        rows.append((datetime.fromtimestamp(t, timezone.utc).astimezone(_NY).date().isoformat(), float(e)))   # New York trading date
    if not rows:
        rows = list(local)
    rows = [r for r in rows if r[1] > 0.5 * start_capital]          # drop pre-funding zeros
    return rows


def stats(rows: List[tuple], start_capital: float) -> dict:
    if not rows:
        return {}
    peak, mdd = -1.0, 0.0
    for _, e in rows:
        peak = max(peak, e)
        mdd = min(mdd, e / peak - 1)
    rets = [rows[i][1] / rows[i - 1][1] - 1 for i in range(1, len(rows))]
    sharpe = None
    if len(rets) >= 20:
        m = sum(rets) / len(rets)
        sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
        sharpe = m / sd * math.sqrt(252) if sd else None
    return {"total": rows[-1][1] / start_capital - 1, "mdd": mdd, "sharpe": sharpe,
            "days": len(rows), "best": max(rets) if rets else None, "worst": min(rets) if rets else None}


def write_live_account(snap: dict, instruments: Dict[str, dict], start_capital: float,
                       local_equity: List[tuple], today: str):
    by_sym = {v["symbol"]: a for a, v in instruments.items()}
    a = snap["account"]
    equity, last = _f(a.get("equity")), _f(a.get("last_equity"))
    rows = equity_series(snap, start_capital, local_equity)
    if equity and (not rows or rows[-1][0] < today):
        rows.append((today, equity))            # Alpaca's history stops at the last close
    st = stats(rows, start_capital)
    real = realized_pnl(snap["orders"])
    unreal = sum(_f(p["unrealized_pl"]) for p in snap["positions"])
    L = [FM.format(type="live-account", updated=today, extra_tags="\n  - live-account\n  - alpaca"),
         "# 10 - Live Paper Account", "",
         f"> [!success] Real data from Alpaca ({snap['environment']}) — pulled {snap['taken_at'][:16].replace('T', ' ')} UTC",
         "> Every number on this page comes from the broker's API: the trades really happened in Alpaca's "
         "paper-trading account, at real market prices. Paper means the $100,000 is practice money, not your savings.",
         "", "## Account", "",
         "| | |", "|---|---|",
         f"| Account | {a.get('account_number') or '—'} · {a.get('status') or ''} · {a.get('currency') or 'USD'} |",
         f"| Started with | ${start_capital:,.2f} on 2026-11-12 |",
         f"| **Equity now** | **${equity:,.2f}** |",
         f"| Change since start | {equity - start_capital:+,.2f} ({(equity / start_capital - 1) * 100:+.2f}%) |",
         f"| Change today | {equity - last:+,.2f} ({((equity / last - 1) * 100) if last else 0:+.2f}%) |",
         f"| Invested | ${_f(a.get('long_market_value')):,.2f} |",
         f"| Cash | ${_f(a.get('cash')):,.2f} |",
         f"| Unrealised P&L (open positions) | {unreal:+,.2f} |",
         f"| Realised P&L (closed lots) | {sum(real.values()):+,.2f} |",
         "", "## Positions", ""]
    if not snap["positions"]:
        L.append("No open positions.")
    else:
        L += ["| ETF | What it is | Shares | Avg cost | Price | Value | Weight | P&L $ | P&L % | Today |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for p in sorted(snap["positions"], key=lambda p: -_f(p["market_value"])):
            asset = by_sym.get(p["symbol"], p["symbol"])
            L.append(f"| **{p['symbol']}** | {ASSET_NAMES.get(asset, asset)} | {_f(p['qty']):,.3f} | "
                     f"${_f(p['avg_entry_price']):,.2f} | ${_f(p['current_price']):,.2f} | ${_f(p['market_value']):,.2f} | "
                     f"{_f(p['market_value']) / equity * 100 if equity else 0:.1f}% | {_f(p['unrealized_pl']):+,.2f} | "
                     f"{_f(p['unrealized_plpc']) * 100:+.2f}% | {_f(p['change_today']) * 100:+.2f}% |")
    L += ["", "## Ledger", "",
          "Every filled order in the account, oldest first (from Alpaca's order history).", ""]
    if not snap["orders"]:
        L.append("No filled orders yet.")
    else:
        L += ["| # | Filled (UTC) | Side | ETF | Shares | Price | Value | Order id |", "|---|---|---|---|---|---|---|---|"]
        for i, o in enumerate(sorted(snap["orders"], key=lambda o: o.get("filled_at") or ""), 1):
            q, px = _f(o["filled_qty"]), _f(o["filled_avg_price"])
            side = "🟢 BUY" if o["side"] == "buy" else "🔴 SELL"
            L.append(f"| {i} | {(o.get('filled_at') or '')[:16].replace('T', ' ')} | {side} | **{o['symbol']}** | "
                     f"{q:,.4f} | ${px:,.2f} | ${q * px:,.2f} | `{(o.get('id') or '')[:8]}` |")
    L += ["", "## Equity curve", ""]
    if rows:
        L += ["| Date | Equity | Day change | From start | Drawdown from peak |", "|---|---|---|---|---|"]
        peak = 0.0
        prev = None
        for d, e in rows:
            peak = max(peak, e)
            ch = f"{(e / prev - 1) * 100:+.2f}%" if prev else "—"
            L.append(f"| {d} | ${e:,.2f} | {ch} | {(e / start_capital - 1) * 100:+.2f}% | {(e / peak - 1) * 100:.2f}% |")
            prev = e
    L += ["", "## Scorecard", "",
          "| Metric | Target | Actual |", "|---|---|---|",
          f"| Total return | — | {st.get('total', 0) * 100:+.2f}% |",
          f"| Max drawdown | better than −25% (halt level) | {st.get('mdd', 0) * 100:.2f}% |",
          f"| Sharpe (annualised) | > 0.5 | {('%.2f' % st['sharpe']) if st.get('sharpe') is not None else 'needs 20+ days'} |",
          f"| Best / worst day | — | {('%+.2f%%' % (st['best'] * 100)) if st.get('best') is not None else '—'} / "
          f"{('%+.2f%%' % (st['worst'] * 100)) if st.get('worst') is not None else '—'} |",
          f"| Trading days tracked | — | {st.get('days', 0)} |",
          f"| Filled orders | — | {len(snap['orders'])} |",
          "", "Updated automatically after every bot run. See also [[00 - Bot Dashboard]], [[07 - Trade Log]], [[06 - One-Month Trial]].", ""]
    _write(ROOT / "10 - Live Paper Account.md", "\n".join(L))
