"""Daily closes of the Dow, S&P 500 and Nasdaq for the Obsidian home page's comparison lines.

Obsidian can't always reach Yahoo, so the bot fetches them on GitHub and writes state/benchmarks.json.
Real index levels from Yahoo first; if Yahoo refuses, the ETFs that track them (DIA, SPY, QQQ) from Alpaca."""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

from .data import ROOT

OUT = ROOT / "state" / "benchmarks.json"
INDEXES = {"^DJI": "DIA", "^GSPC": "SPY", "^IXIC": "QQQ"}
START = "2026-10-01"


def _yahoo(sym, start):
    p1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    p2 = int(time.time()) + 86400
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym)}"
           f"?period1={p1}&period2={p2}&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    r = json.loads(urllib.request.urlopen(req, timeout=20).read())["chart"]["result"][0]
    off = r["meta"].get("gmtoffset", 0)
    out = []
    for t, c in zip(r.get("timestamp") or [], r["indicators"]["quote"][0].get("close") or []):
        if c is not None:
            out.append([datetime.fromtimestamp(t + off, timezone.utc).strftime("%Y-%m-%d"), round(c, 2)])
    return out


def _alpaca(http, etf, start):
    q = f"/v2/stocks/{etf}/bars?timeframe=1Day&start={start}T00:00:00Z&limit=1000&adjustment=all&feed=iex"
    return [[b["t"][:10], b["c"]] for b in (http("GET", q) or {}).get("bars") or []]


def write(http=None, start: str = START):
    series, source = {}, {}
    for idx, etf in INDEXES.items():
        try:
            s = _yahoo(idx, start)
            if s:
                series[idx], source[idx] = s, "Yahoo index level"
                continue
        except Exception as e:  # noqa: BLE001
            print(f"benchmarks: Yahoo {idx} failed ({e})")
        if http:
            try:
                s = _alpaca(http, etf, start)
                if s:
                    series[idx], source[idx] = s, f"{etf} ETF (Alpaca)"
            except Exception as e:  # noqa: BLE001
                print(f"benchmarks: Alpaca {etf} failed ({e})")
    if not series:
        return None
    doc = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": source, "series": series}
    OUT.write_text(json.dumps(doc, indent=1))
    print("benchmarks:", {k: (len(v), v[-1]) for k, v in series.items()})
    return doc
