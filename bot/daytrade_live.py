"""
daytrade_live.py - the Opening Range Breakout day-trader, placing REAL orders in a
SEPARATE Alpaca PAPER account (never the long-term portfolio, never real money).

Rules - identical to the simulator in daytrade.py and 'Day Traders/12':
  opening range   09:30-09:45 New York, SPY and QQQ
  entry           first completed 5-minute bar closing above the high (long) / below the low (short)
                  -> market order with an attached bracket: stop at the other side of the range,
                  take-profit at 1.5 x range height; no new entries after 15:00
  size            risk 0.5% of the day-trading account per trade, position <= 20% of it
  limits          one trade per symbol per day; no new trades after a -$500 day
  flat            every open order cancelled and every position closed at 15:55

Keys: APCA_DT_KEY_ID / APCA_DT_SECRET_KEY (a second Alpaca paper account). The code only ever
talks to paper-api.alpaca.markets and refuses to run if it sees long-term ETFs in the account.
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from .daytrade import MAX_POS, RISK, SYMBOLS, TARGET_X
from .data import ROOT
from .vault import FM, _write

NY = ZoneInfo("America/New_York")
PAPER = "https://paper-api.alpaca.markets"
DATA = "https://data.alpaca.markets"
STATE = ROOT / "state" / "daytrade_live.json"
DAY_LOSS = 500.0
LONG_TERM = {"VOO", "IEFA", "IEF", "TLT", "VNQ", "GLDM", "PDBC", "SGOV"}


class Alpaca:
    def __init__(self, key=None, secret=None, http=None):
        self.key = key or os.environ.get("APCA_DT_KEY_ID")
        self.secret = secret or os.environ.get("APCA_DT_SECRET_KEY")
        self._fake = http
        if not (self.key and self.secret) and http is None:
            raise MissingKeys()

    def call(self, method, path, body=None, data=False):
        if self._fake:
            return self._fake(method, path, body)
        req = urllib.request.Request((DATA if data else PAPER) + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret,
                                              "Content-Type": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    t = r.read().decode()
                    return json.loads(t) if t else {}
            except urllib.error.HTTPError as e:
                msg = e.read().decode()[:300]
                if e.code in (429, 500, 502, 503) and attempt < 2:
                    time.sleep(3 * (attempt + 1)); continue
                raise RuntimeError(f"Alpaca {method} {path}: HTTP {e.code} {msg}") from e
            except urllib.error.URLError:
                if attempt < 2:
                    time.sleep(3 * (attempt + 1)); continue
                raise


class MissingKeys(Exception):
    pass


def et_now():
    return datetime.now(timezone.utc).astimezone(NY)


def at(day: date, hm: str):
    h, m = map(int, hm.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=NY)


def bars_today(api: Alpaca, day: date):
    start = at(day, "09:30").astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = urllib.parse.urlencode({"symbols": ",".join(SYMBOLS), "timeframe": "5Min", "feed": "iex",
                                "start": start, "limit": 10000, "adjustment": "raw"})
    r = api.call("GET", "/v2/stocks/bars?" + q, data=True)
    out = {}
    now = datetime.now(timezone.utc)
    for s, bs in (r.get("bars") or {}).items():
        done = []
        for b in bs:
            t = datetime.fromisoformat(b["t"].replace("Z", "+00:00"))
            if t + timedelta(minutes=5) <= now:            # completed bars only
                done.append(dict(b, hm=t.astimezone(NY).strftime("%H:%M")))
        out[s] = done
    return out


def todays_orb_orders(api: Alpaca, day: date):
    after = at(day, "04:00").astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    orders = api.call("GET", f"/v2/orders?status=all&after={after}&limit=500&nested=true")
    tag = f"orb-{day:%Y%m%d}-"
    return [o for o in orders if (o.get("client_order_id") or "").startswith(tag)]


def plan(bars, equity):
    """Return the trade the rules want right now for one symbol's completed bars, or None."""
    rng = [b for b in bars if b["hm"] < "09:45"]
    if len(rng) < 3 or bars[0]["hm"] != "09:30":
        return None
    hi, lo = max(b["h"] for b in rng), min(b["l"] for b in rng)
    height = hi - lo
    after = [b for b in bars if b["hm"] >= "09:45"]
    if not after or height <= 0:
        return None
    for b in after:                                      # first breakout of the day only
        if b["c"] > hi or b["c"] < lo:
            first = b
            break
    else:
        return None
    if first is not after[-1]:                          # the breakout happened earlier and was missed
        return {"skip": f"breakout at {first['hm']} already passed"}
    side = "buy" if first["c"] > hi else "sell"
    ref = first["c"]
    stop = lo if side == "buy" else hi
    target = ref + TARGET_X * height if side == "buy" else ref - TARGET_X * height
    per = abs(ref - stop)
    qty = min(math.floor(equity * RISK / per), math.floor(equity * MAX_POS / ref)) if per > 0 else 0
    if qty < 1:
        return {"skip": "size rounds to zero"}
    return {"side": side, "qty": qty, "ref": ref, "stop": round(stop, 2), "target": round(target, 2),
            "risk": round(per * qty, 2), "hi": hi, "lo": lo, "bar": first["hm"]}


def flatten(api: Alpaca, log):
    try:
        api.call("DELETE", "/v2/orders")
    except Exception as e:  # noqa: BLE001
        log(f"cancel orders: {e}")
    try:
        api.call("DELETE", "/v2/positions?cancel_orders=true")
    except Exception as e:  # noqa: BLE001
        log(f"close positions: {e}")
    log("flat: all orders cancelled, all positions closed")


def run(until: str, flatten_at: str | None = None, gate: bool = False, poll: int = 20, log=print, api=None):
    try:
        api = api or Alpaca()
    except MissingKeys:
        log("Day trading is not connected yet: add APCA_DT_KEY_ID and APCA_DT_SECRET_KEY "
            "(keys of a SECOND Alpaca paper account) as GitHub secrets.")
        return False
    now = et_now(); day = now.date()
    if gate and now.hour != 9:
        log(f"{now:%H:%M} New York - not this trigger's hour (daylight-saving twin), exiting")
        return False
    clock = api.call("GET", "/v2/clock")
    nxt = datetime.fromisoformat(clock["next_open"].replace("Z", "+00:00")).astimezone(NY)
    if not clock.get("is_open") and nxt.date() != day:
        log("market closed today"); return False
    acct = api.call("GET", "/v2/account")
    pos = api.call("GET", "/v2/positions")
    bad = [p["symbol"] for p in pos if p["symbol"] in LONG_TERM]
    if bad:
        raise RuntimeError(f"These keys belong to the long-term portfolio account (holds {bad}). "
                           "Day trading needs a separate paper account - refusing to trade.")
    equity = float(acct["equity"]); start_eq = float(acct.get("last_equity") or equity)
    log(f"day-trading account equity ${equity:,.2f}; running until {until} New York")
    end = at(day, until); flat_t = at(day, flatten_at) if flatten_at else None
    while et_now() < at(day, "09:45") + timedelta(seconds=30):
        time.sleep(15)
    done = {o["symbol"] for o in todays_orb_orders(api, day)}
    skipped = set()
    while True:
        now = et_now()
        if flat_t and now >= flat_t:
            flatten(api, log); break
        if now >= end:
            break
        if now < at(day, "15:00"):
            eq = float(api.call("GET", "/v2/account")["equity"])
            if eq - start_eq <= -DAY_LOSS:
                if "loss" not in skipped:
                    log(f"daily loss limit hit ({eq - start_eq:+,.2f}) - no more trades today"); skipped.add("loss")
            else:
                try:
                    bars = bars_today(api, day)
                except Exception as e:  # noqa: BLE001
                    log(f"bars: {e}"); bars = {}
                for s in SYMBOLS:
                    if s in done or s in skipped or not bars.get(s):
                        continue
                    p = plan(bars[s], eq)
                    if not p:
                        continue
                    if "skip" in p:
                        log(f"{s}: {p['skip']}"); skipped.add(s); continue
                    cid = f"orb-{day:%Y%m%d}-{s}-{'L' if p['side'] == 'buy' else 'S'}-r{p['risk']:.0f}"
                    body = {"symbol": s, "qty": str(p["qty"]), "side": p["side"], "type": "market", "time_in_force": "day",
                            "order_class": "bracket", "client_order_id": cid,
                            "take_profit": {"limit_price": f"{p['target']:.2f}"}, "stop_loss": {"stop_price": f"{p['stop']:.2f}"}}
                    try:
                        o = api.call("POST", "/v2/orders", body)
                        log(f"{s}: {'LONG' if p['side'] == 'buy' else 'SHORT'} {p['qty']} after the {p['bar']} bar closed "
                            f"{p['ref']:.2f} (range {p['lo']:.2f}-{p['hi']:.2f}); stop {p['stop']}, target {p['target']}, "
                            f"risk ${p['risk']:.0f} - order {o.get('id', '')[:8]}")
                        done.add(s)
                    except Exception as e:  # noqa: BLE001
                        log(f"{s}: order rejected - {e}"); skipped.add(s)
        time.sleep(poll)
    return True


def report(today: str | None = None, log=print):
    """Rebuild today's trades from Alpaca fills, append to the state file and write the note."""
    try:
        api = Alpaca()
    except MissingKeys:
        return
    day = date.fromisoformat(today) if today else et_now().date()
    st = json.loads(STATE.read_text()) if STATE.exists() else {"trades": [], "days": []}
    fills = api.call("GET", f"/v2/account/activities/FILL?date={day.isoformat()}&direction=asc") or []
    orders = {o["id"]: o for o in todays_orb_orders(api, day)}
    by_sym = {}
    for f in fills:
        if f.get("symbol") in SYMBOLS:
            by_sym.setdefault(f["symbol"], []).append(f)
    st["trades"] = [t for t in st["trades"] if t["date"] != day.isoformat()]
    for s, fs in by_sym.items():
        entry = fs[0]; side = entry["side"]; q = sum(float(f["qty"]) for f in fs if f["side"] == side)
        ein = sum(float(f["qty"]) * float(f["price"]) for f in fs if f["side"] == side) / q
        out = [f for f in fs if f["side"] != side]
        xq = sum(float(f["qty"]) for f in out)
        xp = sum(float(f["qty"]) * float(f["price"]) for f in out) / xq if xq else None
        pnl = ((xp - ein) if side == "buy" else (ein - xp)) * xq if xp else 0.0
        cid = next((o.get("client_order_id") for o in orders.values() if o["symbol"] == s), "") or ""
        risk = float(cid.split("-r")[-1]) if "-r" in cid else None
        st["trades"].append({"date": day.isoformat(), "symbol": s, "side": "LONG" if side == "buy" else "SHORT", "qty": q,
                             "entry": round(ein, 4), "entry_time": entry["transaction_time"][11:16], "exit": round(xp, 4) if xp else None,
                             "exit_time": out[-1]["transaction_time"][11:16] if out else None, "pnl": round(pnl, 2),
                             "r": round(pnl / risk, 2) if risk else None, "risk": risk})
    acct = api.call("GET", "/v2/account")
    st["days"] = [d for d in st["days"] if d["date"] != day.isoformat()] + [{"date": day.isoformat(), "equity": float(acct["equity"])}]
    st["start"] = st.get("start") or day.isoformat()
    st["start_equity"] = st.get("start_equity") or float(acct.get("last_equity") or acct["equity"])
    STATE.write_text(json.dumps(st, indent=1))
    write_note(st, day.isoformat())
    log(f"report written: {len([t for t in st['trades'] if t['date'] == day.isoformat()])} trades today")


def write_note(st, today):
    tr = st["trades"]; eq = st["days"][-1]["equity"] if st["days"] else None; s0 = st.get("start_equity") or 25000
    wins = [t for t in tr if t["pnl"] > 0]; rs = [t["r"] for t in tr if t.get("r") is not None]
    L = [FM.format(type="live-day-trading", updated=today, extra_tags="\n  - day-trading\n  - alpaca"),
         "# 12 - Live Day Trading", "",
         "> [!success] Real orders in a separate Alpaca paper account",
         "> The Opening Range Breakout rules from [[11 - Day Trading Simulator]] placed as real bracket orders on SPY and QQQ "
         "(practice money, real fills). Flat every day by 15:55 New York.", "",
         "## Account", "", "| | |", "|---|---|",
         f"| Started | {st.get('start')} with ${s0:,.2f} |",
         f"| **Equity** | **${eq:,.2f}** ({(eq / s0 - 1) * 100:+.2f}%) |" if eq else "| Equity | — |",
         f"| Trades | {len(tr)} ({len(wins)} winners) |",
         f"| Average R | {sum(rs) / len(rs):+.2f} |" if rs else "| Average R | — |", "",
         "## Ledger", ""]
    if not tr:
        L.append("No trades yet.")
    else:
        L += ["| Date | Sym | Dir | Qty | Entry (UTC) | Exit (UTC) | P&L $ | R |", "|---|---|---|---|---|---|---|---|"]
        for t in reversed(tr):
            ex = f"{t['exit']:.2f} ({t['exit_time']})" if t.get("exit") else "open"
            rr = f"{t['r']:+.2f}" if t.get("r") is not None else "—"
            L.append(f"| {t['date']} | {t['symbol']} | {t['side']} | {t['qty']:.0f} | {t['entry']:.2f} ({t['entry_time']}) | {ex} | {t['pnl']:+,.2f} | {rr} |")
    L += ["", "Compare with the rule-based replay: [[11 - Day Trading Simulator#Scorecard]] · back to [[00 - Bot Dashboard]]", ""]
    _write(ROOT / "12 - Live Day Trading.md", "\n".join(L))
