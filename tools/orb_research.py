"""
orb_research.py - which filters make the live opening-range day trader pick better trades?

Replays the live ORB rules (opening range 09:30-09:45, first 5-minute close outside it, stop at the other
side, target 1.5x the range, flat at 15:55) on real 5-minute SIP bars for SPY and QQQ since 2016, in R units
(1R = the planned risk), with 2 bp round-trip cost. Then tests candidate filters. A filter only counts as
an improvement if it raises the average R in BOTH halves of the history (2016-2020 and 2021-now) - a filter
that only helps in one half is most likely fitted to noise.

Writes state/orb_research.json and "17 - Day Trader Research.md". Never trades.
Run: python -m tools.orb_research   (needs APCA_DT_KEY_ID / APCA_DT_SECRET_KEY for market data)
"""
from __future__ import annotations

import gzip
import json
import math
import os
import statistics as stt
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.daytrade import fetch_bars, session_bars  # noqa: E402
from bot.data import ROOT  # noqa: E402
from bot.vault import FM, _write  # noqa: E402

CACHE = ROOT / "data" / "orb_5min.json.gz"
OUT = ROOT / "state" / "orb_research.json"
START = "2016-01-04"
SPLIT = "2021-01-01"
COST = 0.0002          # round trip, as a fraction of price


def load_bars(http, start=START, end=None):
    end = end or (date.today() - timedelta(days=1)).isoformat()
    cache = {}
    if CACHE.exists():
        cache = json.loads(gzip.open(CACHE, "rt").read())
    have = max((d for s in cache.values() for d in s), default=None)
    frm = (date.fromisoformat(have) + timedelta(days=1)).isoformat() if have else start
    d = date.fromisoformat(frm)
    while d.isoformat() <= end:
        e = min(date(d.year + (d.month + 2) // 12, (d.month + 2) % 12 + 1, 1) - timedelta(days=1), date.fromisoformat(end))
        raw = fetch_bars(http, d.isoformat(), e.isoformat(), feed="sip")
        for s, bars in raw.items():
            for day, bs in session_bars(bars).items():
                cache.setdefault(s, {})[day] = [[b["hm"], b["o"], b["h"], b["l"], b["c"]] for b in bs]
        print(f"bars {d} .. {e}: {sum(len(v) for v in cache.values())} sessions", flush=True)
        d = e + timedelta(days=1)
    CACHE.parent.mkdir(exist_ok=True)
    with gzip.open(CACHE, "wt") as f:
        f.write(json.dumps(cache))
    return cache


EXTRA = ["IWM", "DIA"]
CACHE_X = ROOT / "data" / "orb_5min_extra.json.gz"


def load_extra(http, end=None):
    import bot.daytrade as dtm
    end = end or (date.today() - timedelta(days=1)).isoformat()
    cache = json.loads(gzip.open(CACHE_X, "rt").read()) if CACHE_X.exists() else {}
    have = max((d for s_ in cache.values() for d in s_), default=None)
    d = date.fromisoformat((date.fromisoformat(have) + timedelta(days=1)).isoformat() if have else START)
    old = dtm.SYMBOLS
    dtm.SYMBOLS = EXTRA
    try:
        while d.isoformat() <= end:
            e = min(date(d.year + (d.month + 2) // 12, (d.month + 2) % 12 + 1, 1) - timedelta(days=1), date.fromisoformat(end))
            raw = fetch_bars(http, d.isoformat(), e.isoformat(), feed="sip")
            for s_, bars in raw.items():
                for day, bs in session_bars(bars).items():
                    cache.setdefault(s_, {})[day] = [[b["hm"], b["o"], b["h"], b["l"], b["c"]] for b in bs]
            print(f"extra bars {d} .. {e}", flush=True)
            d = e + timedelta(days=1)
    finally:
        dtm.SYMBOLS = old
    with gzip.open(CACHE_X, "wt") as f:
        f.write(json.dumps(cache))
    return cache


def extra_trade(xb, spy, qqq, target_x=3.0):
    """Trade an extra index ETF only when SPY and QQQ have confirmed the same direction AND the ETF itself has
    broken out that way too; entry at the next bar after the last of the three breakouts."""
    a, b, c = first_break(spy), first_break(qqq), first_break(xb)
    if not a or not b or not c or not (a[1] == b[1] == c[1]):
        return None
    conf = max(spy[a[0]][0], qqq[b[0]][0], xb[c[0]][0])
    if conf > "15:00":
        return None
    k = next((j for j, x in enumerate(xb) if x[0] > conf), None)
    if k is None or xb[k][0] >= "15:55":
        return None
    side, hi, lo = c[1], c[2], c[3]
    entry = xb[k][1]; h = hi - lo; stop = lo if side == 1 else hi
    risk = (entry - stop) * side
    if risk <= 0:
        return None
    tgt = entry + side * target_x * h
    exit_ = None
    for x in xb[k:]:
        if x[0] >= "15:55":
            exit_ = x[1]; break
        if (x[1] <= stop) if side == 1 else (x[1] >= stop): exit_ = x[1]; break
        if (x[3] <= stop) if side == 1 else (x[2] >= stop): exit_ = stop; break
        if (x[1] >= tgt) if side == 1 else (x[1] <= tgt): exit_ = x[1]; break
        if (x[2] >= tgt) if side == 1 else (x[3] <= tgt): exit_ = tgt; break
    if exit_ is None:
        exit_ = xb[-1][4]
    return dict(side=side, entry=entry, r=((exit_ - entry) * side - COST * entry) / risk)


def day_trade(bars, target_x=1.5, last_entry="15:00"):
    """Live rules on one session. bars: [hm, o, h, l, c]. Returns dict or None."""
    if len(bars) < 20 or bars[0][0] != "09:30":
        return None
    rng = [b for b in bars if b[0] < "09:45"]
    if len(rng) < 3:
        return None
    hi, lo = max(b[2] for b in rng), min(b[3] for b in rng)
    h = hi - lo
    if h <= 0:
        return None
    after = [b for b in bars if b[0] >= "09:45"]
    for i, b in enumerate(after[:-1]):
        if b[0] > last_entry:
            return None
        if b[4] > hi or b[4] < lo:
            side = 1 if b[4] > hi else -1
            entry = after[i + 1][1]
            stop = lo if side == 1 else hi
            risk = (entry - stop) * side
            if risk <= 0:
                return None
            tgt = entry + side * target_x * h if target_x else None
            exit_, how = None, "close"
            for c in after[i + 1:]:
                if c[0] >= "15:55":
                    exit_ = c[1]; break
                if side == 1:
                    if c[1] <= stop: exit_, how = c[1], "stop"; break
                    if c[3] <= stop: exit_, how = stop, "stop"; break
                    if tgt and c[1] >= tgt: exit_, how = c[1], "target"; break
                    if tgt and c[2] >= tgt: exit_, how = tgt, "target"; break
                else:
                    if c[1] >= stop: exit_, how = c[1], "stop"; break
                    if c[2] >= stop: exit_, how = stop, "stop"; break
                    if tgt and c[1] <= tgt: exit_, how = c[1], "target"; break
                    if tgt and c[3] <= tgt: exit_, how = tgt, "target"; break
            if exit_ is None:
                exit_ = after[-1][4]
            r = ((exit_ - entry) * side - COST * entry) / risk
            return dict(side=side, entry=entry, hi=hi, lo=lo, width=h, bar=b[0], r=r, how=how, open=bars[0][1])
    return None


def first_break(bars):
    """(index into bars, side, hi, lo) of the first 5-minute close outside the opening range, or None."""
    if len(bars) < 20 or bars[0][0] != "09:30":
        return None
    rng = [b for b in bars if b[0] < "09:45"]
    if len(rng) < 3:
        return None
    hi, lo = max(b[2] for b in rng), min(b[3] for b in rng)
    for i, b in enumerate(bars):
        if b[0] < "09:45":
            continue
        if b[4] > hi or b[4] < lo:
            return i, (1 if b[4] > hi else -1), hi, lo
    return None


def confirmed_trade(bars, me, other, target_x=1.5, last_entry="15:00", stop_mid=False):
    """No look-ahead version of 'SPY and QQQ break the same way': a symbol is entered only once BOTH have
    closed outside their opening ranges in the same direction - at the next bar's open after the later of
    the two breakouts. If the other symbol breaks the other way first or never breaks, no trade."""
    a, b = first_break(bars), first_break(other)
    if not a or not b or a[1] != b[1]:
        return None
    i, side, hi, lo = a
    conf_hm = max(bars[i][0], other[b[0]][0])
    if conf_hm > last_entry:
        return None
    k = next((j for j, x in enumerate(bars) if x[0] > conf_hm), None)
    if k is None or bars[k][0] >= "15:55":
        return None
    entry = bars[k][1]; h = hi - lo
    stop = (lo if side == 1 else hi) if not stop_mid else (hi + lo) / 2
    risk = (entry - stop) * side
    if risk <= 0:
        return None
    tgt = entry + side * target_x * h if target_x else None
    exit_, how = None, "close"
    for c in bars[k:]:
        if c[0] >= "15:55":
            exit_ = c[1]; break
        lo_hit = c[3] <= stop if side == 1 else c[2] >= stop
        op_hit = c[1] <= stop if side == 1 else c[1] >= stop
        if op_hit: exit_, how = c[1], "stop"; break
        if lo_hit: exit_, how = stop, "stop"; break
        if tgt:
            if (c[1] >= tgt) if side == 1 else (c[1] <= tgt): exit_, how = c[1], "target"; break
            if (c[2] >= tgt) if side == 1 else (c[3] <= tgt): exit_, how = tgt, "target"; break
    if exit_ is None:
        exit_ = bars[-1][4]
    r = ((exit_ - entry) * side - COST * entry) / risk
    return dict(side=side, entry=entry, hi=hi, lo=lo, width=h, bar=bars[k][0], r=r, how=how, open=bars[0][1],
                waited=bars[k][0] != bars[min(i + 1, len(bars) - 1)][0])


def features(cache):
    """Daily context per symbol/day, using only information available before the trade."""
    ctx = {}
    for s, days in cache.items():
        ds = sorted(days)
        closes, ranges = [], []
        for k, d in enumerate(ds):
            bs = days[d]
            f = {}
            if len(closes) >= 50:
                pc = closes[-1]
                f["prev_close"] = pc
                f["sma20"] = stt.mean(closes[-20:]); f["sma50"] = stt.mean(closes[-50:])
                f["atr14"] = stt.mean(ranges[-14:])
                rets = [closes[j] / closes[j - 1] - 1 for j in range(len(closes) - 20, len(closes))]
                f["vol20"] = stt.pstdev(rets) * math.sqrt(252)
                f["ret1"] = closes[-1] / closes[-2] - 1
                f["ret5"] = closes[-1] / closes[-6] - 1
                f["gap"] = bs[0][1] / pc - 1
            ctx[(s, d)] = f
            closes.append(bs[-1][4]); ranges.append(max(b[2] for b in bs) - min(b[3] for b in bs))
    return ctx


def stats(rs):
    if not rs:
        return dict(n=0)
    eq = pk = dd = 0.0
    for r in rs:
        eq += r; pk = max(pk, eq); dd = min(dd, eq - pk)
    w = [r for r in rs if r > 0]; l = [-r for r in rs if r <= 0]
    return dict(n=len(rs), avg=stt.mean(rs), win=len(w) / len(rs), pf=(sum(w) / sum(l)) if l and sum(l) else None,
                total=sum(rs), maxdd=dd, t=(stt.mean(rs) / stt.pstdev(rs) * math.sqrt(len(rs))) if len(rs) > 2 and stt.pstdev(rs) else None)


def run(http=None):
    if http is None:
        from bot.daytrade_live import Alpaca
        api = Alpaca()
        http = lambda m, p: api.call(m, p, data=True)  # noqa: E731
    cache = load_bars(http)
    ctx = features(cache)
    targets = {"1.5x range (live)": 1.5, "1.0x range": 1.0, "2.0x range": 2.0, "3.0x range": 3.0, "no target, hold to 15:55": None}
    base_by_t = {}
    for name, tx in targets.items():
        tr = []
        for s, days in cache.items():
            for d, bs in days.items():
                t = day_trade(bs, tx)
                if t and ctx.get((s, d)):
                    tr.append(dict(t, sym=s, date=d, **{"f_" + k: v for k, v in ctx[(s, d)].items()}))
        base_by_t[name] = sorted(tr, key=lambda x: (x["date"], x["sym"]))
    base = base_by_t["1.5x range (live)"]
    # does the other symbol break the same way the same day?
    by_day = {}
    for t in base:
        by_day.setdefault(t["date"], {})[t["sym"]] = t["side"]
    filters = {
        "Trend: trade only with the 20-day average": lambda t: (t["entry"] > t["f_sma20"]) == (t["side"] == 1),
        "Trend: trade only with the 50-day average": lambda t: (t["entry"] > t["f_sma50"]) == (t["side"] == 1),
        "Skip wide ranges (range > 60% of daily ATR)": lambda t: t["width"] / t["f_atr14"] <= 0.6,
        "Skip narrow ranges (range < 20% of daily ATR)": lambda t: t["width"] / t["f_atr14"] >= 0.2,
        "Breakout before 10:30 only": lambda t: t["bar"] < "10:30",
        "Breakout after 10:30 only": lambda t: t["bar"] >= "10:30",
        "Trade with the gap (gap and breakout same way)": lambda t: (t["f_gap"] > 0) == (t["side"] == 1),
        "Skip big gaps (over 1%)": lambda t: abs(t["f_gap"]) <= 0.01,
        "Skip high-volatility regimes (20-day vol > 25%)": lambda t: t["f_vol20"] <= 0.25,
        "Only high-volatility regimes (20-day vol > 18%)": lambda t: t["f_vol20"] > 0.18,
        "Longs only": lambda t: t["side"] == 1,
        "Shorts only": lambda t: t["side"] == -1,
        "SPY and QQQ break the same way": lambda t: len(set(by_day[t["date"]].values())) == 1 and len(by_day[t["date"]]) == 2,
        "Against yesterday's move (mean reversion)": lambda t: (t["f_ret1"] < 0) == (t["side"] == 1),
        "With the 5-day move": lambda t: (t["f_ret5"] > 0) == (t["side"] == 1),
    }
    def split(tr):
        a = [t["r"] for t in tr if t["date"] < SPLIT]; b = [t["r"] for t in tr if t["date"] >= SPLIT]
        return stats([t["r"] for t in tr]), stats(a), stats(b)
    rows = []
    for name, tr in base_by_t.items():
        al, a, b = split(tr); rows.append(dict(kind="target", name=name, all=al, first=a, second=b))
    b_all, b_a, b_b = split(base)
    for name, f in filters.items():
        tr = [t for t in base if f(t)]
        al, a, b = split(tr)
        ok = a.get("n", 0) >= 50 and b.get("n", 0) >= 50 and a["avg"] > b_a["avg"] and b["avg"] > b_b["avg"]
        rows.append(dict(kind="filter", name=name, all=al, first=a, second=b, both_halves=ok, kept=al.get("n", 0) / b_all["n"]))
    good = [r for r in rows if r["kind"] == "filter" and r["both_halves"] and r["kept"] >= 0.35]
    # best pair of filters that both pass
    combos = []
    for i in range(len(good)):
        for j in range(i + 1, len(good)):
            f1, f2 = filters[good[i]["name"]], filters[good[j]["name"]]
            tr = [t for t in base if f1(t) and f2(t)]
            al, a, b = split(tr)
            if a.get("n", 0) >= 50 and b.get("n", 0) >= 50 and a["avg"] > max(good[i]["first"]["avg"], good[j]["first"]["avg"]) \
                    and b["avg"] > max(good[i]["second"]["avg"], good[j]["second"]["avg"]):
                combos.append(dict(kind="combo", name=good[i]["name"] + " + " + good[j]["name"], all=al, first=a, second=b, kept=al["n"] / b_all["n"]))
    # ---- the pair filter done properly (no look-ahead) ----
    conf = {}
    for name, tx in targets.items():
        tr = []
        for s_, o_ in (("SPY", "QQQ"), ("QQQ", "SPY")):
            for d, bs in cache.get(s_, {}).items():
                ob = cache.get(o_, {}).get(d)
                if not ob or not ctx.get((s_, d)):
                    continue
                t = confirmed_trade(bs, s_, ob, tx)
                if t:
                    tr.append(dict(t, sym=s_, date=d, **{"f_" + k: v for k, v in ctx[(s_, d)].items()}))
        conf[name] = sorted(tr, key=lambda x: (x["date"], x["sym"]))
    cb = conf["1.5x range (live)"]
    for name, tr in conf.items():
        al, a, b = split(tr); rows.append(dict(kind="confirmed", name="Confirmed pair, target " + name, all=al, first=a, second=b, kept=al.get("n", 0) / b_all["n"]))
    for name in ("Trend: trade only with the 20-day average", "With the 5-day move", "Trade with the gap (gap and breakout same way)", "Skip narrow ranges (range < 20% of daily ATR)"):
        tr = [t for t in cb if filters[name](t)]
        al, a, b = split(tr); rows.append(dict(kind="confirmed", name="Confirmed pair + " + name, all=al, first=a, second=b, kept=al.get("n", 0) / b_all["n"]))
    # ---- exits and stops on the ADOPTED rule (confirmed pair + 20-day trend) ----
    trend = filters["Trend: trade only with the 20-day average"]
    for name, tx in targets.items():
        for mid in (False, True):
            tr = []
            for s_, o_ in (("SPY", "QQQ"), ("QQQ", "SPY")):
                for d, bs in cache.get(s_, {}).items():
                    ob = cache.get(o_, {}).get(d)
                    if not ob or not ctx.get((s_, d)):
                        continue
                    t = confirmed_trade(bs, s_, ob, tx, stop_mid=mid)
                    if t:
                        t = dict(t, sym=s_, date=d, **{"f_" + k: v for k, v in ctx[(s_, d)].items()})
                        if trend(t):
                            tr.append(t)
            al, a, b = split(tr)
            if tx == 3.0 and not mid:
                adopted_years = {}
                for t in tr:
                    adopted_years.setdefault(t["date"][:4], []).append(t["r"])
            rows.append(dict(kind="adopted", name=f"Live rule now, target {name}" + (", stop at the range middle" if mid else ""),
                             all=al, first=a, second=b, kept=al.get("n", 0) / b_all["n"]))
    # ---- extra index ETFs on the live rule ----
    try:
        xc = load_extra(http)
        xctx = features(xc)
        for x in EXTRA:
            tr = []
            for d, xb in xc.get(x, {}).items():
                sp, qq = cache.get("SPY", {}).get(d), cache.get("QQQ", {}).get(d)
                f = xctx.get((x, d))
                if not sp or not qq or not f:
                    continue
                t = extra_trade(xb, sp, qq)
                if t and (t["entry"] > f["sma20"]) == (t["side"] == 1):
                    tr.append(dict(t, date=d))
            al, a, b = split(tr)
            rows.append(dict(kind="extra", name=f"{x} on the live rule (SPY+QQQ confirm, {x} breaks too, 20-day trend, 3x target)",
                             all=al, first=a, second=b, kept=al.get("n", 0) / b_all["n"]))
    except Exception as e:  # noqa: BLE001
        print("extra symbols failed:", e)
    years_c = {}
    for t in cb:
        years_c.setdefault(t["date"][:4], []).append(t["r"])
    years = {}
    for t in base:
        years.setdefault(t["date"][:4], []).append(t["r"])
    res = dict(generated=date.today().isoformat(), sessions={s: len(v) for s, v in cache.items()}, base=b_all,
               rows=rows + combos, years={y: stats(v) for y, v in sorted(years.items())},
               years_confirmed={y: stats(v) for y, v in sorted(years_c.items())},
               years_adopted={y: stats(v) for y, v in sorted(adopted_years.items())},
               exits={k: sum(1 for t in base if t["how"] == k) for k in ("stop", "target", "close")},
               recommended=sorted(good + combos, key=lambda r: -min(r["first"]["avg"], r["second"]["avg"]))[:3])
    OUT.write_text(json.dumps(res, indent=1, default=str))
    write_note(res)
    return res


def _row(r):
    f = lambda s, k, fmt: (fmt.format(s[k]) if s.get(k) is not None else "—")  # noqa: E731
    return (f"| {r['name']} | {r['all'].get('n', 0)} | {f(r['all'], 'win', '{:.0%}')} | {f(r['all'], 'avg', '{:+.3f}')} | "
            f"{f(r['all'], 'pf', '{:.2f}')} | {f(r['first'], 'avg', '{:+.3f}')} | {f(r['second'], 'avg', '{:+.3f}')} | "
            f"{f(r['all'], 'maxdd', '{:.1f}')} |")


def write_note(res):
    H = "| Version | Trades | Win | Avg R | PF | Avg R 2016-20 | Avg R 2021-now | Worst run (R) |\n|---|---|---|---|---|---|---|---|"
    b = res["base"]
    L = [FM.format(type="research", updated=res["generated"], extra_tags="\n  - day-trading\n  - research"),
         "# 17 - Day Trader Research", "",
         f"The live day trader's exact rules replayed on every session since 2016 for SPY and QQQ ({sum(res['sessions'].values()):,} symbol-days of real 5-minute prices), "
         "measured in R (1R = the planned risk on a trade, so +0.10 means each trade earns a tenth of what it risks, on average). Costs of 2 bp per round trip are included.", "",
         f"**Live rules:** {b['n']:,} trades, {b['win']:.0%} winners, average **{b['avg']:+.3f}R**, profit factor {b['pf']:.2f}. "
         f"Exits: {res['exits']['stop']:,} stops, {res['exits']['target']:,} targets, {res['exits']['close']:,} at the 15:55 close.", "",
         "A change only counts if it improves **both** halves of the history (2016-2020 and 2021-now). Anything that helps in one half only is probably luck.", "",
         "## Targets", "", H] + [_row(r) for r in res["rows"] if r["kind"] == "target"] + ["",
         "## Filters (on the live 1.5x target)", "", H.replace("| Version", "| Filter") + ""] + \
        [_row(r) + "" for r in res["rows"] if r["kind"] == "filter"] + ["",
         "Passes both halves: " + (", ".join(r["name"] for r in res["rows"] if r.get("both_halves")) or "none"), ""]
    if any(r["kind"] == "combo" for r in res["rows"]):
        L += ["## Combinations that beat either filter alone in both halves", "", H] + [_row(r) for r in res["rows"] if r["kind"] == "combo"] + [""]
    L += ["## The pair rule without hindsight", "",
          "The 'SPY and QQQ break the same way' filter above peeks ahead: at SPY's breakout you may not yet know which way QQQ will go. "
          "Here each symbol is entered only after BOTH have broken out the same way, at the next bar after the later breakout - exactly what the live bot could do.", "", H] + \
         [_row(r) for r in res["rows"] if r["kind"] == "confirmed"] + ["",
          "## Exits and stops on the rule now live (pair confirmed + 20-day trend)", "", H] + \
         [_row(r) for r in res["rows"] if r["kind"] == "adopted"] + ["",
          "## Adding more index ETFs", "", H] + [_row(r) for r in res["rows"] if r["kind"] == "extra"] + ["",
          "## By year: original rules vs the rules now live", "", "| Year | Original trades | Original avg R | Original total R | Now-live trades | Now-live avg R | Now-live total R |", "|---|---|---|---|---|---|---|"] + \
         [f"| {y} | {s['n']} | {s['avg']:+.3f} | {s['total']:+.1f} | {res['years_adopted'].get(y, {}).get('n', 0)} | "
          f"{res['years_adopted'].get(y, {}).get('avg', 0):+.3f} | {res['years_adopted'].get(y, {}).get('total', 0):+.1f} |" for y, s in res["years"].items()] + ["",
         "## Recommendation", ""]
    live_row = next((r for r in res["rows"] if r["name"] == "Live rule now, target 3.0x range"), None)
    if live_row:
        ya = res.get("years_adopted", {})
        pos = sum(1 for v in ya.values() if v.get("avg", 0) > 0)
        L += [f"**Live since 30 Nov 2026:** both SPY and QQQ must break out the same way, only with the 20-day trend, target 3x the opening range. "
              f"{live_row['all']['n']:,} trades since 2016, average {live_row['all']['avg']:+.3f}R ({live_row['first']['avg']:+.3f} in 2016-20, "
              f"{live_row['second']['avg']:+.3f} in 2021-now), profitable in {pos} of {len(ya)} calendar years. "
              "Chosen from the tests above, so expect live results somewhat below these numbers. The Bot Brain compares the two every day.",
              "", "Plain-English summary: [[13 - The Live Rules and the Evidence]]."]
    L += ["", "Back to [[12 - Live Day Trading]] · [[16 - Bot Brain]]", ""]
    _write(ROOT / "17 - Day Trader Research.md", "\n".join(L))


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("base", "exits", "recommended")}, indent=1, default=str))
