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
        self.assertAlmostEqual(p["target"], round(101.4 + 1.5 * 2, 2))
        self.assertLessEqual(p["qty"] * 101.4, 25000 * 0.2)

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


if __name__ == "__main__":
    unittest.main()
