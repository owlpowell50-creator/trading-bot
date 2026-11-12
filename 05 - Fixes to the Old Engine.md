---
type: audit
department: risk
department_color: "#EF4444"
cssclasses:
  - dept-risk
tags:
  - type/audit
  - department/risk
  - trading-bot
  - model-risk
---
# 05 - Fixes to the Old Engine (2026-11-12)

The research engine in `Company/_build/` had bugs that made its trading results look far better than they were. Here's what was wrong, what changed, and the proof. The original files are saved in `Company/_build/_backup_before_fix_2026-11-12/`.

## 1. Trading costs were never charged — `portfolio_backtest.py`

**Bug:** costs were subtracted from cash and then cash was recalculated from scratch three lines later, so the subtraction vanished.
**Proof:** the same strategy returned **+156.15% at 0, 10 and 500 bps.**
**Fix:** costs now come out of the portfolio before new positions are sized.
**After the fix:** 0 bps → **+147.5%**, 500 bps → **−37.7%**. The lower zero-cost number reflects fix 2.

## 2. Same-day execution — `portfolio_backtest.py`, `strategy_lab.py`

**Bug:** signals from day *t*'s close were traded at that same close, which you can't do in real life.
**Fix:** a one-day delay. The signal at *t*'s close is traded at *t+1*'s close.

## 3. All 24 "strategies" were one strategy — `portfolio_backtest.py`

**Bug:** each strategy's signal was used only as a filter, and then every strategy picked the top 20 by the same 63-day momentum. That's why several showed an identical −33.79% drawdown.
**Fix:** each strategy now holds every stock its *own* rule selects. The old behaviour is still available with `--rank momentum`.

## 4. Missing prices made holdings vanish — `portfolio_backtest.py`

**Bug:** a holding with no price that day dropped out of portfolio value, creating fake losses and gains.
**Fix:** it's carried at its last known price.

## 5. "Supported" meant "made any money in a rising market" — `strategy_lab.py`

**Bug:**
- A strategy was labelled *supported* if it was positive over the last 30% of a 2-year bull market. It was never compared with simply holding the stock.
- Short signals were taken with no borrowing cost.
- "In-sample/out-of-sample" was a mislabel, since no parameters are fitted.

**Fix:**
- *Supported* now requires beating buy-and-hold of the same stock after costs, in the out-of-sample window and in most walk-forward folds.
- Strategies are long-only by default.
- The split is labelled honestly.

**Re-run on 100 stocks:**

| | Before | After |
|---|---|---|
| Best strategy "supported" on | 41 / 100 (rsi-reversion) | 10 / 100 (dual-ma-fast) |
| Typical rejection rate | ~50% | **80–98%** |

24 strategies × 100 stocks is 2,400 tries, so a few percent passing is about what luck alone produces. **No single-stock timing rule here shows a real edge yet.** That's why the bot trades asset classes instead. New results are in `Company/audit-reports/strategy-lab.json`; the old file is kept as `strategy-lab.PRE-FIX-2026-11-04.json`.

## 6. Prices weren't dividend-adjusted — `price_loader.py`, `market_data.py`

**Bug:** the loader downloaded adjusted closes and threw them away. Splits were fine (Yahoo's close is split-adjusted), but dividends were missing.
**Fix:** a new `adjclose` column; the engines use it when it's present.
**To fill it, run once on the Mac:**

```bash
cd ~/Desktop/"Trading bot"/"trading bot"/Company/_build
python3 price_loader.py --vault ../.. load --from-warehouse --limit 2000 --allow-unofficial --reload
```

## 7. Paper fills were typed in by hand — `order_management.py`

**Bug:** `simulate --fill-price` accepted any number. ORD0001, a $190 limit buy, "filled" at $189.50 while NVDA traded around $204.
**Fix:** fills now come from the latest real bar. A limit order fills only if the bar actually reached the limit, and a typed price outside the day's high–low range is refused.
**Replay of ORD0001:** "not-filled (limit 190.0 never reached; low 200.94)".

## 8. Results that are now invalid

- `Company/audit-reports/strategy-scorecard.json` is marked `INVALIDATED`. It came from the cost-free engine. Re-run `strategy_scorecard.py` (about a minute per strategy) or use [[03 - Backtest Report]].
- The NVDA fill in `Company/_registry/orders.json` (ORD0001) and the "Semis Fund" paper P&L used hand-typed or stale prices. Treat them as examples, not performance.

## Database note

While adding the `adjclose` column, a write from the sync sandbox left a rollback journal. It was rolled back on a copy, integrity-checked (`quick_check: ok`, 520,127 price rows intact), and put back. A copy from before the change is in `Company/_registry/backups/before-adjclose-2026-11-12/`.

## What's still true about the old engine

- **Survivorship bias:** the stock universe is today's listed companies only. This can't be fixed without data that includes delisted stocks (e.g. Norgate).
- **Two years of prices** for individual stocks isn't enough to judge a strategy. The bot uses 1986–2026 asset-class data instead.

Related: [[07 - Model Risk and Assumption Failure]] · [[10 - Postmortems and Lessons]] · [[Guide - Backtesting]]
