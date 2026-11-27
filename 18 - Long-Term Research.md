---
type: research
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-27
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
| Live bot | 9.40% | -17.6% | 0.99 | 1.43 | 0.76 | — |
| Skip a pick if 6-month correlation > 0.8 with a better one | 9.30% | -15.1% | 1.04 | 1.48 | 0.81 | yes |
| Skip a pick if 6-month correlation > 0.6 with a better one | 8.35% | -14.7% | 1.01 | 1.50 | 0.72 | no |
| Rank by momentum per unit of risk | 9.43% | -15.2% | 1.05 | 1.41 | 0.84 | no |
| Park half of unused cash in 7-10y Treasuries when they trend up | 9.38% | -17.6% | 0.99 | 1.42 | 0.76 | no |
| Skip the latest month in momentum (12-1 style) | 8.51% | -27.5% | 0.87 | 1.37 | 0.61 | no |
| Halve exposure if the chosen mix fell 8%+ over 3 months | 9.40% | -17.6% | 0.99 | 1.43 | 0.76 | no |

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
| 2026 | +13.3% | +7.8% |

Beat the live bot in **49.5%** of 2,000 resampled histories (growth difference, middle case -0.01 points a year).

**Verdict: not adopted.** It lowers risk on paper, but it trailed the live bot in 9 of the last 11 years and is no better than a coin flip in the resampling test. Small risk gains are not worth weaker recent results.

Back to [[16 - Bot Brain]] · [[03 - Backtest Report]] · [[17 - Day Trader Research]]
