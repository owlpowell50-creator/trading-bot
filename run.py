#!/usr/bin/env python3
"""
Trading bot - command line.

  python3 run.py daily            the scheduled job: update data, check, rebalance if due, write notes
  python3 run.py daily --no-download   same, using the data already on disk
  python3 run.py signal           show what the strategy wants right now (changes nothing)
  python3 run.py backtest         re-run the 1997-today evaluation and rewrite "03 - Backtest Report"
  python3 run.py update-data      download fresh prices only
  python3 run.py status           account, holdings, drawdown
  python3 run.py resume           clear a drawdown halt after you have reviewed it
  python3 run.py start-trial      fresh paper account + 30-day scorecard vs the S&P 500
  python3 run.py test             run the self-tests

Settings: edit the YAML block at the top of "02 - Risk Limits.md".
"""
from __future__ import annotations

import argparse
import os
import csv
import json
import sys
import traceback
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from bot import backtest as bt          # noqa: E402
from bot import config as cfgmod        # noqa: E402
from bot import data, risk, research, vault  # noqa: E402
from bot import strategies as st        # noqa: E402
from bot.broker import STATE, PaperBroker  # noqa: E402

RUNS = STATE / "runs.json"
EQUITY = STATE / "equity.csv"


def load_state():
    return json.loads(RUNS.read_text()) if RUNS.exists() else {"runs": [], "last_signal": None, "halted": False}


def save_state(st_):
    STATE.mkdir(parents=True, exist_ok=True)
    RUNS.write_text(json.dumps(st_, indent=1))


def equity_history():
    if not EQUITY.exists():
        return []
    with open(EQUITY) as f:
        return [(r["date"], float(r["equity"])) for r in csv.DictReader(f)]


def record_equity(d, eq):
    hist = [h for h in equity_history() if h[0] != d] + [(d, eq)]
    STATE.mkdir(parents=True, exist_ok=True)
    with open(EQUITY, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "equity"])
        for row in sorted(hist):
            w.writerow([row[0], f"{row[1]:.2f}"])
    return sorted(hist)


def make_strategy(cfg):
    return st.by_name(cfg["strategy"], cfg["vol_cap"], cfg["max_single_asset"])


def latest_prices(s: data.Series):
    i = len(s.dates) - 1
    return {a: s.levels[a][i] for a in s.assets if s.levels[a][i] is not None}


def current_signal(s, strat, today):
    me = st.MonthEnds(s, today=today)
    i = me.me[-1]
    tgt = strat.target(s, me, i)
    scores = strat.scores(s, me, i) if hasattr(strat, "scores") else {}
    return s.dates[i], tgt, scores or {}


# ------------------------------------------------------------------ daily
def cmd_daily(args):
    cfg = cfgmod.load()
    today = args.today or date.today().isoformat()
    state = load_state()
    from datetime import datetime as _dt
    run = {"date": today, "time": _dt.now().strftime("%H:%M"), "mode": cfg["mode"],
           "strategy": cfg["strategy"], "problems": [],
           "dry_run": bool(args.dry_run),
           "risk_notes": [], "orders": [], "fills": [], "halt_at": cfg["max_drawdown_halt"]}
    # 1. data
    if not args.no_download:
        print("Downloading prices...")
        try:
            data.update_history()
        except Exception as e:  # noqa: BLE001
            run["problems"].append(f"download failed: {e}")
    hist = data.load_history()
    run["problems"] += data.sanity_check(hist, cfg["data_max_age_days"], date.fromisoformat(today))
    s = data.build_series()
    run["data_through"] = s.dates[-1]
    prices = latest_prices(s)
    # 2. account
    run["instruments"] = cfg["instruments"]
    run["region"] = cfg["region"]
    if cfg["mode"] == "paper":
        broker = PaperBroker(cfg["capital"], cfg["cost_bps"])
        values = broker.values(prices)
        run["start_capital"] = broker.acct["starting_capital"]
    else:
        if cfg["mode"].startswith("alpaca"):
            from bot.broker import AlpacaBroker
            broker = AlpacaBroker(cfg, cfg["instruments"])
        elif cfg["mode"].startswith("ibkr"):
            from bot.broker import IBKRBroker
            broker = IBKRBroker(cfg, cfg["instruments"])
        else:
            raise RuntimeError(f"unknown mode {cfg['mode']!r} in '02 - Risk Limits'")
        values = broker.values()
        run["start_capital"] = state.get("start_capital") or sum(values.values())
        state["start_capital"] = run["start_capital"]
    equity = sum(values.values())
    if not args.dry_run:
        maybe_start_new_trial(cfg, today, equity, s, state)
    hist_eq = record_equity(today, equity) if not args.dry_run else \
        sorted([h for h in equity_history() if h[0] != today] + [(today, equity)])
    base = state.get("halt_baseline_date")      # set by `resume`: peak is measured from here
    hist_dd = [h for h in hist_eq if not base or h[0] >= base]
    peak, dd, breach = risk.drawdown_status(hist_dd, cfg["max_drawdown_halt"], today, equity)
    run.update(equity=equity, peak=peak, drawdown=dd,
               weights_before={a: v / equity for a, v in values.items()} if equity else {})
    run["weights_target"] = dict(run["weights_before"])
    run["weights_after"] = dict(run["weights_before"])
    if breach and not state.get("halted"):
        state["halted"] = True
        run["problems"].append(f"drawdown {dd:.1%} hit the {cfg['max_drawdown_halt']:.0%} halt - "
                               "review, then run `python3 run.py resume`")
    # 3. signal
    strat = make_strategy(cfg)
    sig_date, target, scores = current_signal(s, strat, today)
    run["signal"] = {"date": sig_date, "scores": scores}
    due = state.get("last_signal") != sig_date or not broker_has_positions(values)
    status, headline = "HOLD", f"No rebalance due (signal of {sig_date} already acted on)."
    if target is None:
        run["problems"].append("strategy could not compute a target (missing history)")
    if state.get("halted"):
        status, headline = "HALTED", "Trading paused by the drawdown rule. Nothing was sent."
    elif run["problems"] and due:
        status, headline = "BLOCKED", "Rebalance was due but data/download problems blocked it. Nothing was sent."
    elif due and target is not None:
        tgt, notes = risk.clamp_weights(target, cfg["max_single_asset"])
        run["risk_notes"] += notes
        first = not broker_has_positions(values)
        final, orders, notes2 = risk.plan_orders(values, tgt, equity,
                                                 0.0 if first else cfg["no_trade_band"],
                                                 cfg["min_trade_value"])
        run["risk_notes"] += notes2
        run["weights_target"] = final
        blocks = risk.pre_trade_checks(orders, values, equity, list(cfg["instruments"]))
        if blocks:
            run["problems"] += blocks
            status, headline = "BLOCKED", "Pre-trade checks failed. Nothing was sent."
        elif args.dry_run:
            run["orders"] = orders
            status, headline = "DRY RUN", f"{len(orders)} orders planned, not sent (--dry-run)."
        else:
            run["orders"] = orders
            if orders:
                if cfg["mode"] == "paper":
                    run["fills"] = broker.execute(orders, prices, today)
                    broker.save()
                    values = broker.values(prices)
                else:
                    run["fills"] = broker.execute(orders, today)
                    values = broker.values()
                    bf = STATE / "broker_fills.json"
                    old = json.loads(bf.read_text()) if bf.exists() else []
                    bf.write_text(json.dumps(old + run["fills"], indent=1))
                status = "TRADED"
                headline = f"Rebalanced on the {sig_date} signal: {len(orders)} orders."
            else:
                status, headline = "NO CHANGE", "Rebalance due, but holdings are already within the no-trade band."
            state["last_signal"] = sig_date
            equity = sum(values.values())
            run["equity"] = equity
            run["weights_after"] = {a: v / equity for a, v in values.items()}
            hist_eq = record_equity(today, equity)
    elif run["problems"]:
        status, headline = "HOLD", "Not a rebalance day. Problems noted below."
    if cfg["mode"] == "paper" and not args.dry_run:
        broker.save()
    else:
        try:
            broker.close()
        except Exception:  # noqa: BLE001
            pass
    run["status"], run["headline"] = status, headline
    run["scenarios"] = risk.scenario_losses(s, run["weights_target"], run["equity"])
    if not args.dry_run:
        update_trial(today, run["equity"], s)
    p = vault.write_journal(run)
    if args.dry_run:
        print(f"{status}: {headline}")
        for o in run["orders"]:
            print(f"  would {o['side']:<4} {o['asset']:<10} {o['value']:>12,.2f}")
        print(f"Journal: {p}")
        return 0
    state["runs"].append({"date": today, "status": status, "equity": run["equity"]})
    state["runs"] = state["runs"][-500:]
    save_state(state)
    vault.write_dashboard(run, hist_eq, state["runs"])
    (STATE / "last_run.json").write_text(json.dumps(run, default=str))
    refresh_extras(cfg, s, today)
    if cfg["mode"].startswith("alpaca"):
        live_notes(cfg, broker, today, run)
    print(f"{status}: {headline}")
    for pr in run["problems"]:
        print("  !", pr)
    print(f"Journal: {p}")
    if status in ("TRADED", "BLOCKED", "HALTED") or run["problems"]:
        write_alert(status if status != "HOLD" else "WARNING", headline, run, p)
    return 1 if status in ("BLOCKED", "HALTED") else 0


def write_alert(status, headline, run, journal_path):
    """state/alert.md -> the GitHub workflow turns it into an Issue, which GitHub
    emails / pushes to your phone. Not committed (see .gitignore)."""
    icon = {"TRADED": "🟢", "BLOCKED": "🔴", "HALTED": "🛑", "WARNING": "⚠️"}.get(status, "ℹ️")
    lines = [f"{icon} **{status}** — {headline}", "",
             f"Equity {run['equity']:,.0f} · drawdown {run['drawdown']:.1%} · data through {run['data_through']}", ""]
    if run.get("orders"):
        lines += ["| Side | ETF | Value |", "|---|---|---|"]
        for o in run["orders"]:
            lines.append(f"| {o['side']} | {run['instruments'][o['asset']]['symbol']} | {o['value']:,.0f} |")
        lines.append("")
    for pr in run.get("problems", []):
        lines.append(f"- ⚠️ {pr}")
    lines += ["", f"Full journal: `{Path(journal_path).name}`"]
    (STATE / "alert.md").write_text("\n".join(lines))
    (STATE / "alert_title.txt").write_text(f"{icon} Bot {status} {run['date']}: {headline[:80]}")


TRIAL = STATE / "trial.json"


def replay(cfg, s, months=12):
    strat = make_strategy(cfg)
    start = s.dates[max(0, len(s.dates) - 21 * months - 30)]
    r = bt.run(s, strat, start=start, cost_bps=cfg["cost_bps"], band=cfg["no_trade_band"], capital=10000.0)
    spy = bt.run(s, st.BuyHold({"US": 1.0}, "SPY"), start=start, capital=10000.0)
    spy_by_date = dict(zip(spy.dates, spy.equity))
    t0 = r.weights_log[0][0]
    # rebase both to 10,000 on the first trade day
    i0 = r.dates.index(t0)
    b0, s0 = r.equity[i0], spy_by_date[t0]
    dates = r.dates[i0:]
    bot = [x / b0 * 10000 for x in r.equity[i0:]]
    spyc = [spy_by_date[d] / s0 * 10000 for d in dates]
    months_out, prev = [], {}
    log = r.weights_log
    for k, (d, w) in enumerate(log):
        nxt = log[k + 1][0] if k + 1 < len(log) else dates[-1]
        ia, ib = dates.index(d), dates.index(nxt)
        changes = [{"asset": a, "delta": w.get(a, 0) - prev.get(a, 0), "new": w.get(a, 0)}
                   for a in sorted(set(w) | set(prev)) if abs(w.get(a, 0) - prev.get(a, 0)) >= 0.005]
        months_out.append({"date": d, "weights": w, "changes": changes,
                           "bot": bot[ib] / bot[ia] - 1, "spy": spyc[ib] / spyc[ia] - 1})
        prev = w
    # monthly points for the chart
    idx = [k for k in range(len(dates)) if k == 0 or dates[k][:7] != dates[k - 1][:7]] + [len(dates) - 1]
    def mdd(xs):
        pk, m = xs[0], 0.0
        for x in xs:
            pk = max(pk, x); m = min(m, x / pk - 1)
        return m
    labels = [dates[k][:7] for k in idx[:-1]] + [dates[-1]]
    return {"generated": dates[-1], "start": t0, "labels": labels,
            "bot_curve": [bot[k] for k in idx], "spy_curve": [spyc[k] for k in idx],
            "bot_ret": bot[-1] / bot[0] - 1, "spy_ret": spyc[-1] / spyc[0] - 1,
            "bot_dd": mdd(bot), "spy_dd": mdd(spyc), "months": months_out}


def live_notes(cfg, broker, today, run):
    """Real Alpaca account note + day-trading simulator on real intraday bars.
    Never allowed to break the daily run."""
    from bot import live, daytrade
    try:
        snap = live.snapshot(broker)
        live.write_live_account(snap, cfg["instruments"], run["start_capital"], equity_history(), today)
    except Exception as e:  # noqa: BLE001
        run.setdefault("problems", [])
        print("live account note skipped:", e)
    try:
        st = daytrade.run(broker.data_http, today)
        daytrade.write_note(st, today)
    except Exception as e:  # noqa: BLE001
        print("day-trading simulator skipped:", e)


def refresh_extras(cfg, s, today):
    if cfg["mode"] == "paper":
        acct = STATE / "paper_account.json"
        fills = json.loads(acct.read_text())["fills"] if acct.exists() else []
    else:
        bf = STATE / "broker_fills.json"
        fills = json.loads(bf.read_text()) if bf.exists() else []
    vault.write_trade_log(fills, cfg["instruments"], today)
    try:
        vault.write_replay(replay(cfg, s), cfg["instruments"])
    except Exception as e:  # noqa: BLE001  (a replay problem must never stop the daily run)
        print("replay note skipped:", e)


def cmd_notes(args):
    """Rebuild the Obsidian notes from the saved state (no trading, no download)."""
    cfg = cfgmod.load()
    s = data.build_series()
    lr = STATE / "last_run.json"
    if lr.exists():
        run = json.loads(lr.read_text())
        vault.write_dashboard(run, equity_history(), load_state()["runs"])
    if TRIAL.exists():
        vault.write_trial(json.loads(TRIAL.read_text()))
    refresh_extras(cfg, s, (json.loads(lr.read_text())["date"] if lr.exists() else date.today().isoformat()))
    from bot import live, daytrade
    if live.SNAP.exists():
        lrun = json.loads(lr.read_text()) if lr.exists() else {"start_capital": 100000.0}
        live.write_live_account(json.loads(live.SNAP.read_text()), cfg["instruments"],
                                lrun.get("start_capital", 100000.0), equity_history(), lrun.get("date", ""))
    if daytrade.STATE.exists():
        daytrade.write_note(daytrade.load(), date.today().isoformat())
    print("Notes rebuilt: 00 Dashboard, 06 Trial, 07 Trade Log, 08 Replay, 10 Live Account, 11 Day Trading")
    return 0


def update_trial(today, equity, s):
    """Track the paper trial against an S&P 500 buy-and-hold started the same day."""
    if not TRIAL.exists():
        return
    t = json.loads(TRIAL.read_text())
    us = s.levels["US"]
    t["days"] = [d for d in t["days"] if d["date"] != today]
    bot_ret = equity / t["start_equity"] - 1
    spy_ret = us[-1] / t["spy_start_level"] - 1
    t["days"].append({"date": today, "data_through": s.dates[-1], "equity": round(equity, 2),
                      "bot": bot_ret, "spy": spy_ret})
    t["days"].sort(key=lambda d: d["date"])
    finished = today >= t["end"]
    t["finished"] = finished
    TRIAL.write_text(json.dumps(t, indent=1))
    vault.write_trial(t)


def maybe_start_new_trial(cfg, today, equity, s, state):
    """When `mode` changes (e.g. paper -> alpaca-paper), archive the old account's
    history and start a new 30-day trial on the new account's real balance."""
    if not TRIAL.exists():
        return
    t = json.loads(TRIAL.read_text())
    if t.get("settings", {}).get("mode", "paper") == cfg["mode"]:
        return
    arch = STATE / f"archive-{t.get('settings', {}).get('mode', 'paper')}-until-{today}"
    arch.mkdir(parents=True, exist_ok=True)
    for f in ("trial.json", "equity.csv", "runs.json"):
        if (STATE / f).exists():
            (STATE / f).replace(arch / f)
    state.clear()
    state.update({"runs": [], "last_signal": None, "halted": False, "start_capital": equity})
    from datetime import date as _d, timedelta
    TRIAL.write_text(json.dumps({
        "start": today, "end": (_d.fromisoformat(today) + timedelta(days=30)).isoformat(),
        "start_equity": equity, "spy_start_level": s.levels["US"][-1], "spy_start_date": s.dates[-1],
        "settings": {k: cfg[k] for k in ("strategy", "worst_month_loss", "max_single_asset",
                                         "max_drawdown_halt", "region", "mode")},
        "vol_cap": cfg["vol_cap"], "days": []}, indent=1))
    print(f"New account mode {cfg['mode']}: started a fresh trial with {equity:,.2f}")


def cmd_start_trial(args):
    """Fresh paper account, riskier settings already in '02 - Risk Limits', first trade today."""
    cfg = cfgmod.load()
    if cfg["mode"] != "paper":
        print("Trials run in paper mode only."); return 1
    today = args.today or date.today().isoformat()
    arch = STATE / f"archive-before-trial-{today}"
    arch.mkdir(parents=True, exist_ok=True)
    for f in ("paper_account.json", "runs.json", "equity.csv", "trial.json"):
        if (STATE / f).exists():
            (STATE / f).replace(arch / f)
    s = data.build_series()
    from datetime import date as _d, timedelta
    end = (_d.fromisoformat(today) + timedelta(days=args.days)).isoformat()
    TRIAL.write_text(json.dumps({"start": today, "end": end, "start_equity": cfg["capital"],
                                 "spy_start_level": s.levels["US"][-1], "spy_start_date": s.dates[-1],
                                 "settings": {k: cfg[k] for k in ("strategy", "worst_month_loss", "max_single_asset",
                                                                  "max_drawdown_halt", "region", "mode")},
                                 "vol_cap": cfg["vol_cap"], "days": []}, indent=1))
    print(f"Trial {today} -> {end} with {cfg['capital']:,.0f} paper. Previous account archived in {arch.name}/")
    args.no_download = getattr(args, "no_download", False)
    args.dry_run = False
    return cmd_daily(args)


def broker_has_positions(values):
    return any(v > 1 for a, v in values.items() if a != "CASH")


def cmd_signal(args):
    cfg = cfgmod.load()
    s = data.build_series()
    strat = make_strategy(cfg)
    today = args.today or date.today().isoformat()
    sig_date, tgt, scores = current_signal(s, strat, today)
    print(f"Region {cfg['region']}  Strategy {cfg['strategy']}  vol cap {cfg['vol_cap']:.1%}  data through {s.dates[-1]}")
    print(f"Signal date (month-end close): {sig_date}")
    if scores:
        cash = scores.get("CASH")
        for a, v in sorted(scores.items(), key=lambda kv: -kv[1]):
            print(f"  {a:<10} score {v:+7.2%} {'' if a == 'CASH' else ('beats T-bills' if v > cash else '')}")
    tgt, notes = risk.clamp_weights(tgt, cfg["max_single_asset"])
    print("Target:")
    for a, w in sorted(tgt.items(), key=lambda kv: -kv[1]):
        if w > 0.0005:
            ins = cfg["instruments"][a]
            print(f"  {w:6.1%}  {a:<10} -> {ins['symbol']:<5} {ins['isin'] or 'US-listed':<13} {ins['name']}")
    for n in notes:
        print("  note:", n)
    return 0


def cmd_backtest(args):
    cfg = cfgmod.load()
    s = data.build_series()
    print(f"Evaluating 1997-{s.dates[-1]} ... (about a minute)")
    res = research.evaluate(s, cfg["vol_cap"], cfg["cost_bps"], cfg["no_trade_band"],
                            bootstrap_sims=args.sims, max_weight=cfg["max_single_asset"],
                            us_rates=(cfg["us_short_term_rate"], cfg["us_long_term_rate"]))
    res.pop("runs", None)
    vault.write_backtest_report(res, cfg)
    (HERE / "state").mkdir(exist_ok=True)
    (HERE / "state" / "backtest_results.json").write_text(json.dumps(res, indent=1, default=str))
    for k, m in res["strategies"].items():
        print(f"  {k:<10} {m['cagr']:6.2%}/yr (IRA)  US taxable {m['after_tax_us_cagr']:6.2%}  "
              f"Italy {m['after_tax_cagr']:6.2%}  worst fall {m['max_dd']:7.2%}")
    print("Wrote 03 - Backtest Report.md")
    return 0


def cmd_update(args):
    data.update_history()
    print("problems:", data.sanity_check(data.load_history()) or "none")
    return 0


def cmd_status(args):
    cfg = cfgmod.load()
    s = data.build_series()
    prices = latest_prices(s)
    b = PaperBroker(cfg["capital"], cfg["cost_bps"])
    v = b.values(prices)
    eq = sum(v.values())
    print(f"Mode {cfg['mode']}  data through {s.dates[-1]}  equity {eq:,.2f}")
    for a, x in sorted(v.items(), key=lambda kv: -kv[1]):
        print(f"  {a:<10} {x:>12,.2f}  {x / eq:6.1%}")
    hist = equity_history()
    if hist:
        peak, dd, _ = risk.drawdown_status(hist, cfg["max_drawdown_halt"])
        print(f"Peak {peak:,.2f}  drawdown {dd:.2%}  halted={load_state().get('halted')}")
    return 0


def cmd_resume(args):
    st_ = load_state()
    st_["halted"] = False
    hist = equity_history()
    st_["halt_baseline_date"] = hist[-1][0] if hist else date.today().isoformat()
    save_state(st_)
    print(f"Halt cleared. Drawdown is now measured from {st_['halt_baseline_date']}; "
          "the bot halts again only on a fresh fall of the same size.")
    return 0


def cmd_test(args):
    import unittest
    suite = unittest.defaultTestLoader.discover(str(HERE / "tests"))
    r = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if r.wasSuccessful() else 1


def cmd_daytrade_live(args):
    from bot import daytrade_live as dl
    if args.check:
        dl.check(); return 0
    active = dl.run(args.until, args.flatten, gate=args.gate)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"active={'1' if active else '0'}\n")
    if args.report:
        dl.report()
    return 0


def cmd_daytrade_month(args):
    from datetime import timedelta
    from bot import daytrade_live as dl, daytrade_month as dm
    api = dl.Alpaca()
    end = args.end or (date.today() - timedelta(days=1)).isoformat()
    start = args.start or (date.fromisoformat(end) - timedelta(days=30)).isoformat()
    st = dm.simulate(lambda m, p, b=None: api.call(m, p, b, data=True), start, end, args.capital)
    dm.write_note(st, date.today().isoformat())
    print(f"month simulation {start} -> {end}: {len(st['trades'])} trades, equity ${st['equity']:,.2f}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("daily")
    d.add_argument("--no-download", action="store_true")
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--today", help="pretend today is YYYY-MM-DD (testing)")
    sg = sub.add_parser("signal")
    sg.add_argument("--today")
    b = sub.add_parser("backtest")
    b.add_argument("--sims", type=int, default=2000)
    sub.add_parser("update-data")
    sub.add_parser("status")
    sub.add_parser("resume")
    sub.add_parser("notes")
    tr = sub.add_parser("start-trial")
    tr.add_argument("--days", type=int, default=30)
    tr.add_argument("--today")
    tr.add_argument("--no-download", action="store_true")
    sub.add_parser("test")
    dl = sub.add_parser("daytrade-live", help="run the live (paper) opening-range day-trader")
    dl.add_argument("--until", default="15:57"); dl.add_argument("--flatten"); dl.add_argument("--gate", action="store_true")
    dl.add_argument("--report", action="store_true"); dl.add_argument("--check", action="store_true")
    dm = sub.add_parser("daytrade-month", help="simulate one month of the live day-trader on real 5-minute bars")
    dm.add_argument("--start"); dm.add_argument("--end"); dm.add_argument("--capital", type=float, default=100000.0)
    args = ap.parse_args()
    fn = {"daily": cmd_daily, "signal": cmd_signal, "backtest": cmd_backtest, "update-data": cmd_update,
          "status": cmd_status, "resume": cmd_resume, "test": cmd_test,
          "start-trial": cmd_start_trial, "notes": cmd_notes, "daytrade-live": cmd_daytrade_live, "daytrade-month": cmd_daytrade_month}[args.cmd]
    try:
        return fn(args)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
