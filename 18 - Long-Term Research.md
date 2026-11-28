---
type: research
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-28
tags:
  - type/research
  - department/trading
  - trading-bot
  - long-term
  - research
---

# 18 - Long-Term Research

New ideas for the long-term bot, each a small change to the live strategy, replayed 1987-2026 with the live costs and 10% no-trade band. An idea has to (1) raise the Sharpe ratio in **both** halves of the history (1987-2006 and 2007-now), (2) not deepen the worst fall, (3) not do clearly worse in the crises and recent years, and (4) beat the live bot in more than half of 2,000 resampled histories. Already-tested ideas live in [[00 - Variant Lab]] and [[Experiment — Faster Re-entry After a Crash]].

| Idea | Growth / yr | Worst fall | Sharpe | Sharpe 1987-2006 | Sharpe 2007-now | Passes step 1-2 |
|---|---|---|---|---|---|---|
| Live bot | 9.44% | -17.6% | 1.00 | 1.43 | 0.77 | — |
| Skip a pick if 6-month correlation > 0.8 with a better one | 9.33% | -15.1% | 1.05 | 1.48 | 0.81 | yes |
| Skip a pick if 6-month correlation > 0.6 with a better one | 8.38% | -14.7% | 1.01 | 1.50 | 0.72 | no |
| Rank by momentum per unit of risk | 9.47% | -15.2% | 1.05 | 1.41 | 0.84 | no |
| Park half of unused cash in 7-10y Treasuries when they trend up | 9.41% | -17.6% | 0.99 | 1.42 | 0.77 | no |
| Skip the latest month in momentum (12-1 style) | 8.54% | -27.5% | 0.87 | 1.37 | 0.62 | no |
| Halve exposure if the chosen mix fell 8%+ over 3 months | 9.44% | -17.6% | 1.00 | 1.43 | 0.77 | no |

## Closer look: Skip a pick if 6-month correlation > 0.8 with a better one

| Crisis | Live bot | With the idea |
|---|---|---|
| Black Monday 1987 | -7.6% | -7.6% |
| Gulf War recession 1990 | -2.7% | -2.7% |
| Russia / LTCM 1998 | +2.9% | -1.5% |
| Dot-com bust 2000-02 | +26.1% | +20.3% |
| Global financial crisis 2007-09 | +24.7% | +19.8% |
| Flash crash / euro scare 2010 | -10.2% | -5.0% |
| US downgrade / euro debt 2011 | -6.8% | -5.7% |
| China / oil crash 2015-16 | -8.4% | -6.1% |
| Q4 2018 sell-off | -13.3% | -13.7% |
| COVID crash 2020 | +0.7% | -9.5% |
| Inflation bear market 2022 | -6.6% | -6.7% |
| Tariff shock 2025 | -7.6% | -7.6% |

| Year | Live bot | With the idea |
|---|---|---|
| 2016 | +4.0% | +3.0% |
| 2017 | +13.9% | +12.1% |
| 2018 | -6.7% | -7.2% |
| 2019 | +10.1% | +9.6% |
| 2020 | +10.1% | +11.0% |
| 2021 | +27.5% | +28.6% |
| 2022 | -6.9% | -7.0% |
| 2023 | +3.4% | +1.6% |
| 2024 | +18.4% | +15.0% |
| 2025 | +24.3% | +21.9% |
| 2026 | +14.6% | +9.0% |

Beat the live bot in **49.5%** of 2,000 resampled histories (growth difference, middle case -0.01 points a year).

**Verdict: not adopted.** It lowers risk on paper, but it trailed the live bot in 9 of the last 11 years and is no better than a coin flip in the resampling test. Small risk gains are not worth weaker recent results.

## Two tranches (half rebalanced at month-end, half mid-month)

Same signal, same costs; only the trading day is spread out so one unlucky date matters less.

| Version | Growth / yr | Worst fall | Sharpe | Sharpe 1987-2006 | Sharpe 2007-now |
|---|---|---|---|---|---|
| Live (month-end only) | 9.37% | -17.6% | 0.99 | 1.42 | 0.76 |
| Mid-month only | 8.82% | -29.1% | 0.92 | 1.39 | 0.68 |
| Two tranches, half each | 9.11% | -17.6% | 0.98 | 1.42 | 0.75 |

Beat the live bot in 28% of resampled histories. **Not adopted.**

## How much the worst fall depends on the rebalance day

The identical strategy, deciding on a different day of the month. Growth barely changes; the worst fall changes a lot, mostly through when it caught the COVID crash.

| Decides on | Growth / yr | Worst fall | Sharpe | Bottom of worst fall |
|---|---|---|---|---|
| day 3 | 9.48% | -16.4% | 1.01 | 2018-12-24 |
| day 5 | 9.54% | -17.4% | 1.02 | 2011-08-08 |
| day 8 | 9.52% | -20.7% | 1.03 | 2009-08-17 |
| day 10 | 9.62% | -15.4% | 1.02 | 2009-08-17 |
| day 12 | 9.48% | -26.3% | 0.98 | 2020-03-12 |
| day 15 | 9.06% | -29.1% | 0.95 | 2020-03-18 |
| day 18 | 9.12% | -22.6% | 0.96 | 2023-02-24 |
| day 20 | 9.13% | -27.0% | 0.96 | 2020-03-23 |
| day 22 | 8.84% | -26.8% | 0.92 | 2020-03-23 |
| day 25 | 10.19% | -17.3% | 1.08 | 2020-03-18 |
| day 27 | 10.26% | -14.2% | 1.09 | 2018-12-24 |
| month-end (live) | 9.59% | -17.6% | 1.02 | 2016-01-20 |

**What this means:** expect about 9.5% a year whichever day it trades, but plan for a worst fall of about -19% (typical) and up to -29% - not the -17.6% the month-end backtest shows. The live risk limit (stop and ask at -25%) sits inside that range, so an unlucky year could trigger it - that would be the limit doing its job, not a malfunction.


## Crash guards (sell one asset mid-month only on a deep, fast fall)

The plain 200-day crash brake was rejected in [[09 - Upgrades Tested]] for whipsaw. These three guards were declared before testing and judged on 12 rebalance days, so no result rests on calendar luck.

| Version | Growth / yr (month-end) | Worst fall (month-end) | Sharpe 1987-2006 / 2007-now | Median Sharpe, 12 days | Median worst fall | Worst of the 12 | Beat live in resampling |
|---|---|---|---|---|---|---|---|
| Live (no guard) | 9.62% | -17.6% | 1.52 / 0.77 | 1.02 | -19.1% | -29.1% | — |
| G1: 10% off 3-month high and below 100-day average | 8.19% | -19.3% | 1.44 / 0.65 | 0.97 | -17.8% | -19.8% | 0% |
| G2: 15% off 3-month high | 8.74% | -17.6% | 1.47 / 0.68 | 0.99 | -17.6% | -25.0% | 0% |
| G3: 10% fall in 10 trading days | 8.99% | -18.1% | 1.50 / 0.70 | 1.01 | -17.3% | -23.6% | 0% |

**Not adopted.** Every guard lowers growth (0.6-1.4 points a year) and Sharpe, and none beat the live bot in any resampled history. What they buy is a smaller *worst case*: G1 keeps the worst fall near -20% on every rebalance day, against up to -29% without it. That is a preference, not an improvement - if you would rather give up about 1.4 points a year for a lower worst case, G1 is the one to switch on.


Back to [[16 - Bot Brain]] · [[03 - Backtest Report]] · [[17 - Day Trader Research]]
