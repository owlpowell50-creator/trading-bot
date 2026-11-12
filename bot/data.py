"""
data.py - price history: download, splice, sanity-check.

Every asset the bot trades is represented by a *total-return* series
(dividends reinvested). Before an ETF existed, its older Vanguard mutual-fund
twin is used so the history covers the 2000-2002 and 2008 crashes:

    US stocks          VFINX (1980)  -> SPY (1993)
    World ex-US stocks VGTSX (1996)  -> EFA (2001)
    7-10y Treasuries   VFITX (1991)  -> IEF (2002)
    20y+ Treasuries    VUSTX (1986)  -> TLT (2002)
    US real estate     VGSIX (1996)  -> VNQ (2004)
    Gold               GLD (2004)
    Commodities        DBC (2006)
    Cash               13-week T-bill yield (^IRX) accrued daily

Pure standard library so it runs on a stock Mac python3.
"""
from __future__ import annotations

import csv
import json
import math
import os
import ssl
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.csv"

# asset -> list of (symbol, used-from date or None for "from the start")
SPLICE = {
    "US":        [("VFINX", None), ("SPY", "1993-02-01")],
    "INTL":      [("VGTSX", None), ("EFA", "2001-09-04")],
    "BONDS":     [("VFITX", None), ("IEF", "2002-08-01")],
    "LONGBONDS": [("VUSTX", None), ("TLT", "2002-08-01")],
    "REIT":      [("VGSIX", None), ("VNQ", "2004-10-01")],
    "GOLD":      [("GLD", None)],
    "COMMOD":    [("DBC", None)],
}
CASH_SYMBOL = "^IRX"
CASH_FEE = 0.0007          # yearly cost of holding a T-bill ETF (IB01 TER)
DOWNLOAD_SYMBOLS = sorted({s for v in SPLICE.values() for s, _ in v} | {CASH_SYMBOL, "BIL"})

ASSET_NAMES = {
    "US": "US stocks (S&P 500)",
    "INTL": "Developed ex-US stocks",
    "BONDS": "US Treasuries 7-10y",
    "LONGBONDS": "US Treasuries 20y+",
    "REIT": "US real estate",
    "GOLD": "Gold",
    "COMMOD": "Commodities",
    "CASH": "Cash (T-bills)",
}


# ------------------------------------------------------------------ raw file
def load_history(path: Path = HISTORY) -> Dict[str, Dict[str, Tuple[float, float, float]]]:
    """{symbol: {date: (open, close, adjclose)}}"""
    out: Dict[str, Dict[str, Tuple[float, float, float]]] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                adj = float(row["adjclose"])
                close = float(row["close"]) if row["close"] else adj
                opn = float(row["open"]) if row["open"] else close
            except (ValueError, KeyError):
                continue
            if adj <= 0 and row["symbol"] != CASH_SYMBOL:
                continue
            out.setdefault(row["symbol"], {})[row["date"]] = (opn, close, adj)
    return out


def save_history(hist, path: Path = HISTORY) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "date", "open", "close", "adjclose"])
        for sym in sorted(hist):
            for d in sorted(hist[sym]):
                o, c, a = hist[sym][d]
                w.writerow([sym, d, f"{o:.7g}", f"{c:.7g}", f"{a:.7g}"])
    os.replace(tmp, path)


# ------------------------------------------------------------------ download
def _fetch_yahoo(symbol: str, period1: int, retries: int = 3):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbol)}?period1={period1}&period2={int(time.time())}"
           "&interval=1d&events=div%2Csplit&includeAdjustedClose=true")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
                d = json.loads(r.read().decode())
            res = d["chart"]["result"][0]
            ts = res.get("timestamp") or []
            q = res["indicators"]["quote"][0]
            adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
            rows = {}
            for i, t in enumerate(ts):
                c = q["close"][i]
                if c is None or adj[i] is None:
                    continue
                o = q["open"][i] if q["open"][i] is not None else c
                rows[datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")] = (o, c, adj[i])
            return rows
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"download failed for {symbol}: {last}")


def update_history(path: Path = HISTORY, full: bool = False, log=print) -> dict:
    """Download fresh daily bars from Yahoo and merge into history.csv.

    Yahoo re-bases adjusted closes every time a dividend is paid, so the
    whole adjusted series of a symbol is replaced on each update (we re-pull
    max history; it is a few hundred KB per symbol)."""
    hist = load_history(path) if path.exists() else {}
    report = {}
    for sym in DOWNLOAD_SYMBOLS:
        try:
            rows = _fetch_yahoo(sym, 0)
        except RuntimeError as e:
            report[sym] = f"FAILED: {e}"
            log(f"  {sym:<6} FAILED ({e})")
            continue
        if sym == CASH_SYMBOL:
            rows = {d: v for d, v in rows.items() if d >= "1985-01-01"}
        old_last = max(hist.get(sym, {"0": 0}))
        hist[sym] = rows
        new_last = max(rows) if rows else "-"
        report[sym] = new_last
        log(f"  {sym:<6} {len(rows):>6} bars, last {new_last} (was {old_last})")
    save_history(hist, path)
    return report


# ------------------------------------------------------------------ splicing
class Series:
    """Date-aligned total-return levels for each asset on the US trading calendar."""

    def __init__(self, dates: List[str], levels: Dict[str, List[Optional[float]]],
                 first_valid: Dict[str, int], price_levels: Optional[Dict[str, list]] = None):
        self.dates = dates
        self.levels = levels            # asset -> total-return level (None before inception)
        self.price_levels = price_levels or {}  # asset -> price-only level (no dividends)
        self.first_valid = first_valid  # asset -> index of first valid level
        self.idx = {d: i for i, d in enumerate(dates)}

    @property
    def assets(self):
        return list(self.levels)

    def ret(self, asset: str, i: int) -> float:
        """Total return of asset from day i-1 close to day i close."""
        lv = self.levels[asset]
        a, b = lv[i - 1], lv[i]
        if a is None or b is None or a <= 0:
            return 0.0
        return b / a - 1.0

    def available(self, asset: str, i: int) -> bool:
        return self.levels[asset][i] is not None

    def income(self, asset: str, i: int) -> float:
        """Part of day i's total return that was dividends/interest (taxable each
        year in a US taxable account). Cash is all income."""
        if asset == "CASH":
            return self.ret(asset, i)
        pl = self.price_levels.get(asset)
        if not pl or pl[i - 1] is None or pl[i] is None or pl[i - 1] <= 0:
            return 0.0
        return max(0.0, self.ret(asset, i) - (pl[i] / pl[i - 1] - 1.0))


def build_series(hist=None, start: str = "1986-01-01", use_cache: bool = True) -> Series:
    """Splice everything into one aligned Series (cached next to history.csv)."""
    cache = ROOT / "data" / "series_cache.json"
    if hist is None and use_cache and cache.exists() and HISTORY.exists() \
            and cache.stat().st_mtime >= HISTORY.stat().st_mtime:
        try:
            c = json.loads(cache.read_text())
            if c.get("start") == start and c.get("v") == 2:
                return Series(c["dates"], c["levels"], c["first_valid"], c.get("price_levels"))
        except (ValueError, KeyError):
            pass
    s = _build_series(hist or load_history(), start)
    if hist is None and use_cache:
        cache.write_text(json.dumps({"v": 2, "start": start, "dates": s.dates, "levels": s.levels,
                                     "first_valid": s.first_valid, "price_levels": s.price_levels}))
    return s


def _build_series(hist, start: str) -> Series:
    # master calendar: US stock trading days
    cal = sorted(d for d in set(hist.get("VFINX", {})) | set(hist.get("SPY", {})) if d >= start)
    levels, first_valid = _splice_levels(hist, cal, col=2)
    price_levels, _ = _splice_levels(hist, cal, col=1)
    _add_cash(levels, first_valid, hist, cal)
    return Series(cal, levels, first_valid, price_levels)


def _splice_levels(hist, cal, col: int):
    levels: Dict[str, List[Optional[float]]] = {}
    first_valid: Dict[str, int] = {}
    for asset, legs in SPLICE.items():
        lv: List[Optional[float]] = [None] * len(cal)
        level = None
        prev_px: Dict[str, Optional[float]] = {}
        for i, d in enumerate(cal):
            # which leg is active today?
            active = None
            for sym, frm in legs:
                if sym in hist and (frm is None or d >= frm) and d >= min(hist[sym]):
                    active = sym
            if active is None:
                continue
            px = _last_known(hist[active], d, col)
            if px is None:
                continue
            if level is None:
                level = 100.0
            else:
                p0 = prev_px.get(active)
                if p0:
                    level *= px / p0
                # if we just switched leg, p0 is the new leg's previous price, so the
                # day's return comes from the new leg only (no artificial jump)
            for sym, _ in legs:
                if sym in hist:
                    q = _last_known(hist[sym], d, col)
                    if q is not None:
                        prev_px[sym] = q
            lv[i] = level
        levels[asset] = lv
        first_valid[asset] = next((i for i, x in enumerate(lv) if x is not None), len(cal))
    return levels, first_valid


def _add_cash(levels, first_valid, hist, cal):
    # cash from T-bill yield
    irx = hist.get(CASH_SYMBOL, {})
    lv = [None] * len(cal)
    level = 100.0
    prev_d = None
    for i, d in enumerate(cal):
        y = _last_known(irx, prev_d or d)
        if prev_d is not None and y is not None:
            days = (date.fromisoformat(d) - date.fromisoformat(prev_d)).days
            level *= 1 + (max(y, 0.0) / 100.0 - CASH_FEE) * days / 365.0
        lv[i] = level
        prev_d = d
    levels["CASH"] = lv
    first_valid["CASH"] = 0


_cache_keys: Dict[int, List[str]] = {}


def _last_known(rows: Dict[str, tuple], d: str, col: int = 2):
    """Column `col` (1=close, 2=adjclose) for date d, or the most recent earlier bar."""
    if d in rows:
        return rows[d][col]
    key = id(rows)
    ks = _cache_keys.get(key)
    if ks is None or len(ks) != len(rows):
        ks = sorted(rows)
        _cache_keys[key] = ks
    import bisect
    j = bisect.bisect_right(ks, d) - 1
    if j < 0:
        return None
    return rows[ks[j]][col]


# ------------------------------------------------------------------ checks
def sanity_check(hist, max_age_days: int = 4, today: Optional[date] = None) -> List[str]:
    """Problems that should stop the bot from trading today."""
    today = today or date.today()
    problems = []
    for sym in ("SPY", "EFA", "IEF", "TLT", "GLD", "VNQ", CASH_SYMBOL):
        rows = hist.get(sym)
        if not rows:
            problems.append(f"{sym}: no data")
            continue
        last = max(rows)
        age = (today - date.fromisoformat(last)).days
        if age > max_age_days:
            problems.append(f"{sym}: last bar {last} is {age} days old (stale)")
        ks = sorted(rows)[-260:]
        for a, b in zip(ks, ks[1:]):
            pa, pb = rows[a][2], rows[b][2]
            if sym != CASH_SYMBOL and pa > 0 and abs(pb / pa - 1) > 0.25:
                problems.append(f"{sym}: {b} moved {pb / pa - 1:+.0%} in one day (check data)")
    return problems
