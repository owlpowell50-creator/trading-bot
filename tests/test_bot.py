"""Self-tests: python3 run.py test   (or python3 -m unittest discover tests)"""
from __future__ import annotations

import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from bot import backtest as bt          # noqa: E402
from bot import config, data, risk     # noqa: E402
from bot import strategies as st        # noqa: E402
from bot.broker import PaperBroker      # noqa: E402

SERIES = data.build_series()


def truncated(s: data.Series, end: str) -> data.Series:
    k = max(i for i, d in enumerate(s.dates) if d <= end) + 1
    return data.Series(s.dates[:k], {a: v[:k] for a, v in s.levels.items()},
                       {a: min(i, k) for a, i in s.first_valid.items()})


class NoLookAhead(unittest.TestCase):
    def test_signal_identical_with_future_removed(self):
        """The target on a past month-end must not change when every later bar is deleted."""
        for cut in ("2001-06-29", "2008-09-30", "2020-03-31", "2022-06-30"):
            short = truncated(SERIES, cut)
            for strat in (st.Core(), st.GEM(), st.Trend(), st.SpyTrend()):
                full_me = st.MonthEnds(SERIES)
                short_me = st.MonthEnds(short, today="2099-01-01")
                i = SERIES.idx[cut]
                a = strat.target(SERIES, full_me, i)
                b = strat.target(short, short_me, i)
                self.assertEqual(a.keys() if a else None, b.keys() if b else None, (cut, strat.name))
                for k in (a or {}):
                    self.assertAlmostEqual(a[k], b[k], places=12, msg=(cut, strat.name, k))

    def test_trades_happen_after_signal_day(self):
        r = bt.run(SERIES, st.Core(), start="2005-01-01", end="2007-01-01")
        me = set(SERIES.dates[i] for i in st.month_end_indices(SERIES))
        for d, _ in r.weights_log:
            self.assertNotIn(d, me, "a trade was filled on the signal day itself")


class Costs(unittest.TestCase):
    def test_costs_are_charged(self):
        """The bug in the old engine: 0, 10 and 500 bps gave identical results."""
        a = bt.run(SERIES, st.Core(), start="2005-01-01", cost_bps=0).equity[-1]
        b = bt.run(SERIES, st.Core(), start="2005-01-01", cost_bps=10).equity[-1]
        c = bt.run(SERIES, st.Core(), start="2005-01-01", cost_bps=500).equity[-1]
        self.assertGreater(a, b)
        self.assertGreater(b, c)

    def test_buy_and_hold_pays_almost_nothing(self):
        r = bt.run(SERIES, st.BuyHold({"US": 1.0}, "SPY"), start="2005-01-01")
        self.assertLessEqual(r.costs_paid, 0.0021)  # only the first purchase


class Tax(unittest.TestCase):
    def test_buy_and_hold_defers_tax(self):
        tx = bt.ItalianTax()
        r = bt.run(SERIES, st.BuyHold({"US": 1.0}, "SPY"), start="2005-01-01", tax=tx)
        self.assertAlmostEqual(tx.paid, 0.0, places=6)
        self.assertGreater(r.liquidation_tax, 0)

    def test_etf_losses_do_not_offset_etf_gains(self):
        tx = bt.ItalianTax()
        tx.basis = {"US": 100.0, "INTL": 100.0}
        self.assertEqual(tx.realise("INTL", 100.0, 0.0, 2020), 0.0)      # sell at cost: nothing
        tx.basis["INTL"] = 150.0
        tx.realise("INTL", 100.0, 0.0, 2020)                               # 50 loss banked
        owed = tx.realise("US", 200.0, 0.0, 2020)                          # 100 ETF gain
        self.assertAlmostEqual(owed, 26.0)                                 # loss NOT used
        tx.basis["GOLD"] = 100.0
        owed_gold = tx.realise("GOLD", 160.0, 0.0, 2021)                   # 60 ETC gain, 50 banked
        self.assertAlmostEqual(owed_gold, 0.26 * 10)


class USTaxRules(unittest.TestCase):
    def test_short_vs_long_term(self):
        t = bt.USTax(st_rate=0.30, lt_rate=0.15)
        t.buy("US", 100.0, 1.0, "2020-01-02")
        t.sell("US", 50.0, 1.2, "2020-06-01")       # held 5 months: short-term
        self.assertAlmostEqual(t.year_st, 50.0 - 50.0 / 1.2, places=9)
        self.assertAlmostEqual(t.year_end(), 0.30 * (50.0 - 50.0 / 1.2), places=9)
        t.sell("US", 60.0, 1.2, "2021-06-01")       # held 17 months: long-term
        self.assertEqual(t.year_st, 0.0)
        self.assertAlmostEqual(t.year_end(), 0.15 * (60.0 - 50.0), places=9)

    def test_losses_offset_and_carry_forward(self):
        t = bt.USTax(0.30, 0.15)
        t.buy("US", 100.0, 1.0, "2020-01-02")
        t.sell("US", 80.0, 0.8, "2020-03-01")       # -20 short-term loss
        self.assertEqual(t.year_end(), 0.0)
        self.assertAlmostEqual(t.carry, 20.0)
        t.buy("BONDS", 100.0, 1.0, "2021-01-04")
        t.sell("BONDS", 130.0, 1.3, "2021-03-01")   # +30 short-term gain, 20 offset by carry
        self.assertAlmostEqual(t.year_end(), 0.30 * 10.0)

    def test_buy_and_hold_pays_only_dividend_tax(self):
        tx = bt.USTax()
        r = bt.run(SERIES, st.BuyHold({"US": 1.0}, "SPY"), start="2010-01-01", end="2015-01-01", tax=tx)
        self.assertGreater(r.tax_paid, 0)                            # dividends taxed yearly
        self.assertLess(r.tax_paid, 0.01 * len(r.equity) / 252 * 3)  # but small (< ~1%/yr)
        self.assertGreater(r.liquidation_tax, 0)                     # the big bill comes at the end


class AlpacaSafety(unittest.TestCase):
    def _broker(self, positions, cash=1000.0):
        from bot.broker import AlpacaBroker
        sent = []

        def http(method, path, body=None):
            if path == "/v2/positions":
                return [{"symbol": k, "qty": str(q), "market_value": str(v)} for k, (q, v) in positions.items()]
            if path == "/v2/account":
                return {"cash": str(cash)}
            if path == "/v2/clock":
                return {"is_open": True}
            if method == "POST":
                sent.append(body)
                return {"id": f"o{len(sent)}"}
            return {"status": "filled", "filled_qty": "1", "filled_avg_price": "100"}
        cfg = dict(config.DEFAULTS, mode="alpaca-paper")
        return AlpacaBroker(cfg, config.US_INSTRUMENTS, http=http), sent

    def test_never_sells_more_than_held(self):
        b, sent = self._broker({"VOO": (2.0, 1000.0)})
        b.execute([{"asset": "US", "side": "SELL", "value": 5000.0}], "2026-12-01")
        self.assertEqual(float(sent[0]["qty"]), 2.0)                  # capped at holding: no short
        b, sent = self._broker({})
        b.execute([{"asset": "LONGBONDS", "side": "SELL", "value": 100.0}], "2026-12-01")
        self.assertEqual(sent, [])                                   # nothing held -> nothing sent

    def test_values_map_symbols(self):
        b, _ = self._broker({"VOO": (2.0, 1000.0), "SGOV": (5.0, 500.0), "AAPL": (1, 200.0)}, cash=300.0)
        v = b.values()
        self.assertEqual(v["US"], 1000.0)
        self.assertEqual(v["CASH"], 800.0)                           # SGOV + plain cash
        self.assertNotIn("AAPL", v)

    def test_live_requires_confirmation(self):
        from bot.broker import AlpacaBroker
        cfg = dict(config.DEFAULTS, mode="alpaca-live", live_trading_confirmed=False)
        with self.assertRaises(RuntimeError):
            AlpacaBroker(cfg, config.US_INSTRUMENTS, http=lambda *a, **k: {})


class RiskRules(unittest.TestCase):
    def test_vol_cap_matches_risk_note(self):
        self.assertAlmostEqual(config.vol_cap(0.08), 0.08 / 2.326 * math.sqrt(12))
        self.assertAlmostEqual(round(config.vol_cap(0.08), 3), 0.119)

    def test_clamp_no_leverage_and_cap(self):
        w, notes = risk.clamp_weights({"US": 0.9, "BONDS": 0.5}, 0.6)
        self.assertLessEqual(sum(w.values()), 1.0 + 1e-9)
        self.assertLessEqual(w["US"], 0.6 + 1e-9)
        self.assertTrue(notes)

    def test_core_never_levered_and_capped(self):
        me = st.MonthEnds(SERIES)
        c = st.Core()
        for i in me.me[150:]:
            t = c.target(SERIES, me, i)
            if t:
                self.assertLessEqual(sum(t.values()), 1.0 + 1e-9)
                self.assertTrue(all(x <= 0.6 + 1e-9 for a, x in t.items() if a != "CASH"))

    def test_pre_trade_blocks(self):
        vals = {"US": 5000.0, "CASH": 5000.0}
        self.assertTrue(risk.pre_trade_checks([{"asset": "BTC", "side": "BUY", "value": 100}], vals, 10000, ["US", "CASH"]))
        self.assertTrue(risk.pre_trade_checks([{"asset": "US", "side": "SELL", "value": 9000}], vals, 10000, ["US", "CASH"]))
        self.assertTrue(risk.pre_trade_checks([{"asset": "US", "side": "BUY", "value": 9000}], vals, 10000, ["US", "CASH"]))
        self.assertFalse(risk.pre_trade_checks([{"asset": "US", "side": "BUY", "value": 4000}], vals, 10000, ["US", "CASH"]))

    def test_sells_before_buys(self):
        _, orders, _ = risk.plan_orders({"US": 6000, "CASH": 4000}, {"BONDS": 0.6, "CASH": 0.4}, 10000, 0.0, 50)
        sides = [o["side"] for o in orders]
        self.assertEqual(sides, sorted(sides, key=lambda x: 0 if x == "SELL" else 1))

    def test_drawdown_halt(self):
        _, dd, halt = risk.drawdown_status([("a", 100), ("b", 120), ("c", 85)], 0.25)
        self.assertAlmostEqual(dd, 85 / 120 - 1)
        self.assertTrue(halt)


class PaperAccount(unittest.TestCase):
    def test_round_trip_costs(self):
        tmp = Path(tempfile.mkdtemp()) / "acct.json"
        b = PaperBroker(10000, 10, tmp)
        prices = {"US": 100.0, "CASH": 1.0}
        b.execute([{"asset": "US", "side": "BUY", "value": 5000}], prices, "2026-01-01")
        self.assertAlmostEqual(b.equity(prices), 10000 - 5.0, places=6)
        b.execute([{"asset": "US", "side": "SELL", "value": 99999}], prices, "2026-01-02")
        self.assertNotIn("US", b.acct["units"])                      # cannot sell more than held
        self.assertLess(b.equity(prices), 10000)
        shutil.rmtree(tmp.parent)


class DataQuality(unittest.TestCase):
    def test_splices_have_no_jumps(self):
        for a in SERIES.assets:
            lv = SERIES.levels[a]
            for i in range(SERIES.first_valid[a] + 1, len(lv)):
                if lv[i] and lv[i - 1]:
                    self.assertLess(abs(lv[i] / lv[i - 1] - 1), 0.25, (a, SERIES.dates[i]))

    def test_known_2008_returns(self):
        y0, y1 = SERIES.idx["2007-12-31"], SERIES.idx["2008-12-31"]
        us = SERIES.levels["US"][y1] / SERIES.levels["US"][y0] - 1
        self.assertAlmostEqual(us, -0.368, delta=0.01)     # SPY total return 2008


class Config(unittest.TestCase):
    def test_frontmatter(self):
        tmp = Path(tempfile.mkdtemp()) / "n.md"
        tmp.write_text("---\nmode: paper   # comment\nworst_month_loss: 0.06\nlive_trading_confirmed: false\n---\n# x\n")
        c = config.load(tmp)
        self.assertEqual(c["worst_month_loss"], 0.06)
        self.assertIs(c["live_trading_confirmed"], False)
        self.assertAlmostEqual(c["vol_cap"], 0.06 / 2.326 * math.sqrt(12))
        shutil.rmtree(tmp.parent)


class LiveAndDayTrade(unittest.TestCase):
    """Real-account note and intraday simulator logic (fake broker responses)."""

    def _bars(self, path):
        from datetime import datetime, timedelta, timezone
        out, t0 = [], datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc)   # 09:30 New York
        for i, (o, h, l, c) in enumerate(path):
            out.append({"t": (t0 + timedelta(minutes=5 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "o": o, "h": h, "l": l, "c": c, "v": 1000})
        return out

    def test_orb_long_hits_target(self):
        from bot import daytrade as dt
        path = [(100, 101, 99, 100)] * 3                      # range 99-101
        path += [(100.5, 101.5, 100.4, 101.2)]                # 09:45 closes above 101 -> signal
        path += [(101.3, 101.6, 101.1, 101.5)]                # entry at 101.3 open
        path += [(101.5, 104.5, 101.4, 104.2)]                # target 101.31+3 = 104.31 hit
        path += [(104, 104.1, 103.9, 104)] * 70
        days = dt.session_bars(self._bars(path))
        bars = list(days.values())[0]
        tr = dt.simulate_day("SPY", bars, 25000, 1.0)
        self.assertEqual(tr["side"], "LONG")
        self.assertEqual(tr["reason"], "Target")
        self.assertAlmostEqual(tr["entry"], 101.3 * 1.0001, places=3)
        self.assertGreater(tr["pnl"], 0)
        self.assertLessEqual(tr["shares"] * tr["entry"], 25000 * 0.2 + 1e-6)   # 20% position cap

    def test_orb_same_bar_assumes_stop(self):
        from bot import daytrade as dt
        path = [(100, 101, 99, 100)] * 3 + [(100.5, 101.5, 100.4, 101.2), (101.3, 105, 98.5, 100)]
        path += [(100, 100.1, 99.9, 100)] * 70
        bars = list(dt.session_bars(self._bars(path)).values())[0]
        tr = dt.simulate_day("SPY", bars, 25000, 1.0)
        self.assertEqual(tr["reason"], "Stop")
        self.assertLess(tr["pnl"], 0)

    def test_orb_no_breakout_no_trade(self):
        from bot import daytrade as dt
        path = [(100, 101, 99, 100)] * 78
        bars = list(dt.session_bars(self._bars(path)).values())[0]
        self.assertIsNone(dt.simulate_day("SPY", bars, 25000, 1.0))

    def test_realized_pnl_fifo(self):
        from bot import live
        orders = [{"symbol": "VOO", "side": "buy", "filled_qty": "10", "filled_avg_price": "100", "filled_at": "1"},
                  {"symbol": "VOO", "side": "buy", "filled_qty": "10", "filled_avg_price": "110", "filled_at": "2"},
                  {"symbol": "VOO", "side": "sell", "filled_qty": "15", "filled_avg_price": "120", "filled_at": "3"}]
        self.assertAlmostEqual(live.realized_pnl(orders)["VOO"], 10 * 20 + 5 * 10)


class LiveDayTrader(unittest.TestCase):
    def _bars(self, path):
        hms = [f"{9 + (30 + 5 * i) // 60:02d}:{(30 + 5 * i) % 60:02d}" for i in range(len(path))]
        return [{"hm": h, "o": o, "h": hi, "l": lo, "c": c} for h, (o, hi, lo, c) in zip(hms, path)]

    def test_plan_long_on_fresh_breakout(self):
        from bot.daytrade_live import plan
        p = plan(self._bars([(100, 101, 99, 100)] * 3 + [(100.5, 101.6, 100.4, 101.4)]), 25000)
        self.assertEqual(p["side"], "buy"); self.assertEqual(p["stop"], 99.0)
        self.assertAlmostEqual(p["target"], round(101.4 + 3.0 * 2, 2))
        self.assertLessEqual(p["qty"] * 101.4, 25000 * 2.0 + 1)

    def test_plan_skips_old_breakout(self):
        from bot.daytrade_live import plan
        p = plan(self._bars([(100, 101, 99, 100)] * 3 + [(100.5, 101.6, 100.4, 101.4), (101.4, 101.5, 101.0, 101.2)]), 25000)
        self.assertIn("skip", p)

    def test_plan_none_inside_range(self):
        from bot.daytrade_live import plan
        self.assertIsNone(plan(self._bars([(100, 101, 99, 100)] * 5), 25000))

    def test_refuses_long_term_account(self):
        from bot import daytrade_live as dl
        def fake(method, path, body=None):
            if path == "/v2/clock": return {"is_open": True, "next_open": "2099-01-01T14:30:00Z"}
            if path == "/v2/account": return {"equity": "99000", "last_equity": "99000"}
            if path == "/v2/positions": return [{"symbol": "VOO"}]
            return {}
        if True:
            with self.assertRaises(RuntimeError):
                dl.run("15:57", gate=False, log=lambda *a: None, api=dl.Alpaca(http=fake))


class SkillPack(unittest.TestCase):
    """The vendored day-trader-skill pipeline: scanner -> exit -> news -> time machine -> sizing."""

    def _data(self, news):
        import random
        from datetime import date as D, datetime as DT, timedelta as TD, timezone as TZ
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")

        def bars(d, rnd, upto=None):
            out, p = [], 100.0
            for k in range(78):
                if upto is not None and k > upto:
                    break
                t = DT(d.year, d.month, d.day, 9, 30, tzinfo=ny) + TD(minutes=5 * k)
                o = p; c = p * (1.01 if k == upto else 1 + rnd.gauss(0.0002, 0.002))
                out.append({"t": t.astimezone(TZ.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "o": o, "h": max(o, c) * 1.0005,
                            "l": min(o, c) * 0.9995, "c": c, "v": 1000}); p = c
            return out
        rnd = random.Random(1); hist = []; d = D(2026, 9, 20); n = 0
        while n < 40:
            d += TD(days=1)
            if d.weekday() < 5:
                hist += bars(d, rnd); n += 1

        class Api:
            def call(self, m, p, b=None, data=False):
                return {"news": [{"headline": news}]}
        now = DT(2026, 11, 18, 9, 55, 10, tzinfo=ny)
        return Api(), bars(D(2026, 11, 18), rnd, upto=4), hist, D(2026, 11, 18), now

    def test_breakout_passes_pipeline_and_sizes(self):
        from bot import skill_trader as sk
        api, tb, hist, day, now = self._data("Analyst upgrade")
        d = sk.evaluate(api, "XYZ", tb, hist, day, now, 100000)
        self.assertNotIn("skip", d, d)
        self.assertLess(d["stop"], d["price"]); self.assertGreater(d["target"], d["price"])
        self.assertLessEqual(d["qty"] * d["price"], 100000 * sk.RULES["max_position_x"] + 1)
        self.assertLessEqual(d["risk"], sk.RULES["risk_usd"] + 1)
        body = sk.order_body(d, day)
        self.assertEqual(body["side"], "buy"); self.assertEqual(body["order_class"], "bracket")
        self.assertTrue(body["client_order_id"].startswith("dts-20261118-XYZ-L-r"))

    def test_earnings_news_blocks_trade(self):
        from bot import skill_trader as sk
        api, tb, hist, day, now = self._data("XYZ earnings results beat estimates")
        d = sk.evaluate(api, "XYZ", tb, hist, day, now, 100000)
        self.assertIn("news", d["skip"])


class DayRiskBudget(unittest.TestCase):
    """$5,000 of risk a day across both day-trading strategies."""

    class Api:
        def __init__(self, pos, orders):
            self.pos, self.orders = pos, orders

        def call(self, m, p, b=None, data=False):
            return self.pos if p.startswith("/v2/positions") else self.orders

    def test_budget_counts_losses_and_open_stops(self):
        from bot import daytrade_live as dl
        api = self.Api([{"symbol": "SPY", "qty": "100", "current_price": "500"}],
                       [{"symbol": "SPY", "type": "market", "status": "filled",
                         "legs": [{"symbol": "SPY", "type": "stop", "stop_price": "497", "status": "held"},
                                  {"symbol": "SPY", "type": "limit", "limit_price": "505", "status": "new"}]}])
        # down $200 on the day, and the open SPY trade can still lose $300 at its stop -> $4,500 left
        self.assertAlmostEqual(dl.risk_left(api, 100000, 99800), 4500.0)
        short = self.Api([{"symbol": "QQQ", "qty": "-50", "current_price": "400"}],
                         [{"symbol": "QQQ", "type": "stop", "stop_price": "404", "status": "held"}])
        self.assertAlmostEqual(dl.risk_left(short, 100000, 100000), 4800.0)
        self.assertAlmostEqual(dl.risk_left(self.Api([], []), 100000, 95000), 0.0)

    def test_plan_is_shrunk_to_the_budget_left(self):
        from bot import daytrade_live as dl
        self.assertEqual(dl.DAY_RISK_USD, 5000.0)
        bars = [{"hm": f"09:{m:02d}", "o": 100, "h": 101, "l": 99, "c": 100} for m in (30, 35, 40)]
        bars.append({"hm": "09:45", "o": 100, "h": 102, "l": 100, "c": 101.5})
        full = dl.plan(bars, 100000)
        small = dl.plan(bars, 100000, 150)
        if full and "skip" not in full:
            self.assertLessEqual(small["risk"], 150.0 + 1e-6)
            self.assertLess(small["qty"], full["qty"])


class Brain(unittest.TestCase):
    def test_flip_moves(self):
        from bot.brain import flips
        sc = {"US": 0.10, "INTL": 0.08, "GOLD": 0.05, "REIT": 0.04, "CASH": 0.02}
        f = {x["asset"]: x for x in flips(sc)}
        self.assertEqual(f["US"]["status"], "held"); self.assertEqual(f["REIT"]["status"], "out")
        # REIT must beat GOLD's 5%: (1.05/1.04) - 1
        self.assertAlmostEqual(f["REIT"]["move"], 1.05 / 1.04 - 1, places=6)
        # GOLD drops out once it falls below REIT's 4%
        self.assertAlmostEqual(f["GOLD"]["move"], 1.04 / 1.05 - 1, places=6)


if __name__ == "__main__":
    unittest.main()


class CarriedTrades(unittest.TestCase):
    def test_overnight_trade_gets_exit_from_later_fill(self):
        from datetime import date
        from bot import daytrade_live as dl
        st = {"trades": [{"date": "2026-11-23", "symbol": "SPY", "side": "LONG", "qty": 39.0, "entry": 726.68, "entry_time": "15:25",
                          "exit": None, "exit_time": None, "pnl": 0.0, "r": 0.0, "risk": 494.0, "strategy": "ORB"}]}
        class Api:
            def call(self, m, p, b=None):
                return [{"symbol": "SPY", "side": "buy", "qty": "39", "price": "726.68", "transaction_time": "2026-11-23T15:25:01Z"},
                        {"symbol": "QQQ", "side": "sell", "qty": "35", "price": "650", "transaction_time": "2026-11-24T14:31:00Z"},
                        {"symbol": "SPY", "side": "sell", "qty": "39", "price": "720.00", "transaction_time": "2026-11-24T14:31:02Z"}]
        dl.close_old_trades(Api(), st, date(2026, 11, 24), log=lambda *a: None)
        t = st["trades"][0]
        self.assertEqual(t["exit"], 720.0); self.assertEqual(t["exit_date"], "2026-11-24")
        self.assertAlmostEqual(t["pnl"], (720.0 - 726.68) * 39, places=2); self.assertTrue(t["carried"])


class FlattenChecks(unittest.TestCase):
    def _api(self, stuck_rounds):
        state = {"pos": [{"symbol": "SPY", "qty": "84"}], "n": 0}
        class Api:
            def call(self, m, p, b=None):
                if m == "GET" and p.startswith("/v2/orders"):
                    return []
                if m == "GET" and p == "/v2/positions":
                    return list(state["pos"])
                if m == "DELETE" and p.startswith("/v2/positions"):
                    state["n"] += 1
                    if state["n"] > stuck_rounds:
                        state["pos"] = []
                return {}
        return Api()

    def test_retries_until_flat(self):
        from bot import daytrade_live as dl
        logs = []
        self.assertTrue(dl.flatten(self._api(1), logs.append, wait=0))
        self.assertTrue(any("still open" in l for l in logs))

    def test_reports_when_not_flat(self):
        from bot import daytrade_live as dl
        logs = []
        self.assertFalse(dl.flatten(self._api(99), logs.append, tries=3, wait=0))
        self.assertTrue(any("NOT FLAT" in l for l in logs))


class PairRule(unittest.TestCase):
    def bars(self, closes, hi=101.0, lo=99.0):
        hms = ["09:30", "09:35", "09:40"] + [f"{9 + (45 + 5 * i) // 60:02d}:{(45 + 5 * i) % 60:02d}" for i in range(len(closes))]
        out = [dict(hm=h, o=100, h=hi, l=lo, c=100) for h in hms[:3]]
        out += [dict(hm=h, o=c, h=c + .1, l=c - .1, c=c) for h, c in zip(hms[3:], closes)]
        return out

    def test_waits_for_confirmation_then_trades_with_trend(self):
        from bot import daytrade_live as dl
        spy = self.bars([100.5, 101.5])                  # SPY breaks up at 09:50
        qqq = self.bars([100.5, 100.6])                  # QQQ not yet
        self.assertIn("wait", dl.plan_pair({"SPY": spy, "QQQ": qqq}, "SPY", 100000, 500, {"SPY": 95, "QQQ": 95}))
        spy = self.bars([100.5, 101.5, 101.6]); qqq = self.bars([100.5, 100.6, 101.4])   # QQQ confirms at 09:55
        p = dl.plan_pair({"SPY": spy, "QQQ": qqq}, "SPY", 100000, 500, {"SPY": 95, "QQQ": 95})
        self.assertEqual(p["side"], "buy"); self.assertEqual(p["confirmed"], "09:55"); self.assertEqual(p["stop"], 99.0)
        self.assertLessEqual(p["risk"], 500)

    def test_against_trend_and_opposite_breaks_skip(self):
        from bot import daytrade_live as dl
        spy = self.bars([101.5]); qqq = self.bars([101.4])
        self.assertIn("against the 20-day trend", dl.plan_pair({"SPY": spy, "QQQ": qqq}, "SPY", 100000, 500, {"SPY": 105, "QQQ": 95})["skip"])
        qqq = self.bars([98.5])
        self.assertIn("opposite", dl.plan_pair({"SPY": spy, "QQQ": qqq}, "SPY", 100000, 500, {"SPY": 95, "QQQ": 95})["skip"])
        self.assertIn("not trading blind", dl.plan_pair({"SPY": spy, "QQQ": self.bars([101.4])}, "SPY", 100000, 500, None)["skip"])


class EdgeCheck(unittest.TestCase):
    def test_flags_a_broken_edge(self):
        from bot.brain import edge_check
        res = {"rows": [{"name": "Live rule now, target 3.0x range", "second": {"avg": 0.15}}], "years_confirmed": {}}
        dt = {"trades": [{"date": "2026-12-%02d" % (1 + k % 28), "strategy": "ORB", "exit": 1, "r": -1.0 if k % 3 else 0.5} for k in range(40)]}
        out = edge_check(dt, res)
        self.assertTrue(any(o[0] == "alert" and o[1] == "red" for o in out))

    def test_quiet_when_on_track(self):
        from bot.brain import edge_check
        res = {"rows": [{"name": "Live rule now, target 3.0x range", "second": {"avg": 0.15}}], "years_confirmed": {}}
        dt = {"trades": [{"date": "2026-12-01", "strategy": "ORB", "exit": 1, "r": r} for r in (1.0, -1.0, 2.0, -1.0, 0.2)]}
        self.assertFalse(any(o[0] == "alert" for o in edge_check(dt, res)))


class PerformanceContext(unittest.TestCase):
    def test_tracking_and_context_run_on_real_series(self):
        from bot import brain, data, config, strategies as st
        cfg = config.load(); s = data.build_series()
        strat = st.by_name(cfg["strategy"], cfg["vol_cap"], cfg["max_single_asset"])
        d = s.dates[-25:]
        curve = [(x, 100000 * s.levels["US"][s.idx[x]] / s.levels["US"][s.idx[d[0]]]) for x in d]
        t = brain.tracking_check(s, strat, curve, {"start": d[0]})
        self.assertIsNotNone(t); self.assertAlmostEqual(t["live"], curve[-1][1] / curve[0][1] - 1)
        c = brain.context_check(s, strat, cfg, curve)
        self.assertTrue(c is None or 0 <= c["rank"] <= 1)


class TailRisk(unittest.TestCase):
    def test_var_es_ordering_and_cash(self):
        from bot import brain, data
        s = data.build_series(); i = len(s.dates) - 1
        v = brain.hist_var_es(s, {"US": 1.0}, i, 21)
        self.assertGreater(v["es99"], v["var99"]); self.assertGreater(v["var99"], v["var95"]); self.assertGreater(v["var95"], 0)
        c = brain.hist_var_es(s, {"CASH": 1.0}, i, 21)
        self.assertLess(c["var95"], 0.005)            # cash almost never loses money over a month
        rc = brain.risk_contrib(s, {"US": 0.5, "BONDS": 0.5}, i)
        self.assertAlmostEqual(sum(rc.values()), 1.0, places=6)
