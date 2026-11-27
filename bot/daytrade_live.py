"""
daytrade_live.py - the Opening Range Breakout day-trader, placing REAL orders in a
SEPARATE Alpaca PAPER account (never the long-term portfolio, never real money).

Rules - identical to the simulator in daytrade.py and 'Day Traders/12':
  opening range   09:30-09:45 New York, SPY and QQQ
  entry           first completed 5-minute bar closing above the high (long) / below the low (short)
                  -> market order with an attached bracket: stop at the other side of the range,
                  take-profit at 1.5 x range height; no new entries after 15:00
  size            risk $500 per trade, position <= 2x the account
  limits          one trade per symbol per day; $5,000 of risk a day: losses so far + what the open
                  trades could still lose at their stops never exceeds $5,000, new trades are sized to fit
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

from .daytrade import SYMBOLS

# Live target since 2026-11-27: 3x the opening range (was 1.5x). On the pair+trend rule over 2016-2026 it lifted the
# average trade from -0.024R to +0.002R (2016-20) and +0.110R to +0.152R (2021-now) - see '17 - Day Trader Research'.
TARGET_X = 3.0
from .data import ROOT
from .vault import FM, _write

NY = ZoneInfo("America/New_York")
PAPER = "https://paper-api.alpaca.markets"
DATA = "https://data.alpaca.markets"
STATE = ROOT / "state" / "daytrade_live.json"
DAY_RISK_USD = 5000.0        # the most the day trader may lose in one day (both strategies together)
TRADE_RISK_USD = 500.0       # risk per trade: what one trade loses if its stop is hit
CORRELATED_RISK_FACTOR = 0.5  # second same-direction SPY/QQQ trade on the same day gets half the risk
MAX_POS_X = 2.0              # one position at most 2x the account (paper margin; intraday buying power is 4x)
MIN_TRADE_RISK = 50.0        # don't open a trade that can only risk less than this
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



TREND_DAYS = 20


def daily_sma(api: Alpaca, day: date, n: int = TREND_DAYS):
    """Average of the last n daily closes BEFORE `day`, per symbol (the trend filter's line)."""
    q = urllib.parse.urlencode({"symbols": ",".join(SYMBOLS), "timeframe": "1Day", "feed": "sip", "adjustment": "all",
                                "start": (day - timedelta(days=n * 2 + 15)).isoformat(), "end": (day - timedelta(days=1)).isoformat(),
                                "limit": 1000})
    r = api.call("GET", "/v2/stocks/bars?" + q, data=True)
    out = {}
    for s, bs in (r.get("bars") or {}).items():
        closes = [b["c"] for b in bs if b["t"][:10] < day.isoformat()]
        if len(closes) >= n:
            out[s] = sum(closes[-n:]) / n
    return out


def first_break(bars):
    """(bar, side) of the first 5-minute close outside the 09:30-09:45 range, plus the range; None if none yet."""
    rng = [b for b in bars if b["hm"] < "09:45"]
    if len(rng) < 3 or bars[0]["hm"] != "09:30":
        return None
    hi, lo = max(b["h"] for b in rng), min(b["l"] for b in rng)
    for b in bars:
        if b["hm"] >= "09:45" and (b["c"] > hi or b["c"] < lo):
            return {"bar": b["hm"], "side": "buy" if b["c"] > hi else "sell", "hi": hi, "lo": lo}
    return None


def plan_pair(bars_by_sym, s, equity, max_risk=None, sma=None):
    """Live entry rule since 2026-11-27 (see '17 - Day Trader Research'): trade a symbol only once BOTH SPY and
    QQQ have closed outside their opening ranges in the SAME direction, and only in the direction of its
    20-day trend. Entry at the bar that completes the confirmation; stop at the far side of the range;
    target 3x the range from the entry. Returns a plan, {'skip': why} (stop for the day) or None (wait)."""
    other = next(x for x in SYMBOLS if x != s)
    mine, theirs = bars_by_sym.get(s) or [], bars_by_sym.get(other) or []
    a, b = first_break(mine) if mine else None, first_break(theirs) if theirs else None
    if not a:
        return None
    if not b:
        return {"wait": f"broke {'up' if a['side'] == 'buy' else 'down'} at {a['bar']} - waiting for {other} to confirm"}
    if a["side"] != b["side"]:
        return {"skip": f"{s} and {other} broke opposite ways ({a['bar']} / {b['bar']}) - no trade today"}
    conf = max(a["bar"], b["bar"])
    last = mine[-1]
    if last["hm"] > conf:
        return {"skip": f"confirmation at {conf} already passed"}
    if last["hm"] < conf:
        return None
    ref = last["c"]
    if sma is None or s not in sma:
        return {"skip": "no 20-day trend line available - not trading blind"}
    up = ref > sma[s]
    if (a["side"] == "buy") != up:
        return {"skip": f"breakout {'up' if a['side'] == 'buy' else 'down'} is against the 20-day trend "
                        f"(price {ref:.2f} vs average {sma[s]:.2f})"}
    side, hi, lo = a["side"], a["hi"], a["lo"]
    height = hi - lo
    stop = lo if side == "buy" else hi
    per = (ref - stop) if side == "buy" else (stop - ref)
    if per <= 0:
        return {"skip": "price already back inside the range"}
    target = ref + TARGET_X * height if side == "buy" else ref - TARGET_X * height
    budget = TRADE_RISK_USD if max_risk is None else min(TRADE_RISK_USD, max_risk)
    qty = min(math.floor(budget / per), math.floor(equity * MAX_POS_X / ref))
    if qty < 1:
        return {"skip": "size rounds to zero"}
    return {"side": side, "qty": qty, "ref": ref, "stop": round(stop, 2), "target": round(target, 2),
            "risk": round(per * qty, 2), "hi": hi, "lo": lo, "bar": last["hm"], "confirmed": conf}

def todays_orb_orders(api: Alpaca, day: date, both: bool = False):
    after = at(day, "04:00").astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    orders = api.call("GET", f"/v2/orders?status=all&after={after}&limit=500&nested=true")
    tags = (f"orb-{day:%Y%m%d}-", f"dts-{day:%Y%m%d}-") if both else (f"orb-{day:%Y%m%d}-",)
    return [o for o in orders if (o.get("client_order_id") or "").startswith(tags)]


def plan(bars, equity, max_risk=None):
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
    budget = TRADE_RISK_USD if max_risk is None else min(TRADE_RISK_USD, max_risk)
    qty = min(math.floor(budget / per), math.floor(equity * MAX_POS_X / ref)) if per > 0 else 0
    if qty < 1:
        return {"skip": "size rounds to zero"}
    return {"side": side, "qty": qty, "ref": ref, "stop": round(stop, 2), "target": round(target, 2),
            "risk": round(per * qty, 2), "hi": hi, "lo": lo, "bar": first["hm"]}


def risk_left(api: Alpaca, start_eq: float, equity: float) -> float:
    """$ of today's $5,000 still unused: DAY_RISK_USD - today's loss so far (open trades marked to market)
    - what the open positions would still lose if every stop were hit."""
    used = max(0.0, start_eq - equity)
    pos = api.call("GET", "/v2/positions")
    if pos:
        stops = {}
        since = (et_now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for o in api.call("GET", f"/v2/orders?status=all&nested=true&limit=500&after={since}"):
            for leg in [o] + (o.get("legs") or []):
                if (leg.get("type") in ("stop", "stop_limit") and leg.get("stop_price")
                        and leg.get("status") in ("new", "held", "accepted", "pending_new", "partially_filled")):
                    stops[leg["symbol"]] = float(leg["stop_price"])
        for p in pos:
            q, px = float(p["qty"]), float(p["current_price"])
            st = stops.get(p["symbol"])
            used += abs(q) * px if st is None else max(0.0, (px - st) * q)   # q < 0 for shorts
    return DAY_RISK_USD - used


NOT_FLAT = False


def flatten(api: Alpaca, log, tries: int = 8, wait: float = 4.0):
    """Close everything and CHECK it worked. Alpaca's bulk close can silently skip a position while its
    bracket legs are still being cancelled (that is how SPY was carried overnight on 2026-11-24), so we
    cancel, wait for the orders to clear, close, then re-check positions and retry symbol by symbol."""
    def safe(m, p):
        try:
            return api.call(m, p)
        except Exception as e:  # noqa: BLE001
            log(f"{m} {p}: {e}")
            return None
    safe("DELETE", "/v2/orders")
    for _ in range(tries):
        if not (safe("GET", "/v2/orders?status=open") or []):
            break
        time.sleep(wait)
    safe("DELETE", "/v2/positions?cancel_orders=true")
    left = []
    for k in range(tries):
        time.sleep(wait if k else wait / 2)
        left = safe("GET", "/v2/positions")
        if left is None:
            continue
        if not left:
            log("flat: all orders cancelled, all positions closed (checked)")
            return True
        log("still open after close: " + ", ".join(f"{p['symbol']} {p['qty']}" for p in left) + f" - retry {k + 1}")
        safe("DELETE", "/v2/orders")
        for p in left:
            safe("DELETE", f"/v2/positions/{p['symbol']}")
    log("WARNING: NOT FLAT - could not close " + ", ".join(f"{p['symbol']} {p['qty']}" for p in (left or [])) +
        ". Close them by hand in the Alpaca paper account.")
    return False


def run(until: str, flatten_at: str | None = None, gate: bool = False, poll: int = 20, log=print, api=None,
        skills: bool = True):
    try:
        api = api or Alpaca()
    except MissingKeys:
        log("Day trading is not connected yet: add APCA_DT_KEY_ID and APCA_DT_SECRET_KEY "
            "(keys of a SECOND Alpaca paper account) as GitHub secrets.")
        return False
    now = et_now(); day = now.date()
    gate_hours = (9,) if gate is True else (tuple(gate) if isinstance(gate, (tuple, list)) else (gate,))
    if gate and now.hour not in gate_hours:
        log(f"{now:%H:%M} New York - not this trigger's hour (daylight-saving twin), exiting")
        return False
    clock = api.call("GET", "/v2/clock")
    nxt = datetime.fromisoformat(clock["next_open"].replace("Z", "+00:00")).astimezone(NY)
    if not clock.get("is_open") and nxt.date() != day:
        log("market closed today"); return False
    close_t = datetime.fromisoformat(clock["next_close"].replace("Z", "+00:00")).astimezone(NY) if clock.get("next_close") else None
    early = bool(close_t and close_t.date() == day and (close_t.hour, close_t.minute) < (16, 0) and not flatten_at)
    acct = api.call("GET", "/v2/account")
    pos = api.call("GET", "/v2/positions")
    bad = [p["symbol"] for p in pos if p["symbol"] in LONG_TERM]
    if bad:
        raise RuntimeError(f"These keys belong to the long-term portfolio account (holds {bad}). "
                           "Day trading needs a separate paper account - refusing to trade.")
    equity = float(acct["equity"]); start_eq = float(acct.get("last_equity") or equity)
    log(f"day-trading account equity ${equity:,.2f}; running until {until} New York")
    if pos and not flatten_at and not todays_orb_orders(api, day, both=True):
        # a day trader must start flat: anything still open was left over from an earlier session
        log("left-over positions from an earlier session: " + ", ".join(f"{p['symbol']} {p['qty']}" for p in pos) + " - closing them first")
        while not api.call("GET", "/v2/clock").get("is_open"):
            time.sleep(20)
        flatten(api, log)
        time.sleep(5)
        acct = api.call("GET", "/v2/account"); equity = float(acct["equity"])
    if early:
        log(f"early close today ({close_t:%H:%M} New York) - the close job would run too late, so no day trading")
        return False
    end = at(day, until); flat_t = at(day, flatten_at) if flatten_at else None
    while et_now() < at(day, "09:45") + timedelta(seconds=30) and not flatten_at:
        time.sleep(15)
    done = {o["symbol"] for o in todays_orb_orders(api, day)}
    sides = {o["symbol"]: ("buy" if "-L-" in (o.get("client_order_id") or "") else "sell") for o in todays_orb_orders(api, day)}
    skipped = set()
    waits = {}
    sma = None
    if not flatten_at:
        try:
            sma = daily_sma(api, day)
            log("20-day trend lines: " + ", ".join(f"{k} {v:.2f}" for k, v in sma.items()))
        except Exception as e:  # noqa: BLE001
            log(f"trend lines unavailable ({e}) - the opening-range strategy will not trade today")
    skill = None
    if skills:
        from .skill_trader import SkillTrader
        try:
            skill = SkillTrader(api, day, log)
        except Exception as e:  # noqa: BLE001
            log(f"skill pack unavailable: {e}")
    while True:
        now = et_now()
        if flat_t and now >= flat_t:
            if not flatten(api, log):
                global NOT_FLAT
                NOT_FLAT = True
            break
        if now >= end:
            break
        if now < at(day, "15:00"):
            eq = float(api.call("GET", "/v2/account")["equity"])
            left = risk_left(api, start_eq, eq)
            if left < MIN_TRADE_RISK:
                if "loss" not in skipped:
                    log(f"daily $5,000 risk used (P&L {eq - start_eq:+,.2f}, ${max(left, 0):,.0f} left) - "
                        "no new trades until it frees up"); skipped.add("loss")
            else:
                skipped.discard("loss")
                try:
                    bars = bars_today(api, day)
                except Exception as e:  # noqa: BLE001
                    log(f"bars: {e}"); bars = {}
                for s in SYMBOLS:
                    if s in done or s in skipped or not bars.get(s):
                        continue
                    p = plan_pair(bars, s, eq, left, sma)
                    if not p:
                        continue
                    if "wait" in p:
                        if waits.get(s) != p["wait"]:
                            log(f"{s}: {p['wait']}"); waits[s] = p["wait"]
                        continue
                    if "skip" in p:
                        log(f"{s}: {p['skip']}"); skipped.add(s); continue
                    twin = [x for x, sd in sides.items() if x != s and sd == p["side"]]
                    if twin:                 # SPY and QQQ move together: a second same-direction trade gets half the risk
                        p2 = plan_pair(bars, s, eq, min(left, TRADE_RISK_USD * CORRELATED_RISK_FACTOR), sma)
                        if not p2 or "skip" in p2:
                            log(f"{s}: same direction as {twin[0]} - half-size trade rounds to nothing, skipped"); skipped.add(s); continue
                        log(f"{s}: same direction as {twin[0]} already open today - risk halved to ${p2['risk']:.0f}")
                        p = p2
                    cid = f"orb-{day:%Y%m%d}-{s}-{'L' if p['side'] == 'buy' else 'S'}-r{p['risk']:.0f}"
                    body = {"symbol": s, "qty": str(p["qty"]), "side": p["side"], "type": "market", "time_in_force": "day",
                            "order_class": "bracket", "client_order_id": cid,
                            "take_profit": {"limit_price": f"{p['target']:.2f}"}, "stop_loss": {"stop_price": f"{p['stop']:.2f}"}}
                    try:
                        o = api.call("POST", "/v2/orders", body)
                        log(f"{s}: {'LONG' if p['side'] == 'buy' else 'SHORT'} {p['qty']} - SPY and QQQ both broke the same way by {p['bar']}, with the 20-day trend; price "
                            f"{p['ref']:.2f} (range {p['lo']:.2f}-{p['hi']:.2f}); stop {p['stop']}, target {p['target']}, "
                            f"risk ${p['risk']:.0f} - order {o.get('id', '')[:8]}")
                        done.add(s); sides[s] = p["side"]; left -= p["risk"]
                    except Exception as e:  # noqa: BLE001
                        log(f"{s}: order rejected - {e}"); skipped.add(s)
                if skill:
                    try:
                        eq2 = float(api.call("GET", "/v2/account")["equity"])
                        skill.poll(eq2, et_now(), risk_left(api, start_eq, eq2))
                    except Exception as e:  # noqa: BLE001
                        log(f"skill poll: {e}")
        time.sleep(poll)
    return True


def check(log=print):
    api = Alpaca()
    a = api.call("GET", "/v2/account"); pos = api.call("GET", "/v2/positions")
    log(f"CHECK account ...{str(a.get('account_number', ''))[-4:]} status {a.get('status')} equity ${float(a['equity']):,.2f} "
        f"cash ${float(a['cash']):,.2f} buying power ${float(a['buying_power']):,.2f} shorting {a.get('shorting_enabled')} "
        f"positions {[p['symbol'] for p in pos] or 'none'} long-term ETFs present: {any(p['symbol'] in LONG_TERM for p in pos)}")
    eq = float(a["equity"])
    log(f"CHECK daily risk budget: ${risk_left(api, float(a.get('last_equity') or eq), eq):,.0f} of ${DAY_RISK_USD:,.0f} free")
    try:
        sma = daily_sma(api, et_now().date())
        log("CHECK 20-day trend lines: " + ", ".join(f"{k} {v:.2f}" for k, v in sma.items()))
        cal0 = api.call("GET", f"/v2/calendar?start={(et_now().date() - timedelta(days=7)).isoformat()}&end={(et_now().date() - timedelta(days=1)).isoformat()}")
        last = date.fromisoformat(cal0[-1]["date"])
        q = urllib.parse.urlencode({"symbols": ",".join(SYMBOLS), "timeframe": "5Min", "feed": "sip", "adjustment": "raw",
                                    "start": at(last, "09:30").astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "end": at(last, "15:00").astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": 10000})
        allb = {s: [dict(b, hm=datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(NY).strftime("%H:%M")) for b in bs]
                for s, bs in (api.call("GET", "/v2/stocks/bars?" + q, data=True).get("bars") or {}).items()}
        sma_last = daily_sma(api, last)
        seen = {}
        for k in range(3, max(len(v) for v in allb.values()) + 1):
            for s in SYMBOLS:
                if s in seen:
                    continue
                p = plan_pair({x: v[:k] for x, v in allb.items()}, s, eq, TRADE_RISK_USD, sma_last)
                if p and "wait" not in p:
                    seen[s] = p
        for s in SYMBOLS:
            p = seen.get(s)
            log(f"CHECK new entry rule on {last}: {s} " + ("no breakout" if not p else p.get("skip") or
                f"{'LONG' if p['side'] == 'buy' else 'SHORT'} {p['qty']} at {p['ref']:.2f} ({p['bar']}), stop {p['stop']}, target {p['target']}, risk ${p['risk']:.0f}"))
    except Exception as e:  # noqa: BLE001
        log(f"CHECK new entry rule: {e}")
    from .skill_trader import replay_day
    cal = api.call("GET", f"/v2/calendar?start={(et_now().date() - timedelta(days=7)).isoformat()}&end={(et_now().date() - timedelta(days=1)).isoformat()}")
    if cal:
        replay_day(api, date.fromisoformat(cal[-1]["date"]), float(a["equity"]), log)


def report(today: str | None = None, log=print):
    """Rebuild today's trades from Alpaca fills, append to the state file and write the note."""
    try:
        api = Alpaca()
    except MissingKeys:
        return
    day = date.fromisoformat(today) if today else et_now().date()
    st = json.loads(STATE.read_text()) if STATE.exists() else {"trades": [], "days": []}
    fills = api.call("GET", f"/v2/account/activities/FILL?date={day.isoformat()}&direction=asc") or []
    orders = {o["id"]: o for o in todays_orb_orders(api, day, both=True)}
    by_sym = {}
    for f in fills:
        by_sym.setdefault(f["symbol"], []).append(f)
    st["trades"] = [t for t in st["trades"] if t["date"] != day.isoformat()]
    try:
        close_old_trades(api, st, day, log)
    except Exception as e:  # noqa: BLE001
        log(f"could not settle trades carried from earlier days: {e}")
    for s, fs in by_sym.items():
        k = next((n for n, f in enumerate(fs) if f.get("order_id") in orders), None)
        if k is None:
            log(f"{s}: fills today are not from today's entries (a left-over position being closed) - not counted as a trade")
            continue
        fs = fs[k:]
        entry = fs[0]; side = entry["side"]; q = sum(float(f["qty"]) for f in fs if f["side"] == side)
        ein = sum(float(f["qty"]) * float(f["price"]) for f in fs if f["side"] == side) / q
        out = [f for f in fs if f["side"] != side]
        xq = sum(float(f["qty"]) for f in out)
        xp = sum(float(f["qty"]) * float(f["price"]) for f in out) / xq if xq else None
        pnl = ((xp - ein) if side == "buy" else (ein - xp)) * xq if xp else 0.0
        cid = next((o.get("client_order_id") for o in orders.values() if o["symbol"] == s), "") or ""
        risk = float(cid.split("-r")[-1]) if "-r" in cid else None
        strat = "Skill pack" if cid.startswith("dts-") else "ORB"
        parent = next((o for o in orders.values() if o["symbol"] == s), {}) or {}
        how, stop_px, tgt_px = None, None, None
        for leg in parent.get("legs") or []:
            if leg.get("type") == "limit":
                tgt_px = float(leg["limit_price"]) if leg.get("limit_price") else None
                how = how or ("hit target" if leg.get("status") == "filled" else None)
            elif leg.get("type") in ("stop", "stop_limit"):
                stop_px = float(leg["stop_price"]) if leg.get("stop_price") else None
                how = how or ("stopped out" if leg.get("status") == "filled" else None)
        if not how and out:
            ny = datetime.fromisoformat(out[-1]["transaction_time"].replace("Z", "+00:00")).astimezone(NY).strftime("%H:%M")
            how = "closed at the 15:55 flatten" if ny >= "15:54" else "closed before stop or target"
        st["trades"].append({"how": how, "stop": stop_px, "target": tgt_px, "date": day.isoformat(), "symbol": s, "side": "LONG" if side == "buy" else "SHORT", "qty": q,
                             "entry": round(ein, 4), "entry_time": entry["transaction_time"][11:16], "exit": round(xp, 4) if xp else None,
                             "exit_time": out[-1]["transaction_time"][11:16] if out else None, "pnl": round(pnl, 2),
                             "r": round(pnl / risk, 2) if risk else None, "risk": risk, "strategy": strat})
    acct = api.call("GET", "/v2/account")
    st["days"] = [d for d in st["days"] if d["date"] != day.isoformat()] + [{"date": day.isoformat(), "equity": float(acct["equity"])}]
    st["start"] = st.get("start") or day.isoformat()
    st["start_equity"] = st.get("start_equity") or float(acct.get("last_equity") or acct["equity"])
    STATE.write_text(json.dumps(st, indent=1))
    write_note(st, day.isoformat())
    try:
        write_day_review(st, day.isoformat())
    except Exception as e:  # noqa: BLE001
        log(f"day review skipped: {e}")
    try:
        from .benchmarks import write as write_benchmarks
        write_benchmarks(lambda m, p, b=None: api.call(m, p, b, data=True))
    except Exception as e:  # noqa: BLE001
        log(f"benchmarks skipped: {e}")
    log(f"report written: {len([t for t in st['trades'] if t['date'] == day.isoformat()])} trades today")


def write_note(st, today):
    tr = st["trades"]; eq = st["days"][-1]["equity"] if st["days"] else None; s0 = st.get("start_equity") or 25000
    wins = [t for t in tr if t["pnl"] > 0]; rs = [t["r"] for t in tr if t.get("r") is not None]
    L = [FM.format(type="live-day-trading", updated=today, extra_tags="\n  - day-trading\n  - alpaca"),
         "# 12 - Live Day Trading", "",
         "> [!success] Real orders in a separate Alpaca paper account",
         "> Two strategies, one account: the Opening Range Breakout rules from [[11 - Day Trading Simulator]] on SPY and QQQ, "
         "and the **day-trader-skill pack** ([[14 - Skill Pack Day Trader]]: scanner → exit plan → news → time machine → sizing) on 30 liquid stocks. "
         "Real bracket orders, practice money. Risk: **$500 per trade (a second same-direction SPY/QQQ trade gets half), $5,000 a day** across both (losses so far + what open trades could lose at their stops). Flat every day by 15:55 New York (checked, with an alert if anything is left open).", "",
         "**Entry rule (since 27 Nov 2026):** trade only when SPY **and** QQQ have both broken out of their 09:30-09:45 range the same way, and only in the direction of each one's 20-day trend. Target: 3x the opening range (stop: the far side of it). "
         "Over 2016-2026 this beat the original rule in both halves of the history - see [[17 - Day Trader Research]].", "",
         "## Account", "", "| | |", "|---|---|",
         f"| Started | {st.get('start')} with ${s0:,.2f} |",
         f"| **Equity** | **${eq:,.2f}** ({(eq / s0 - 1) * 100:+.2f}%) |" if eq else "| Equity | — |",
         f"| Trades | {len(tr)} ({len(wins)} winners) |",
         f"| Average R | {sum(rs) / len(rs):+.2f} |" if rs else "| Average R | — |", "",
         "## One-month trial", ""]
    if st.get("start"):
        s0d = date.fromisoformat(st["start"]); endd = s0d + timedelta(days=30); today_d = date.fromisoformat(today)
        L += ["| | |", "|---|---|", f"| Trial | {s0d} → {endd} (day {min(30, (today_d - s0d).days + 1)} of 30) |",
              f"| Result so far | {(eq / s0 - 1) * 100:+.2f}% |" if eq else "| Result so far | — |",
              "| Expectation | see [[13 - Day Trading Month Simulation]] — the same rules on the previous month of real data |", ""]
    L += ["## Ledger", ""]
    if not tr:
        L.append("No trades yet.")
    else:
        L += ["| Date | Strategy | Sym | Dir | Qty | Entry (UTC) | Exit (UTC) | P&L $ | R |", "|---|---|---|---|---|---|---|---|---|"]
        for t in reversed(tr):
            ex = f"{t['exit']:.2f} ({t['exit_time']})" if t.get("exit") else "open"
            rr = f"{t['r']:+.2f}" if t.get("r") is not None else "—"
            L.append(f"| {t['date']} | {t.get('strategy', 'ORB')} | {t['symbol']} | {t['side']} | {t['qty']:.0f} | {t['entry']:.2f} ({t['entry_time']}) | {ex} | {t['pnl']:+,.2f} | {rr} |")
    L += ["", "## By strategy", "", "| Strategy | Trades | Winners | P&L $ | Avg R |", "|---|---|---|---|---|"]
    for name in ("ORB", "Skill pack"):
        g = [t for t in tr if t.get("strategy", "ORB") == name]; gr = [t["r"] for t in g if t.get("r") is not None]
        L.append(f"| {name} | {len(g)} | {sum(1 for t in g if t['pnl'] > 0)} | {sum(t['pnl'] for t in g):+,.2f} | "
                 + (f"{sum(gr) / len(gr):+.2f} |" if gr else "— |"))
    sl = st.get("skill_log") or []
    L += ["", "## Skill pack decisions", "",
          "Every breakout the scanner found and what the pipeline decided. Source: "
          "[day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT), vendored in the repo.", ""]
    if not sl:
        L.append("No breakouts evaluated yet.")
    else:
        L += ["| Date | Sym | Breakout | Stop / target | Time machine | Decision |", "|---|---|---|---|---|---|"]
        for d in reversed(sl[-40:]):
            tmv = (f"target {d['p_target'] * 100:.0f}% / stop {d['p_stop'] * 100:.0f}%, avg R {d['avg_r']:+.2f}"
                   if d.get("p_target") is not None else "—")
            so = f"{d['stop']} / {d['target']}" if d.get("stop") else "—"
            dec = f"skipped: {d['skip']}" if d.get("skip") else f"**bought {d['qty']}** (risk ${d['risk']:.0f})"
            L.append(f"| {d['date']} | {d['symbol']} | {d['time']} @ {d['price']} | {so} | {tmv} | {dec.replace('|', '/')} |")
    dts = sorted({d["date"] for d in st["days"]}, reverse=True)
    if dts:
        L += ["", "## Daily reviews", "", " · ".join(f"[[Day Trade Review {d}|{d}]]" for d in dts[:30])]
    L += ["", "Compare with the rule-based replay: [[11 - Day Trading Simulator#Scorecard]] · back to [[00 - Bot Dashboard]]", ""]
    _write(ROOT / "12 - Live Day Trading.md", "\n".join(L))


def close_old_trades(api, st, day, log=print):
    """Trades from earlier days that were never closed the same day (carried overnight, then flattened later):
    find the closing fills in the account history and record the exit, so the ledger and the Brain stop
    reporting them as open."""
    for t in st["trades"]:
        if t.get("exit") or t["date"] >= day.isoformat():
            continue
        want = "sell" if t["side"] == "LONG" else "buy"
        fills = api.call("GET", f"/v2/account/activities/FILL?after={t['date']}T00:00:00Z&direction=asc&page_size=100") or []
        need, got, val, last = float(t["qty"]), 0.0, 0.0, None
        for f in fills:
            if f.get("symbol") != t["symbol"] or f.get("side") != want:
                continue
            if f["transaction_time"][:10] == t["date"] and f["transaction_time"][11:16] <= (t.get("entry_time") or "00:00"):
                continue
            q = min(float(f["qty"]), need - got)
            got += q; val += q * float(f["price"]); last = f
            if got >= need - 1e-9:
                break
        if not last or got < need - 1e-9:
            continue
        xp = val / got
        pnl = ((xp - t["entry"]) if t["side"] == "LONG" else (t["entry"] - xp)) * got
        t.update(exit=round(xp, 4), exit_time=last["transaction_time"][11:16], exit_date=last["transaction_time"][:10],
                 pnl=round(pnl, 2), r=round(pnl / t["risk"], 2) if t.get("risk") else None, carried=True)
        log(f"{t['symbol']} {t['date']}: carried overnight, closed {t['exit_date']} at {xp:.2f} -> P&L ${pnl:+,.2f}")


def _exit_kind(t):
    r = t.get("r")
    if not t.get("exit"):
        return "still open"
    if t.get("how"):
        return t["how"]
    if t.get("carried"):
        return f"held overnight, closed {t.get('exit_date', 'later')}"
    if r is None:
        return "closed"
    if r <= -0.85:
        return "stopped out"
    if r >= 1.8:
        return "hit target"
    return "closed before stop or target"


def write_day_review(st, today):
    """One note per trading day: what happened, how much of the risk budget was used, what to learn."""
    tr = [t for t in st["trades"] if t["date"] == today]
    sl = [d for d in (st.get("skill_log") or []) if d.get("date") == today]
    days = sorted(st["days"], key=lambda d: d["date"])
    k = next((i for i, d in enumerate(days) if d["date"] == today), None)
    eq = days[k]["equity"] if k is not None else None
    prev_eq = days[k - 1]["equity"] if k else (st.get("start_equity") or eq)
    pnl = sum(t["pnl"] for t in tr)
    day_chg = (eq - prev_eq) if (eq is not None and prev_eq is not None) else None
    worst = min([t["pnl"] for t in tr] or [0])
    risk_used = sum((t.get("risk") or 0) for t in tr)
    all_tr = [t for t in st["trades"] if t["date"] <= today and t.get("exit")]
    rs = [t["r"] for t in all_tr if t.get("r") is not None]
    peak = max([d["equity"] for d in days[: (k or 0) + 1]] or [eq or 0])
    L = [FM.format(type="day-trade-review", updated=today, extra_tags="\n  - day-trading\n  - review"),
         f"# Day Trade Review {today}", "",
         f"Back to [[12 - Live Day Trading]]" + (f" · previous: [[Day Trade Review {days[k - 1]['date']}]]" if k else ""), "",
         "## The day", "", "| | |", "|---|---|",
         f"| Trades | {len(tr)} |",
         f"| Result of today's trades | ${pnl:+,.2f} |",
         f"| Account change (includes anything left over) | ${day_chg:+,.2f} |" if day_chg is not None else "| Account change | — |",
         f"| Equity at close | ${eq:,.2f} |" if eq else "| Equity at close | — |",
         f"| Planned risk taken | ${risk_used:,.0f} of the ${DAY_RISK_USD:,.0f} daily limit |",
         f"| Worst trade | ${worst:+,.2f} vs ${TRADE_RISK_USD:,.0f} planned risk per trade |",
         f"| Below the account's peak | {(eq / peak - 1) * 100:+.2f}% |" if eq and peak else "| Below peak | — |", ""]
    if tr:
        L += ["## Trades", "", "| Strategy | Sym | Dir | Entry (UTC) | Exit (UTC) | How it ended | P&L $ | R |", "|---|---|---|---|---|---|---|---|"]
        for t in tr:
            ex = f"{t['exit']:.2f} ({t['exit_time']})" if t.get("exit") else "—"
            rr = f"{t['r']:+.2f}" if t.get("r") is not None else "—"
            L.append(f"| {t.get('strategy', 'ORB')} | {t['symbol']} | {t['side']} | {t['entry']:.2f} ({t['entry_time']}) | {ex} | {_exit_kind(t)} | {t['pnl']:+,.2f} | {rr} |")
        L.append("")
    if sl:
        took = [d for d in sl if not d.get("skip")]
        L += ["## Skill pack", "", f"{len(sl)} breakouts checked, {len(took)} taken.", ""]
        reasons = {}
        for d in sl:
            if d.get("skip"):
                key = d["skip"].split(":")[0].split("(")[0].strip()[:60]
                reasons[key] = reasons.get(key, 0) + 1
        if reasons:
            L += ["| Why skipped | Count |", "|---|---|"] + [f"| {a.replace('|', '/')} | {n} |" for a, n in sorted(reasons.items(), key=lambda x: -x[1])] + [""]
    notes = []
    if not tr:
        notes.append("No trades. A day without a valid setup is a normal outcome, not a failure.")
    if any(_exit_kind(t) == "still open" for t in tr):
        notes.append("A position was still open at the report — check that the 15:55 flatten ran.")
    if tr and all(_exit_kind(t) == "stopped out" for t in tr):
        notes.append("Every trade hit its stop. Losses stayed at the planned size, which is the risk rules working.")
    if worst < -1.2 * TRADE_RISK_USD:
        notes.append(f"The worst trade lost more than 1.2x its planned risk — likely a gap or slippage through the stop. Worth checking the fills.")
    if day_chg is not None and abs(day_chg - pnl) > 50 and not any(_exit_kind(t) == "still open" for t in tr):
        notes.append(f"The account moved ${day_chg - pnl:+,.0f} more than today's trades explain — a left-over position from an earlier day was closed or marked.")
    syms = [t["symbol"] for t in tr]
    if "SPY" in syms and "QQQ" in syms:
        same = len({t["side"] for t in tr if t["symbol"] in ("SPY", "QQQ")}) == 1
        if same:
            notes.append("SPY and QQQ were traded in the same direction — effectively one bet on the market. Under the current rules the second trade risks half.")
    if rs:
        notes.append(f"Running record: {len(rs)} closed trades, average {sum(rs) / len(rs):+.2f}R, {sum(1 for x in rs if x > 0) / len(rs) * 100:.0f}% winners."
                     + (" Too few trades to judge yet — wait for at least 30." if len(rs) < 30 else ""))
    L += ["## What to take from it", ""] + [f"- {n}" for n in notes] + ["", "Reviews by day: [[12 - Live Day Trading]]", ""]
    _write(ROOT / "Day Trades" / f"Day Trade Review {today}.md", "\n".join(L))
