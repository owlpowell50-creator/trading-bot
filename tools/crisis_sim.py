"""Crisis simulation: the long-term bot (live settings) replayed through every major market crisis since 1987,
next to the S&P 500, the Dow and the Nasdaq. Plus the day trader's opening-range breakout on the crises
that have 5-minute data (Alpaca, 2016+).

    python tools/crisis_sim.py                 # needs Yahoo (index levels); Alpaca keys optional (day trader)
Writes state/crisis.json and "15 - Crisis Simulation.md".
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import backtest as bt, config, data, strategies as st  # noqa: E402
from bot.vault import FM, _write  # noqa: E402

ROOT = data.ROOT
OUT = ROOT / "state" / "crisis.json"
NOTE = ROOT / "15 - Crisis Simulation.md"
IDX_CSV = ROOT / "data" / "indexes.csv"

# S&P 500 peak -> trough (closing prices), the standard dates for each sell-off
CRISES = [
    ("Black Monday 1987", "1987-08-25", "1987-12-04"),
    ("Gulf War recession 1990", "1990-07-16", "1990-10-11"),
    ("Russia / LTCM 1998", "1998-07-17", "1998-10-08"),
    ("Dot-com bust 2000-02", "2000-03-24", "2002-10-09"),
    ("Global financial crisis 2007-09", "2007-10-09", "2009-03-09"),
    ("Flash crash / euro scare 2010", "2010-04-23", "2010-07-02"),
    ("US downgrade / euro debt 2011", "2011-04-29", "2011-10-03"),
    ("China / oil crash 2015-16", "2015-05-21", "2016-02-11"),
    ("Q4 2018 sell-off", "2018-09-20", "2018-12-24"),
    ("COVID crash 2020", "2020-02-19", "2020-03-23"),
    ("Inflation bear market 2022", "2022-01-03", "2022-10-12"),
    ("Tariff shock 2025", "2025-02-19", "2025-04-08"),
]
INDEXES = [("S&P 500", "^GSPC"), ("Dow", "^DJI"), ("Nasdaq", "^IXIC")]


def fetch_indexes():
    """Daily closes of the three indexes since 1985 (Yahoo). Cached in data/indexes.csv."""
    out = {}
    for _, sym in INDEXES:
        p1, p2 = int(datetime(1985, 1, 1, tzinfo=timezone.utc).timestamp()), int(time.time()) + 86400
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym)}?period1={p1}&period2={p2}&interval=1d"
        for k in range(4):
            try:
                r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                                      timeout=30).read())["chart"]["result"][0]
                break
            except Exception as e:  # noqa: BLE001
                if k == 3:
                    raise
                print(f"{sym}: retry ({e})"); time.sleep(5 * (k + 1))
        off = r["meta"].get("gmtoffset", 0)
        out[sym] = {datetime.fromtimestamp(t + off, timezone.utc).strftime("%Y-%m-%d"): c
                    for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c}
        print(sym, len(out[sym]), min(out[sym]), max(out[sym]))
    with IDX_CSV.open("w") as f:
        f.write("symbol,date,close\n")
        for sym, m in out.items():
            for d in sorted(m):
                f.write(f"{sym},{d},{m[d]:.4f}\n")
    return out


def load_indexes():
    if not IDX_CSV.exists() or os.environ.get("REFRESH_INDEXES"):
        return fetch_indexes()
    out = {}
    for line in IDX_CSV.read_text().splitlines()[1:]:
        s, d, c = line.split(",")
        out.setdefault(s, {})[d] = float(c)
    return out


def curve_stats(dates, vals, a, b, after_days=3650):
    """Return a->b, worst drop inside the window, and trading days after a until the a-level is regained."""
    ix = [k for k, d in enumerate(dates) if a <= d <= b]
    if len(ix) < 2:
        return None
    i0, i1 = ix[0], ix[-1]
    v0 = vals[i0]
    pk, mdd = v0, 0.0
    for k in range(i0, i1 + 1):
        pk = max(pk, vals[k]); mdd = min(mdd, vals[k] / pk - 1)
    rec = None
    for k in range(i1, min(len(vals), i1 + after_days)):
        if vals[k] >= v0:
            rec = dates[k]; break
    one_year = next((k for k in range(i1, len(dates)) if dates[k] >= (date.fromisoformat(dates[i1]) + timedelta(days=365)).isoformat()), None)
    return {"start": dates[i0], "end": dates[i1], "ret": vals[i1] / v0 - 1, "max_dd": mdd,
            "recovered": rec, "months_to_recover": (round((date.fromisoformat(rec) - date.fromisoformat(dates[i0])).days / 30.44, 1)
                                                    if rec else None),
            "ret_incl_next_year": (vals[one_year] / v0 - 1) if one_year is not None else None}


def full_stats(dates, vals, a):
    ix = [k for k, d in enumerate(dates) if d >= a]
    i0, i1 = ix[0], ix[-1]
    yrs = (date.fromisoformat(dates[i1]) - date.fromisoformat(dates[i0])).days / 365.25
    pk, mdd = vals[i0], 0.0
    for k in ix:
        pk = max(pk, vals[k]); mdd = min(mdd, vals[k] / pk - 1)
    return {"from": dates[i0], "to": dates[i1], "cagr": (vals[i1] / vals[i0]) ** (1 / yrs) - 1, "max_dd": mdd,
            "growth_of_10k": 10000 * vals[i1] / vals[i0]}


def day_trader(crises):
    """Opening-range breakout on SPY/QQQ through the crises Alpaca has 5-minute bars for (SIP, 2016+)."""
    if not (os.environ.get("APCA_DT_KEY_ID") or os.environ.get("APCA_API_KEY_ID")):
        return {"skipped": "no Alpaca keys"}
    from bot.daytrade_live import Alpaca
    from bot.daytrade_month import simulate
    if not os.environ.get("APCA_DT_KEY_ID"):
        os.environ["APCA_DT_KEY_ID"] = os.environ["APCA_API_KEY_ID"]; os.environ["APCA_DT_SECRET_KEY"] = os.environ["APCA_API_SECRET_KEY"]
    api = Alpaca()
    http = lambda m, p, b=None: api.call(m, p, b, data=True)  # noqa: E731
    out = []
    for name, a, b in crises:
        if a < "2016-01-04":
            continue
        try:
            r = simulate(http, a, b, feed="sip", save=False)
        except Exception as e:  # noqa: BLE001
            out.append({"name": name, "error": str(e)[:200]}); continue
        tr = r["trades"]; eq = [r["capital"]] + [d["equity"] for d in r["days"]]
        pk, mdd = eq[0], 0.0
        for x in eq:
            pk = max(pk, x); mdd = min(mdd, x / pk - 1)
        w = [t for t in tr if t["pnl"] > 0]; l = [t for t in tr if t["pnl"] <= 0]
        gl = abs(sum(t["pnl"] for t in l))
        out.append({"name": name, "start": a, "end": b, "ret": r["equity"] / r["capital"] - 1, "max_dd": mdd,
                    "trades": len(tr), "win_rate": len(w) / len(tr) if tr else None,
                    "profit_factor": (sum(t["pnl"] for t in w) / gl) if gl else None,
                    "days": len([d for d in r["days"] if "note" not in d])})
        print("ORB", name, f"{out[-1]['ret']:+.2%}", len(tr), "trades")
    return {"crises": out}


def main():
    cfg = config.load()
    s = data.build_series()
    strat = st.by_name(cfg["strategy"], cfg["vol_cap"], cfg["max_single_asset"])
    r = bt.run(s, strat, start="1986-06-01", cost_bps=cfg["cost_bps"], band=cfg["no_trade_band"], capital=10000.0)
    spy_tr = bt.run(s, st.BuyHold({"US": 1.0}, "SPY"), start="1986-06-01", capital=10000.0)   # S&P 500 with dividends
    idx = load_indexes()
    curves = {"Bot": (r.dates, r.equity), "S&P 500 + dividends": (spy_tr.dates, spy_tr.equity)}
    for name, sym in INDEXES:
        m = idx.get(sym) or {}
        ds = sorted(m)
        curves[name] = (ds, [m[d] for d in ds])
    bot_from = r.weights_log[0][0]
    rows = []
    for name, a, b in CRISES:
        row = {"name": name, "start": a, "end": b, "by": {}}
        for k, (ds, vs) in curves.items():
            if ds and ds[0] <= a:
                row["by"][k] = curve_stats(ds, vs, a, b)
        rows.append(row)
    full = {k: full_stats(ds, vs, bot_from) for k, (ds, vs) in curves.items() if ds and ds[0] <= bot_from}
    # what the bot held going into and coming out of each crisis
    held = []
    for name, a, b in CRISES:
        before = [w for d, w in r.weights_log if d <= a]
        mid = [w for d, w in r.weights_log if a < d <= b]
        held.append({"name": name, "into": before[-1] if before else None,
                     "during": mid[len(mid) // 2] if mid else None})
    doc = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "strategy": strat.name,
           "settings": {"vol_cap": cfg["vol_cap"], "max_single_asset": cfg["max_single_asset"],
                        "no_trade_band": cfg["no_trade_band"], "cost_bps": cfg["cost_bps"]},
           "bot_from": bot_from, "crises": rows, "full": full, "held": held,
           "assets_available": {a: next((s.dates[i] for i in range(len(s.dates)) if s.levels[a][i] is not None), None)
                                for a in s.assets},
           "day_trader": day_trader(CRISES)}
    OUT.write_text(json.dumps(doc, indent=1))
    write_note(doc)
    print(json.dumps({k: v for k, v in doc.items() if k in ("full",)}, indent=1))


def write_note(doc):
    pct = lambda x: "—" if x is None else f"{x * 100:+.1f}%"   # noqa: E731
    cols = ["Bot", "S&P 500 + dividends", "S&P 500", "Dow", "Nasdaq"]
    L = [FM.format(type="crisis-simulation", updated=doc["generated"], extra_tags="\n  - backtest\n  - crisis"),
         "# 15 - Crisis Simulation", "",
         f"> [!info] The long-term bot ({doc['strategy']}, today's settings: volatility cap {doc['settings']['vol_cap'] * 100:.1f}%, "
         f"max {doc['settings']['max_single_asset'] * 100:.0f}% in one fund, {doc['settings']['cost_bps']} bp costs) replayed "
         f"day by day from {doc['bot_from']} through every major crisis, against the S&P 500, the Dow and the Nasdaq.",
         "> Index columns are price only (no dividends), like the numbers you see quoted; *S&P 500 + dividends* is the fair "
         "comparison because the bot's numbers include dividends and interest. Before 2004 the bot could only use US stocks, "
         "foreign stocks, Treasuries, real estate and cash (gold and commodity ETFs didn't exist yet). Taxes not included.", "",
         "## Whole period", "", "| | Yearly return | Worst fall from a peak | $10,000 became |", "|---|---|---|---|"]
    for k in cols:
        f = doc["full"].get(k)
        if f:
            L.append(f"| {'**Bot**' if k == 'Bot' else k} | {pct(f['cagr'])} | {pct(f['max_dd'])} | ${f['growth_of_10k']:,.0f} |")
    L += [f"", f"From {doc['full']['Bot']['from']} to {doc['full']['Bot']['to']}.", "",
          "## Crisis by crisis — return from the S&P 500's peak to its bottom", "",
          "| Crisis | Window | " + " | ".join(cols) + " |", "|---|---|" + "---|" * len(cols)]
    wins = 0; n = 0
    for c in doc["crises"]:
        b = c["by"]
        if "Bot" in b and "S&P 500 + dividends" in b:
            n += 1; wins += b["Bot"]["ret"] > b["S&P 500 + dividends"]["ret"]
        cells = []
        for k in cols:
            v = b.get(k)
            cells.append("—" if not v else (f"**{pct(v['ret'])}**" if k == "Bot" else pct(v["ret"])))
        L.append(f"| {c['name']} | {c['start']} → {c['end']} | " + " | ".join(cells) + " |")
    L += ["", f"The bot lost less than the S&P 500 (with dividends) in **{wins} of {n}** crises.", "",
          "## Worst fall inside each crisis, and how long until it was back to where it started", "",
          "| Crisis | Bot worst fall | Bot back to start | S&P 500 worst fall | S&P 500 back to start | Nasdaq back to start |",
          "|---|---|---|---|---|---|"]
    mo = lambda v: "—" if not v else ("not yet" if v["months_to_recover"] is None else f"{v['months_to_recover']:.0f} months")  # noqa: E731
    for c in doc["crises"]:
        b = c["by"]; bo, sp, nq = b.get("Bot"), b.get("S&P 500 + dividends"), b.get("Nasdaq")
        L.append(f"| {c['name']} | {pct(bo['max_dd']) if bo else '—'} | {mo(bo)} | {pct(sp['max_dd']) if sp else '—'} | {mo(sp)} | {mo(nq)} |")
    L += ["", "## Crash plus the year after (does it miss the rebound?)", "",
          "| Crisis | Bot | S&P 500 + dividends | Nasdaq |", "|---|---|---|---|"]
    for c in doc["crises"]:
        b = c["by"]
        g = lambda k: pct(b[k]["ret_incl_next_year"]) if b.get(k) else "—"  # noqa: E731
        L.append(f"| {c['name']} | **{g('Bot')}** | {g('S&P 500 + dividends')} | {g('Nasdaq')} |")
    names = data.ASSET_NAMES
    L += ["", "## What the bot was holding", "", "| Crisis | Going in | Halfway through |", "|---|---|---|"]
    fw = lambda w: "—" if not w else ", ".join(f"{names.get(a, a).split(' (')[0]} {x * 100:.0f}%" for a, x in sorted(w.items(), key=lambda kv: -kv[1]) if x >= 0.03)  # noqa: E731
    for h in doc["held"]:
        L.append(f"| {h['name']} | {fw(h['into'])} | {fw(h['during'])} |")
    dt = doc.get("day_trader") or {}
    L += ["", "## Day trader (opening-range breakout on SPY and QQQ) through the crises with 5-minute data", ""]
    if dt.get("skipped"):
        L.append(f"Not run: {dt['skipped']}.")
    else:
        L += ["$100,000 practice account, the live day trader's entry rules with a 2% daily loss limit (the live bot now uses a $2,000-a-day risk budget), flat every night. "
              "Alpaca SIP 5-minute bars, so only crises from 2016 on.", "",
              "| Crisis | Return | Worst fall | Trades | Winners | Profit factor | S&P 500 same window |", "|---|---|---|---|---|---|---|"]
        for c in dt.get("crises", []):
            if c.get("error"):
                L.append(f"| {c['name']} | error: {c['error'][:60]} | | | | | |"); continue
            sp = next((x["by"].get("S&P 500") for x in doc["crises"] if x["name"] == c["name"]), None)
            pf = "—" if c["profit_factor"] is None else f"{c['profit_factor']:.2f}"
            wr = "—" if c["win_rate"] is None else f"{c['win_rate'] * 100:.0f}%"
            L.append(f"| {c['name']} | **{pct(c['ret'])}** | {pct(c['max_dd'])} | {c['trades']} | {wr} | {pf} | {pct(sp['ret']) if sp else '—'} |")
    L += ["", "Source: `tools/crisis_sim.py` (GitHub → Actions → crisis). Raw numbers in `state/crisis.json`.", "",
          "Back to [[00 - Bot Dashboard]] · [[03 - Backtest Report]] · [[02 - Risk Limits]]"]
    _write(NOTE, "\n".join(L) + "\n")


if __name__ == "__main__":
    main()
