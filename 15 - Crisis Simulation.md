---
type: crisis-simulation
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-22
tags:
  - type/crisis-simulation
  - department/trading
  - trading-bot
  - backtest
  - crisis
---

# 15 - Crisis Simulation

> [!info] The long-term bot (CORE, today's settings: volatility cap 22.3%, max 80% in one fund, 10 bp costs) replayed day by day from 1987-02-02 through every major crisis, against the S&P 500, the Dow and the Nasdaq.
> Index columns are price only (no dividends), like the numbers you see quoted; *S&P 500 + dividends* is the fair comparison because the bot's numbers include dividends and interest. Before 2004 the bot could only use US stocks, foreign stocks, Treasuries, real estate and cash (gold and commodity ETFs didn't exist yet). Taxes not included.

## Whole period

| | Yearly return | Worst fall from a peak | $10,000 became |
|---|---|---|---|
| **Bot** | +9.4% | -17.6% | $354,453 |
| S&P 500 + dividends | +10.6% | -55.2% | $560,889 |
| S&P 500 | +8.4% | -56.8% | $249,969 |
| Nasdaq | +10.7% | -77.9% | $569,429 |

From 1987-02-02 to 2026-11-20.

## Crisis by crisis — return from the S&P 500's peak to its bottom

| Crisis | Window | Bot | S&P 500 + dividends | S&P 500 | Dow | Nasdaq |
|---|---|---|---|---|---|---|
| Black Monday 1987 | 1987-08-25 → 1987-12-04 | **-7.8%** | -33.0% | -33.5% | — | -35.6% |
| Gulf War recession 1990 | 1990-07-16 → 1990-10-11 | **-2.7%** | -19.2% | -19.9% | — | -30.7% |
| Russia / LTCM 1998 | 1998-07-17 → 1998-10-08 | **+2.9%** | -18.2% | -19.2% | -17.2% | -29.4% |
| Dot-com bust 2000-02 | 2000-03-24 → 2002-10-09 | **+26.1%** | -47.5% | -49.1% | -34.4% | -77.6% |
| Global financial crisis 2007-09 | 2007-10-09 → 2009-03-09 | **+24.7%** | -55.2% | -56.8% | -53.8% | -54.8% |
| Flash crash / euro scare 2010 | 2010-04-23 → 2010-07-02 | **-10.2%** | -15.7% | -16.0% | -13.5% | -17.3% |
| US downgrade / euro debt 2011 | 2011-04-29 → 2011-10-03 | **-6.8%** | -18.6% | -19.4% | -16.8% | -18.7% |
| China / oil crash 2015-16 | 2015-05-21 → 2016-02-11 | **-8.4%** | -13.0% | -14.2% | -14.4% | -16.2% |
| Q4 2018 sell-off | 2018-09-20 → 2018-12-24 | **-13.3%** | -19.3% | -19.8% | -18.2% | -22.9% |
| COVID crash 2020 | 2020-02-19 → 2020-03-23 | **+0.7%** | -33.7% | -33.9% | -36.7% | -30.1% |
| Inflation bear market 2022 | 2022-01-03 → 2022-10-12 | **-6.6%** | -24.5% | -25.4% | -20.2% | -34.2% |
| Tariff shock 2025 | 2025-02-19 → 2025-04-08 | **-7.6%** | -18.8% | -18.9% | -15.6% | -23.9% |

The bot lost less than the S&P 500 (with dividends) in **12 of 12** crises.

## Worst fall inside each crisis, and how long until it was back to where it started

| Crisis | Bot worst fall | Bot back to start | S&P 500 worst fall | S&P 500 back to start | Nasdaq back to start |
|---|---|---|---|---|---|
| Black Monday 1987 | -11.8% | 20 months | -33.1% | 21 months | 23 months |
| Gulf War recession 1990 | -5.0% | 7 months | -19.2% | 7 months | 8 months |
| Russia / LTCM 1998 | -2.3% | 3 months | -19.0% | 4 months | 4 months |
| Dot-com bust 2000-02 | -6.6% | 30 months | -47.5% | 79 months | 179 months |
| Global financial crisis 2007-09 | -9.9% | 17 months | -55.2% | 58 months | 40 months |
| Flash crash / euro scare 2010 | -10.3% | 6 months | -15.7% | 6 months | 6 months |
| US downgrade / euro debt 2011 | -10.8% | 22 months | -18.6% | 9 months | 9 months |
| China / oil crash 2015-16 | -11.9% | 28 months | -13.0% | 11 months | 14 months |
| Q4 2018 sell-off | -13.6% | 12 months | -19.3% | 7 months | 7 months |
| COVID crash 2020 | -9.1% | 1 months | -33.7% | 6 months | 4 months |
| Inflation bear market 2022 | -10.5% | 26 months | -24.5% | 23 months | 25 months |
| Tariff shock 2025 | -8.7% | 2 months | -18.8% | 4 months | 4 months |

## Crash plus the year after (does it miss the rebound?)

| Crisis | Bot | S&P 500 + dividends | Nasdaq |
|---|---|---|---|
| Black Monday 1987 | **-5.5%** | -15.0% | -17.5% |
| Gulf War recession 1990 | **+8.3%** | +7.6% | +10.5% |
| Russia / LTCM 1998 | **+11.4%** | +14.6% | +43.7% |
| Dot-com bust 2000-02 | **+42.0%** | -28.8% | -61.5% |
| Global financial crisis 2007-09 | **+35.8%** | -23.0% | -16.5% |
| Flash crash / euro scare 2010 | **+7.7%** | +12.6% | +11.7% |
| US downgrade / euro debt 2011 | **-6.8%** | +9.3% | +8.6% |
| China / oil crash 2015-16 | **-4.3%** | +12.5% | +12.6% |
| Q4 2018 sell-off | **-1.8%** | +12.6% | +11.5% |
| COVID crash 2020 | **+10.7%** | +17.7% | +34.7% |
| Inflation bear market 2022 | **-7.3%** | -6.7% | -14.3% |
| Tariff shock 2025 | **+33.4%** | +11.9% | +12.9% |

## What the bot was holding

| Crisis | Going in | Halfway through |
|---|---|---|
| Black Monday 1987 | Cash 67%, US stocks 33% | Cash 100% |
| Gulf War recession 1990 | Cash 67%, US stocks 33% | Cash 100% |
| Russia / LTCM 1998 | US Treasuries 7-10y 53%, US Treasuries 20y+ 31%, US stocks 15% | US Treasuries 7-10y 42%, US Treasuries 20y+ 32%, Cash 25% |
| Dot-com bust 2000-02 | Developed ex-US stocks 39%, Cash 37%, US stocks 24% | Cash 41%, US Treasuries 7-10y 34%, US real estate 24% |
| Global financial crisis 2007-09 | Commodities 38%, Gold 37%, Developed ex-US stocks 19%, Cash 5% | US Treasuries 7-10y 50%, US Treasuries 20y+ 34%, Commodities 17% |
| Flash crash / euro scare 2010 | US stocks 45%, Developed ex-US stocks 33%, US real estate 21% | US Treasuries 20y+ 41%, Gold 36%, US real estate 23% |
| US downgrade / euro debt 2011 | US stocks 40%, US real estate 32%, Commodities 28% | Gold 43%, US real estate 31%, Commodities 25% |
| China / oil crash 2015-16 | US stocks 37%, Developed ex-US stocks 32%, US Treasuries 20y+ 27%, Cash 5% | US Treasuries 7-10y 58%, US Treasuries 20y+ 23%, US real estate 19% |
| Q4 2018 sell-off | US stocks 45%, US real estate 33%, Commodities 23% | US real estate 35%, US stocks 34%, Cash 31% |
| COVID crash 2020 | Gold 36%, US stocks 34%, US Treasuries 20y+ 26%, Cash 4% | US Treasuries 7-10y 50%, US Treasuries 20y+ 26%, Gold 24% |
| Inflation bear market 2022 | US stocks 40%, US real estate 36%, Commodities 24% | Cash 68%, Commodities 32% |
| Tariff shock 2025 | Gold 36%, US stocks 35%, US real estate 29% | Gold 36%, Commodities 34%, Developed ex-US stocks 30% |

## Day trader (opening-range breakout on SPY and QQQ) through the crises with 5-minute data

$100,000 practice account, the live day trader's entry rules with a 2% daily loss limit (the live bot now uses a $5,000-a-day risk budget), flat every night. Alpaca SIP 5-minute bars, so only crises from 2016 on.

| Crisis | Return | Worst fall | Trades | Winners | Profit factor | S&P 500 same window |
|---|---|---|---|---|---|---|
| Q4 2018 sell-off | **-3.7%** | -4.2% | 131 | 43% | 0.62 | -19.8% |
| COVID crash 2020 | **-5.9%** | -6.1% | 42 | 31% | 0.25 | -33.9% |
| Inflation bear market 2022 | **-3.3%** | -5.3% | 390 | 47% | 0.89 | -25.4% |
| Tariff shock 2025 | **+5.0%** | -0.4% | 70 | 69% | 2.90 | -18.9% |

Source: `tools/crisis_sim.py` (GitHub → Actions → crisis). Raw numbers in `state/crisis.json`.

Back to [[00 - Bot Dashboard]] · [[03 - Backtest Report]] · [[02 - Risk Limits]]
