"""Second day-trading strategy: the day-trader-skill pack (vendor/day-trader-skill, MIT) run on autopilot.

Pipeline, every poll from 9:50 to 11:30 New York, in the SAME separate Alpaca paper account as the SPY/QQQ ORB:
  1. trader-scanner  - its orb_hit() on today's 5-minute bars of a liquid watchlist (first close above the
                       15-minute opening-range high)
  2. trader-exit     - its default plan: stop at the opening-range midpoint, target 2R
  3. trader-news     - its keyword tags on today's headlines (Alpaca news feed); skip earnings/halt/deal/risk news
  4. trader-timemachine - its 10,000-replay Monte Carlo on the stock's own last ~40 sessions + the history replay;
                       only "Leans/Strongly toward the target" verdicts pass
  5. trader-budget / trader-risk rules - 0.25% of equity at risk, max 15% of equity per position, max 3 trades a
                       day, reward/risk >= 1, stop required, no entries after 11:30, flat by 15:55
  6. bracket order (market entry + stop + target) placed by our own paper-only code.

The pack's own trader-broker asks a human "yes" for every order by design; this bot does not use it.
Long only, like the pack (v2 is buy only).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .data import ROOT

PACK = ROOT / "vendor" / "day-trader-skill"
WATCH = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "NFLX", "JPM", "BAC", "XOM",
         "COST", "WMT", "LLY", "UNH", "V", "MA", "ORCL", "CRM", "ADBE", "INTC", "MU", "QCOM", "PLTR", "UBER",
         "DIS", "BA", "CAT"]
RULES = {"risk_pct": 0.0025, "max_position_pct": 0.15, "max_trades_per_day": 3, "min_reward_risk": 1.0,
         "target_r": 2.0, "no_entries_before": "09:50", "no_entries_after": "11:30", "flat_by": "15:55",
         "replays": 10000, "seed": 19, "skip_news_tags": {"earnings", "halt", "deal", "risk"}}
PREFIX = "dts"


def _load(name, rel):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, PACK / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def pack():
    return (_load("dts_scan", "trader-scanner/scan.py"), _load("dts_tm", "trader-timemachine/timemachine.py"),
            _load("dts_news", "trader-news/news.py"))


def _iso(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_bars(api, symbols, start, end, feed):
    """{SYM: [alpaca bar]} with pagination."""
    out, token = {}, None
    while True:
        q = {"symbols": ",".join(symbols), "timeframe": "5Min", "feed": feed, "start": _iso(start), "end": _iso(end),
             "limit": 10000, "adjustment": "raw"}
        if token:
            q["page_token"] = token
        r = api.call("GET", "/v2/stocks/bars?" + urllib.parse.urlencode(q), data=True)
        for s, bs in (r.get("bars") or {}).items():
            out.setdefault(s, []).extend(bs)
        token = r.get("next_page_token")
        if not token:
            return out


def chart_json(sym, bars, now_utc):
    """Alpaca bars -> the Yahoo chart JSON the time machine reads (so it needs no Yahoo access)."""
    ts, o, h, l, c, v = [], [], [], [], [], []
    for b in sorted(bars, key=lambda b: b["t"]):
        t = datetime.fromisoformat(b["t"].replace("Z", "+00:00"))
        ts.append(int(t.timestamp())); o.append(b["o"]); h.append(b["h"]); l.append(b["l"]); c.append(b["c"])
        v.append(b.get("v", 0))
    return json.dumps({"chart": {"result": [{
        "meta": {"symbol": sym, "dataGranularity": "5m", "regularMarketTime": int(now_utc.timestamp())},
        "timestamp": ts, "indicators": {"quote": [{"open": o, "high": h, "low": l, "close": c, "volume": v}]}}],
        "error": None}})


def scanner_bars(scan, bars, day):
    """Alpaca bars -> the bar dicts trader-scanner's orb_hit() expects (naive New York start times)."""
    out = []
    for b in sorted(bars, key=lambda b: b["t"]):
        t = datetime.fromisoformat(b["t"].replace("Z", "+00:00"))
        et = scan.to_eastern(t.astimezone(timezone.utc))
        if et.date() != day:
            continue
        out.append({"start": et, "c": float(b["c"]), "h": float(b["h"]), "l": float(b["l"]), "v": b.get("v", 0)})
    return out


def news_flags(api, news, sym, day):
    """trader-news keyword tags on today's headlines for one ticker (since 4 PM the day before)."""
    since = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) - timedelta(hours=4)
    try:
        r = api.call("GET", "/v1beta1/news?" + urllib.parse.urlencode(
            {"symbols": sym, "start": _iso(since), "limit": 50}), data=True)
    except Exception:  # noqa: BLE001 - news is a filter, not a requirement
        return set(), []
    import re
    tags, heads = set(), []
    for it in r.get("news") or []:
        hay = f"{it.get('headline', '')} {it.get('summary', '')}"
        t = {label for label, rx in news.KEYWORDS if re.search(rx, hay, re.I)}
        if t:
            heads.append(it.get("headline", "")[:90])
        tags |= t
    return tags, heads[:3]


def evaluate(api, sym, today_bars, hist_bars, day, now_utc, equity, mods=None):
    """Run one stock through scanner -> exit -> news -> time machine -> sizing. Returns a decision dict."""
    scan, tm, news = mods or pack()
    bars = scanner_bars(scan, today_bars, day)
    if len(bars) < 4 or bars[0]["start"].strftime("%H:%M") != "09:30":
        return None
    hit = scan.orb_hit(bars, 3)
    if not hit:
        return None
    d = {"symbol": sym, "time": hit["at"], "price": hit["price"], "or_high": hit["or_high"], "or_low": hit["or_low"]}
    if hit["bar_index"] != len(bars) - 1:
        d["skip"] = f"breakout at {hit['at']} already passed"; return d
    entry = hit["price"]; stop = round((hit["or_high"] + hit["or_low"]) / 2, 2)      # trader-exit default: or-mid
    risk = entry - stop
    if risk <= 0.01:
        d["skip"] = "stop too close"; return d
    target = round(entry + RULES["target_r"] * risk, 2)
    d.update(stop=stop, target=target)
    tags, heads = news_flags(api, news, sym, day)
    bad = tags & RULES["skip_news_tags"]
    d["news"] = sorted(tags)
    if bad:
        d["skip"] = f"news: {', '.join(sorted(bad))} ({heads[0] if heads else ''})"; return d
    plan = tm.normalize_plan({"symbol": sym, "side": "buy", "date": day.isoformat(), "entry": entry, "stop": stop,
                              "target": target, "entry_bar": hit["bar_index"], "setup": "orb",
                              "opening_range": {"minutes": 15}, "stop_rule": "or_mid", "flat_by": RULES["flat_by"]},
                             "skill_trader")
    naive = now_utc.astimezone(timezone.utc).replace(tzinfo=None)          # the pack works in naive UTC
    try:
        doc = tm.time_machine(chart_json(sym, hist_bars + today_bars, now_utc), plan, naive,
                              replays=RULES["replays"], seed=RULES["seed"], until=RULES["flat_by"], source="alpaca")
    except tm.TMError as e:
        d["skip"] = f"time machine: {e}"; return d
    mc = doc["mc"]; h = doc["history"]
    d.update(verdict=doc["verdict"], p_target=mc["p_target"], p_stop=mc["p_stop"], avg_r=mc["avg_R"],
             sessions=mc["pool_sessions"], hist_trades=h.get("triggered"), hist_avg_r=h.get("avg_R"))
    if not doc["verdict"].startswith(("Leans toward the target", "Strongly toward the target")) or mc["avg_R"] <= 0:
        d["skip"] = "time machine: " + doc["verdict"].split(":")[0].lower(); return d
    if (target - entry) / risk < RULES["min_reward_risk"]:
        d["skip"] = "reward/risk too low"; return d
    qty = min(math.floor(equity * RULES["risk_pct"] / risk), math.floor(equity * RULES["max_position_pct"] / entry))
    if qty < 1:
        d["skip"] = "size rounds to zero"; return d
    d.update(qty=qty, risk=round(qty * risk, 2))
    return d


def order_body(d, day):
    return {"symbol": d["symbol"], "qty": str(d["qty"]), "side": "buy", "type": "market", "time_in_force": "day",
            "order_class": "bracket", "client_order_id": f"{PREFIX}-{day:%Y%m%d}-{d['symbol']}-L-r{d['risk']:.0f}",
            "take_profit": {"limit_price": f"{d['target']:.2f}"}, "stop_loss": {"stop_price": f"{d['stop']:.2f}"}}


class SkillTrader:
    """Stateful helper the live loop calls once per poll."""

    def __init__(self, api, day, log=print, mods=None):
        self.api, self.day, self.log = api, day, log
        self.mods = mods or pack()
        self.hist = {}
        self.done, self.seen = set(), set()
        self.decisions = []
        self.ready = False

    def prepare(self):
        """Load ~40 past sessions of 5-minute bars per stock once (SIP history, ends before today's open)."""
        from .daytrade_live import NY as ny
        end = datetime(self.day.year, self.day.month, self.day.day, 9, 0, tzinfo=ny)
        start = end - timedelta(days=62)
        try:
            for i in range(0, len(WATCH), 10):
                self.hist.update(fetch_bars(self.api, WATCH[i:i + 10], start, end, "sip"))
        except Exception as e:  # noqa: BLE001
            self.log(f"skill: SIP history unavailable ({e}); trying IEX")
            for i in range(0, len(WATCH), 10):
                self.hist.update(fetch_bars(self.api, WATCH[i:i + 10], start, end, "iex"))
        prior = [o for o in self.api.call("GET", "/v2/orders?status=all&limit=500&after=" +
                                          _iso(end)) if (o.get("client_order_id") or "").startswith(
            f"{PREFIX}-{self.day:%Y%m%d}-")]
        self.done = {o["symbol"] for o in prior}
        self.ready = True
        self.log(f"skill: history loaded for {len(self.hist)} stocks; {len(self.done)} skill trades already today")

    def poll(self, equity, now_et):
        from .daytrade_live import at
        if now_et < at(self.day, RULES["no_entries_before"]) or now_et >= at(self.day, RULES["no_entries_after"]):
            return
        if len(self.done) >= RULES["max_trades_per_day"]:
            return
        if not self.ready:
            self.prepare()
        start = at(self.day, "09:30"); now_utc = datetime.now(timezone.utc)
        today = {}
        for i in range(0, len(WATCH), 15):
            today.update(fetch_bars(self.api, WATCH[i:i + 15], start, now_utc, "iex"))
        for s in WATCH:
            if s in self.done or s in self.seen or len(self.done) >= RULES["max_trades_per_day"]:
                continue
            bs = [b for b in today.get(s, [])
                  if datetime.fromisoformat(b["t"].replace("Z", "+00:00")) + timedelta(minutes=5) <= now_utc]
            try:
                d = evaluate(self.api, s, bs, self.hist.get(s, []), self.day, now_utc, equity, self.mods)
            except Exception as e:  # noqa: BLE001
                self.log(f"skill {s}: error {e}"); self.seen.add(s); continue
            if not d:
                continue
            self.seen.add(s)
            if "skip" in d:
                self.log(f"skill {s}: breakout {d['time']} at {d['price']} - skipped ({d['skip']})")
            else:
                try:
                    o = self.api.call("POST", "/v2/orders", order_body(d, self.day))
                    self.done.add(s); d["order"] = (o.get("id") or "")[:8]
                    self.log(f"skill {s}: LONG {d['qty']} at ~{d['price']} after the {d['time']} close; stop {d['stop']} "
                             f"target {d['target']} risk ${d['risk']:.0f}; {d['verdict']}")
                except Exception as e:  # noqa: BLE001
                    d["skip"] = f"order rejected: {e}"; self.log(f"skill {s}: {d['skip']}")
            d["date"] = self.day.isoformat()
            self.decisions.append(d)
        self.save()

    def save(self):
        from .daytrade_live import STATE
        st = json.loads(STATE.read_text()) if STATE.exists() else {"trades": [], "days": []}
        keep = [x for x in st.get("skill_log", []) if x.get("date") != self.day.isoformat()]
        st["skill_log"] = (keep + self.decisions)[-200:]
        STATE.write_text(json.dumps(st, indent=1))
