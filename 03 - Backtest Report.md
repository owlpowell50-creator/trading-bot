---
type: backtest-report
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-12
tags:
  - type/backtest-report
  - department/trading
  - trading-bot
  - backtest
---

# Backtest Report — 1997 to today, every crash included

Period **1997-06-01 → 2026-11-11** · costs **10 bps** per unit traded · signal at month-end close, filled at the **next day's** close · vol cap **22.3%** (from a 15% worst month, see [[08 - Risk Limits and Escalation]]) · max **80%** in one asset · no-trade band **10%**.

Before an ETF existed its Vanguard mutual-fund twin is used (VFINX→SPY, VGTSX→EFA, VFITX→IEF, VUSTX→TLT, VGSIX→VNQ); cash earns the 3-month T-bill rate. Dividends are reinvested in every series.

## The short version

> [!summary] What the evidence says
> - **CORE made 10.1%/yr** vs **9.6%/yr** for the S&P 500 and 7.9%/yr for 60/40 — about the same return as stocks, with **half the volatility**.
> - **Worst fall: -17.6%** vs **-55.2%** for the S&P 500 (and -32.1% for 60/40). That is the whole point of the bot.
> - **Taxes decide where to run it.** In an **IRA / Roth IRA** (no tax on trades) CORE keeps **10.1%/yr** vs 9.6%/yr for the S&P 500. In a normal **taxable** account (short-term gains and interest at 29%, long-term and dividends at 20%) it drops to **7.2%/yr** while buy-and-hold S&P keeps **8.6%/yr**, because the bot's gains are mostly short-term and its bond income is taxed every year.
> - **Honest forward estimate:** re-choosing the settings each year using only past data (walk-forward) gave **8.2%/yr** with a **-13.8%** worst fall. Across 36 nearby settings the median was 8.7%/yr. Expect something in that range, not the best number above.
> - **Luck test:** in 85% of 2,000 reshuffled histories CORE beat 60/40; vs the S&P 500 it was a coin flip (54%). The edge is in **risk**, not in raw return.

## Head to head

| | CORE | GEM | TREND | SPY-TREND | 60/40 | SPY |
|---|---|---|---|---|---|---|
| Return per year (= in an IRA / Roth IRA) | 10.1% | 9.6% | 6.3% | 9.6% | 7.9% | 9.6% |
| After tax, US taxable account | 7.2% | 7.0% | 4.5% | 6.8% | 6.4% | 8.6% |
| After tax, Italy | 7.6% | 7.0% | 4.4% | 6.9% | 6.6% | 8.6% |
| Volatility | 10.5% | 15.6% | 7.7% | 13.7% | 11.0% | 19.4% |
| Sharpe (vs T-bills) | 0.77 | 0.53 | 0.56 | 0.58 | 0.55 | 0.46 |
| Worst fall (max drawdown) | -17.6% | -33.7% | -14.6% | -31.5% | -32.1% | -55.2% |
| Worst calendar year | -12.2% | -16.7% | -5.8% | -28.4% | -17.6% | -36.8% |
| Best calendar year | +27.5% | +28.7% | +22.5% | +32.3% | +21.9% | +32.3% |
| Worst month | -6.8% | -14.1% | -7.1% | -14.1% | -10.3% | -16.5% |
| Months up | 63.1% | 62.3% | 65.9% | 65.4% | 64.8% | 63.4% |
| Longest time below a previous peak (days) | 1,073 | 884 | 1,109 | 1,001 | 1,224 | 2,407 |
| $1 grew to | $16.79 | $14.65 | $6.02 | $14.66 | $9.38 | $14.83 |
| Trades per year | 5.6 | 1.5 | 8.2 | 1.5 | 5.6 | 0.0 |
| Cost drag per year | 0.46% | 0.30% | 0.33% | 0.29% | 0.03% | 0.01% |

Strategies: **CORE** — Top-3 diversified momentum (avg 3/6/12m), must beat T-bills, inverse-vol weights, scaled to the vol cap, never levered; **GEM** — Dual momentum: best of US/ex-US if US beats T-bills over the lookback, else Treasuries; **TREND** — Equal slices of 5 asset classes, each held only above its 10-month average; **SPY-TREND** — S&P 500 while it is above its 10-month average, otherwise Treasuries (Faber 2007 / Zweig); **60/40** — 60% US / 40% BONDS; **SPY** — 100% US

## The downs — every crash

| Crash | Dates | CORE | GEM | TREND | SPY-TREND | 60/40 | SPY |
|---|---|---|---|---|---|---|---|
| Asia / LTCM 1998 | 1998-07-17 → 1998-10-08 | +2.6% | -18.2% | -6.5% | -13.5% | -9.0% | -18.2% |
| Dot-com bust 2000-02 | 2000-03-24 → 2002-10-09 | +26.1% | +13.2% | +9.9% | +13.1% | -21.3% | -47.5% |
| Financial crisis 2007-09 | 2007-10-09 → 2009-03-09 | +24.7% | -2.1% | -2.9% | +4.9% | -32.1% | -55.2% |
| Euro debt crisis 2011 | 2011-04-29 → 2011-10-03 | -6.8% | -21.0% | -8.9% | -9.0% | -6.6% | -18.6% |
| China / oil 2015-16 | 2015-05-21 → 2016-02-11 | -8.4% | -15.1% | -8.8% | -14.7% | -5.4% | -13.0% |
| Q4 2018 sell-off | 2018-09-20 → 2018-12-24 | -13.3% | -19.3% | -6.7% | -20.2% | -10.5% | -19.3% |
| COVID crash 2020 | 2020-02-19 → 2020-03-23 | +0.7% | -33.7% | -3.8% | -6.1% | -18.6% | -33.7% |
| Inflation bear 2022 | 2022-01-03 → 2022-10-12 | -6.6% | -18.2% | -4.7% | -27.2% | -20.6% | -24.5% |
| Tariff crash 2025 | 2025-02-19 → 2025-04-08 | -7.6% | -18.8% | -6.4% | -8.8% | -10.5% | -18.8% |

> [!warning] Where CORE is weak
> Fast sell-offs that start and finish between two month-ends (Q4 2018, April 2025) hit it before the month-end signal can react. Its protection comes from *slow* bear markets (2000-02, 2008, 2022).

## The ups — every rally

| Rally | Dates | CORE | GEM | TREND | SPY-TREND | 60/40 | SPY |
|---|---|---|---|---|---|---|---|
| Dot-com mania 1997-2000 | 1997-06-02 → 2000-03-24 | +46.5% | +81.9% | +28.6% | +61.9% | +56.8% | +88.1% |
| Recovery 2002-07 | 2002-10-09 → 2007-10-09 | +82.3% | +131.2% | +93.1% | +80.8% | +73.9% | +119.0% |
| Post-crisis bull 2009-20 | 2009-03-09 → 2020-02-19 | +74.2% | +93.0% | +48.4% | +141.7% | +271.4% | +520.8% |
| COVID rebound 2020-21 | 2020-03-23 → 2022-01-03 | +36.6% | +76.7% | +31.4% | +62.3% | +58.1% | +119.9% |
| AI bull 2022-26 | 2022-10-12 → 2026-12-31 | +78.7% | +70.4% | +27.2% | +57.6% | +70.0% | +124.4% |

CORE gives up a lot in roaring bull markets (2009-2020 especially): it holds bonds, gold and cash alongside stocks. That is the price of the crash protection.

## Year by year

| Year | CORE | GEM | TREND | SPY-TREND | 60/40 | SPY |
|---|---|---|---|---|---|---|
| 1997 | +12.8% | +15.6% | +8.9% | +15.6% | +12.3% | +15.6% |
| 1998 | +11.6% | +28.7% | +5.2% | +16.9% | +21.9% | +28.7% |
| 1999 | +14.2% | +21.6% | +10.0% | +14.1% | +10.4% | +20.4% |
| 2000 | +8.0% | -8.1% | +6.8% | +4.0% | -0.6% | -9.7% |
| 2001 | +7.8% | +7.6% | +5.8% | +7.6% | -3.7% | -11.8% |
| 2002 | +10.1% | +14.7% | -0.7% | +5.8% | -8.1% | -21.6% |
| 2003 | +21.5% | +18.4% | +22.5% | +23.9% | +18.8% | +28.2% |
| 2004 | +13.7% | +19.0% | +13.3% | +7.5% | +8.1% | +10.7% |
| 2005 | +1.9% | +13.3% | +9.1% | +4.8% | +4.0% | +4.8% |
| 2006 | +25.9% | +25.8% | +18.9% | +15.8% | +10.4% | +15.8% |
| 2007 | +11.8% | +10.0% | +9.8% | +5.1% | +7.4% | +5.1% |
| 2008 | +20.3% | +6.3% | -4.7% | +15.8% | -17.6% | -36.8% |
| 2009 | +1.6% | -1.2% | +12.0% | +13.5% | +13.1% | +26.4% |
| 2010 | +11.2% | +5.0% | +3.4% | -0.7% | +13.5% | +15.1% |
| 2011 | -0.3% | -1.2% | -1.0% | -0.5% | +7.9% | +1.9% |
| 2012 | +2.1% | +7.0% | -0.2% | +10.2% | +11.5% | +16.0% |
| 2013 | +13.8% | +16.0% | +6.9% | +32.3% | +15.7% | +32.3% |
| 2014 | +15.9% | +13.5% | +6.8% | +13.5% | +11.8% | +13.5% |
| 2015 | -12.2% | -8.8% | -4.5% | -8.4% | +1.7% | +1.2% |
| 2016 | +4.0% | +5.5% | +3.2% | +5.5% | +7.8% | +12.0% |
| 2017 | +13.7% | +19.1% | +8.8% | +21.7% | +13.8% | +21.7% |
| 2018 | -6.2% | -7.9% | -2.3% | -5.6% | -2.0% | -4.6% |
| 2019 | +10.1% | +16.1% | +7.1% | +7.5% | +21.9% | +31.2% |
| 2020 | +10.1% | -4.9% | +4.5% | +23.7% | +16.7% | +18.3% |
| 2021 | +27.5% | +28.7% | +21.7% | +28.7% | +15.1% | +28.7% |
| 2022 | -6.9% | -16.7% | -5.8% | -28.4% | -16.6% | -18.2% |
| 2023 | +2.5% | +7.4% | +1.6% | +15.4% | +16.7% | +26.2% |
| 2024 | +17.6% | +24.9% | +5.7% | +24.9% | +14.3% | +24.9% |
| 2025 | +24.3% | +17.2% | +9.0% | +10.0% | +14.0% | +17.7% |
| 2026 | +19.7% | +7.1% | +9.8% | +1.7% | +6.4% | +12.3% |

*(first and last years are partial)*

## Is it one lucky setting? (robustness)

36 neighbouring settings (top 2/3/4 assets × 4 lookback sets × vol cap ±25%): return per year min **7.1%**, median **8.7%**, max **10.1%**; worst fall median **-19.2%**, worst **-36.5%**.

| Top | Lookbacks (months) | Vol cap | Return/yr | Worst fall | Sharpe |
|---|---|---|---|---|---|
| 3 | 3/6/12 | 22.3% | 10.1% | -17.6% | 0.97 |
| 3 | 3/6/12 | 27.9% | 10.1% | -17.6% | 0.97 |
| 3 | 3/6/12 | 16.8% | 10.0% | -17.6% | 0.97 |
| 2 | 3/6/12 | 27.9% | 9.9% | -27.2% | 0.78 |
| 2 | 3/6/12 | 22.3% | 9.8% | -27.2% | 0.78 |
| 3 | 6/12 | 22.3% | 9.8% | -18.8% | 0.95 |
| 3 | 6/12 | 27.9% | 9.8% | -18.8% | 0.95 |
| 3 | 1/3/6 | 27.9% | 9.7% | -25.8% | 0.96 |
| 2 | 3/6/12 | 16.8% | 9.7% | -27.2% | 0.79 |
| 3 | 6/12 | 16.8% | 9.7% | -18.8% | 0.96 |
| 3 | 1/3/6 | 22.3% | 9.7% | -25.8% | 0.95 |
| 3 | 1/3/6 | 16.8% | 9.5% | -25.8% | 0.95 |
| 2 | 6/12 | 27.9% | 9.3% | -29.2% | 0.75 |
| 2 | 6/12 | 22.3% | 9.3% | -29.2% | 0.75 |
| 2 | 6/12 | 16.8% | 9.0% | -28.9% | 0.75 |
| 2 | 1/3/6 | 27.9% | 8.8% | -35.9% | 0.71 |
| 3 | 12 | 22.3% | 8.7% | -19.3% | 0.84 |
| 3 | 12 | 27.9% | 8.7% | -19.3% | 0.84 |
| 3 | 12 | 16.8% | 8.7% | -19.3% | 0.84 |
| 2 | 1/3/6 | 22.3% | 8.6% | -35.9% | 0.70 |
| 4 | 3/6/12 | 22.3% | 8.5% | -13.1% | 1.01 |
| 4 | 3/6/12 | 27.9% | 8.5% | -13.1% | 1.01 |
| 4 | 3/6/12 | 16.8% | 8.5% | -13.1% | 1.00 |
| 2 | 12 | 16.8% | 8.4% | -26.5% | 0.69 |
| 2 | 1/3/6 | 16.8% | 8.3% | -35.6% | 0.70 |
| 2 | 12 | 22.3% | 8.2% | -34.1% | 0.66 |
| 4 | 1/3/6 | 27.9% | 8.2% | -19.1% | 0.96 |
| 4 | 6/12 | 16.8% | 8.1% | -12.7% | 0.96 |
| 4 | 1/3/6 | 22.3% | 8.1% | -19.1% | 0.96 |
| 4 | 6/12 | 22.3% | 8.1% | -12.7% | 0.95 |
| 4 | 6/12 | 27.9% | 8.1% | -12.7% | 0.95 |
| 2 | 12 | 27.9% | 8.1% | -36.5% | 0.65 |
| 4 | 1/3/6 | 16.8% | 8.0% | -19.1% | 0.96 |
| 4 | 12 | 22.3% | 7.2% | -17.6% | 0.84 |
| 4 | 12 | 27.9% | 7.2% | -17.6% | 0.84 |
| 4 | 12 | 16.8% | 7.1% | -17.6% | 0.83 |

The chosen setting (top 3, 3/6/12 months) is near the top of this table. It was picked from the published research before testing, but treat the median as the realistic number.

## Walk-forward (settings chosen only from the past)

Return 8.2%/yr · worst fall -13.8% · Sharpe 0.90

Choices made each January: 1997: `CORE-top4-vol22`, 1998: `CORE-top4-vol22-lb1-3-6`, 1999: `CORE-vol22`, 2000: `CORE-vol22`, 2001: `CORE-top4-vol22-lb1-3-6`, 2002: `CORE-vol22`, 2003: `CORE-vol22`, 2004: `CORE-vol22`, 2005: `CORE-vol22-lb1-3-6`, 2006: `CORE-vol22-lb1-3-6`, 2007: `CORE-top4-vol22-lb1-3-6`, 2008: `CORE-top4-vol22-lb1-3-6`, 2009: `CORE-vol22`, 2010: `CORE-top4-vol22`, 2011: `CORE-top4-vol22`, 2012: `CORE-top4-vol22`, 2013: `CORE-top4-vol22`, 2014: `CORE-top4-vol22`, 2015: `CORE-top4-vol22`, 2016: `CORE-top4-vol22`, 2017: `CORE-top4-vol22-lb6-12`, 2018: `CORE-top4-vol22-lb6-12`, 2019: `CORE-top4-vol22-lb6-12`, 2020: `CORE-top4-vol22-lb6-12`, 2021: `CORE-top4-vol22-lb6-12`, 2022: `CORE-top4-vol22-lb6-12`, 2023: `CORE-top4-vol22-lb6-12`, 2024: `CORE-top4-vol22`, 2025: `CORE-top4-vol22`, 2026: `CORE-top4-vol22`

## Costs

| Cost per unit traded | Return/yr | Worst fall |
|---|---|---|
| 0 bps | 10.6% | -17.0% |
| 10 bps | 10.1% | -17.6% |
| 25 bps | 9.3% | -18.5% |
| 50 bps | 8.1% | -20.1% |

Real UCITS ETF spreads at IBKR are usually a few bps; 10 bps is a cautious all-in assumption. See [[11 - Is the Potential Edge Bigger Than the Costs?]].

## First half vs second half

| | 1997–2011 return | 1997–2011 worst fall | 2012–2026 return | 2012–2026 worst fall |
|---|---|---|---|---|
| CORE | 11.6% | -12.3% | 8.6% | -17.6% |
| GEM | 11.6% | -21.0% | 7.5% | -33.7% |
| TREND | 8.0% | -14.6% | 4.7% | -10.1% |
| SPY-TREND | 10.1% | -20.7% | 9.1% | -31.5% |
| 60/40 | 6.2% | -32.1% | 9.5% | -21.2% |
| SPY | 4.5% | -55.2% | 14.7% | -33.7% |

Stocks were terrible in the first half and superb in the second; CORE was steadier in both.

## What drawdown should I expect? (10-year bootstrap)

| | Typical (median) | 1-in-10 | 1-in-20 | 1-in-100 |
|---|---|---|---|---|
| CORE | -11.1% | -17.2% | -19.2% | -24.2% |
| 60/40 | -16.1% | -27.8% | -31.3% | -42.1% |
| SPY | -29.0% | -49.0% | -55.6% | -67.4% |

Resampled 12-month blocks of real history. The 1-in-100 line is what to plan for, not the median.

## In euros (what you actually experience)

| | From | Return/yr in EUR | Worst fall in EUR | Volatility |
|---|---|---|---|---|
| CORE | 2004-01-02 | 9.8% | -20.4% | 15.0% |
| SPY | 2004-01-02 | 11.4% | -51.2% | 20.3% |
| 60/40 | 2004-01-02 | 8.7% | -25.6% | 14.0% |

The ETFs hold US-dollar assets, so EUR/USD moves add to or subtract from your returns. Since 2004 the dollar's strength helped.

## What this test cannot tell you

- The future is not the past. Trend and momentum have long histories, but they can stop working for years.
- Every number is from **one** history. The bootstrap above helps, but crashes nobody has seen before can happen.
- Taxes are simplified. US: FIFO lots, 1-year short/long split, yearly netting and loss carry-forward, dividends/interest taxed yearly, wash-sale rule and state details ignored. Italy: 26%, average cost, losses banked 4 years. Check with a tax professional in the country that taxes you.
- The ETFs it trades track the same indexes as the funds whose history drives the signal, but some are younger or cheaper share classes (VOO for SPY, IEFA for EFA, GLDM for GLD, PDBC for DBC).

Related: [[Guide - Backtesting]] · [[07 - Model Risk and Assumption Failure]] · [[02 - Momentum and Trend Following]] · [[05 - Drawdowns and Recovery]]
