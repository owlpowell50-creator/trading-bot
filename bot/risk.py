"""
risk.py - every check that stands between a signal and an order.

Each rule cites the vault note it comes from:
  * vol cap from worst tolerable month ........ 08 - Risk Limits and Escalation
  * no leverage, size below the optimum ....... 07 - Kelly Criterion and Estimation Error
  * single-asset concentration limit .......... 02 - Concentration and Correlation
  * drawdown halt (human review, not a panic sale) .. 05 - Drawdowns and Recovery
  * skip trades whose cost exceeds their benefit .... 11 - Is the Potential Edge Bigger Than the Costs?
  * stale / broken data blocks trading ......... 11 - Data Sources and Integrity
  * scenario losses on today's book ............ 13 - How Much Could I Lose?
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .backtest import apply_band
from .data import Series

SCENARIOS = [
    ("Financial crisis replay (Oct 2007 - Mar 2009)", "2007-10-09", "2009-03-09"),
    ("COVID crash replay (Feb - Mar 2020)", "2020-02-19", "2020-03-23"),
    ("Inflation bear replay (Jan - Oct 2022)", "2022-01-03", "2022-10-12"),
    ("Dot-com bust replay (Mar 2000 - Oct 2002)", "2000-03-24", "2002-10-09"),
]


def clamp_weights(target: Dict[str, float], max_single: float) -> Tuple[Dict[str, float], List[str]]:
    notes = []
    w = {a: max(0.0, x) for a, x in target.items()}
    tot = sum(w.values())
    if tot > 1.0 + 1e-9:
        notes.append(f"target summed to {tot:.2f} - scaled to 100% (no leverage)")
        w = {a: x / tot for a, x in w.items()}
    for a in list(w):
        if a != "CASH" and w[a] > max_single + 1e-9:
            notes.append(f"{a} capped at {max_single:.0%} (was {w[a]:.0%})")
            w[a] = max_single
    w["CASH"] = max(0.0, 1.0 - sum(x for a, x in w.items() if a != "CASH"))
    return w, notes


def plan_orders(current_values: Dict[str, float], target_w: Dict[str, float], equity: float,
                band: float, min_trade: float) -> Tuple[Dict[str, float], List[dict], List[str]]:
    """Turn target weights into orders (value deltas). Returns final weights,
    orders [{asset, side, value}], and notes."""
    notes = []
    cur_w = {a: v / equity for a, v in current_values.items() if equity > 0}
    final = apply_band(cur_w, target_w, band) if cur_w and band > 0 else dict(target_w)
    orders = []
    for a in sorted(set(final) | set(cur_w)):
        delta = (final.get(a, 0.0) - cur_w.get(a, 0.0)) * equity
        if abs(delta) < min_trade:
            if abs(delta) > 1e-6:
                notes.append(f"{a}: {delta:+,.0f} skipped (below minimum trade size)")
            continue
        orders.append({"asset": a, "side": "BUY" if delta > 0 else "SELL", "value": abs(delta)})
    # sells first so buys are funded
    orders.sort(key=lambda o: 0 if o["side"] == "SELL" else 1)
    return final, orders, notes


def pre_trade_checks(orders: List[dict], current_values: Dict[str, float], equity: float,
                     allowed: List[str]) -> List[str]:
    """Hard blocks. Any message returned means: do not send these orders."""
    blocks = []
    sells = sum(o["value"] for o in orders if o["side"] == "SELL")
    buys = sum(o["value"] for o in orders if o["side"] == "BUY")
    cash_after = current_values.get("CASH", 0.0) + sells - buys
    for o in orders:
        if o["asset"] not in allowed:
            blocks.append(f"{o['asset']} is not on the allowed list")
        if o["value"] > equity * 1.01:
            blocks.append(f"{o['asset']} order {o['value']:,.0f} is bigger than the account")
        if o["side"] == "SELL" and o["value"] > current_values.get(o["asset"], 0.0) * 1.001 + 1:
            blocks.append(f"{o['asset']}: selling more than held (no short selling)")
    if cash_after < -0.01 * equity:
        blocks.append(f"orders would overdraw cash by {-cash_after:,.0f} (no margin)")
    return blocks


def drawdown_status(equity_history: List[Tuple[str, float]], halt_at: float,
                    today: str = None, current: float = None) -> Tuple[float, float, bool]:
    """Peak = highest recorded equity up to `today`; drawdown measured on `current`
    (defaults to the latest record)."""
    if not equity_history:
        return 0.0, 0.0, False
    hist = [h for h in equity_history if today is None or h[0] <= today]
    peak = max(v for _, v in hist) if hist else current or 0.0
    cur = current if current is not None else equity_history[-1][1]
    peak = max(peak, cur)
    dd = cur / peak - 1 if peak > 0 else 0.0
    return peak, dd, dd <= -abs(halt_at)


def scenario_losses(s: Series, weights: Dict[str, float], equity: float) -> List[dict]:
    """Apply each asset's actual return in past crashes to today's holdings.
    Assets that did not exist yet are assumed to fall like US stocks (pessimistic)."""
    out = []
    for name, a, b in SCENARIOS:
        if a not in s.idx or b not in s.idx:
            continue
        ia, ib = s.idx[a], s.idx[b]
        total = 0.0
        for asset, w in weights.items():
            lv = s.levels.get(asset)
            if lv and lv[ia] is not None and lv[ib] is not None:
                r = lv[ib] / lv[ia] - 1
            else:
                us = s.levels["US"]
                r = us[ib] / us[ia] - 1
            total += w * r
        out.append({"scenario": name + " - if held unchanged", "return": total, "loss_value": total * equity})
    worst_day = sum(w * (-0.10 if a in ("US", "INTL", "REIT", "COMMOD") else
                          -0.03 if a in ("LONGBONDS", "GOLD") else -0.01 if a == "BONDS" else 0.0)
                    for a, w in weights.items())
    out.append({"scenario": "Overnight gap: stocks -10%, gold/long bonds -3%, bonds -1%",
                "return": worst_day, "loss_value": worst_day * equity})
    return out
