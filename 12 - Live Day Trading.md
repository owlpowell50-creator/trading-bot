---
type: live-day-trading
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-20
tags:
  - type/live-day-trading
  - department/trading
  - trading-bot
  - day-trading
  - alpaca
---

# 12 - Live Day Trading

> [!success] Real orders in a separate Alpaca paper account
> Two strategies, one account: the Opening Range Breakout rules from [[11 - Day Trading Simulator]] on SPY and QQQ, and the **day-trader-skill pack** ([[14 - Skill Pack Day Trader]]: scanner → exit plan → news → time machine → sizing) on 30 liquid stocks. Real bracket orders, practice money. Flat every day by 15:55 New York.

## Account

| | |
|---|---|
| Started | 2026-11-17 with $100,000.00 |
| **Equity** | **$100,361.59** (+0.36%) |
| Trades | 8 (4 winners) |
| Average R | +0.16 |

## One-month trial

| | |
|---|---|
| Trial | 2026-11-17 → 2026-12-17 (day 4 of 30) |
| Result so far | +0.36% |
| Expectation | see [[13 - Day Trading Month Simulation]] — the same rules on the previous month of real data |

## Ledger

| Date | Strategy | Sym | Dir | Qty | Entry (UTC) | Exit (UTC) | P&L $ | R |
|---|---|---|---|---|---|---|---|---|
| 2026-11-20 | ORB | SPY | LONG | 28 | 715.49 (14:55) | 711.86 (15:19) | -101.50 | -1.03 |
| 2026-11-20 | ORB | QQQ | LONG | 31 | 640.17 (14:55) | 633.93 (15:18) | -193.36 | -1.07 |
| 2026-11-19 | ORB | QQQ | SHORT | 29 | 667.58 (15:15) | 661.69 (15:31) | +170.73 | +0.93 |
| 2026-11-19 | ORB | SPY | SHORT | 27 | 733.67 (15:15) | 727.64 (15:36) | +162.81 | +1.07 |
| 2026-11-18 | ORB | QQQ | SHORT | 30 | 654.44 (16:40) | 662.01 (17:29) | -226.97 | -0.96 |
| 2026-11-18 | ORB | SPY | SHORT | 27 | 728.94 (14:50) | open | +0.00 | +0.00 |
| 2026-11-17 | ORB | QQQ | SHORT | 30 | 658.73 (15:10) | 653.93 (15:40) | +144.03 | +1.16 |
| 2026-11-17 | ORB | SPY | SHORT | 27 | 736.78 (15:10) | 733.39 (15:40) | +91.57 | +1.20 |

## By strategy

| Strategy | Trades | Winners | P&L $ | Avg R |
|---|---|---|---|---|
| ORB | 8 | 4 | +47.31 | +0.16 |
| Skill pack | 0 | 0 | +0.00 | — |

## Skill pack decisions

Every breakout the scanner found and what the pipeline decided. Source: [day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT), vendored in the repo.

| Date | Sym | Breakout | Stop / target | Time machine | Decision |
|---|---|---|---|---|---|
| 2026-11-20 | WMT | 10:15 AM @ 129.94 | 128.53 / 132.76 | target 2% / stop 15%, avg R +0.12 | skipped: time machine: strongly toward the stop |
| 2026-11-20 | LLY | 10:10 AM @ 1368.19 | 1360.19 / 1384.19 | target 24% / stop 70%, avg R -0.20 | skipped: time machine: leans toward the stop |
| 2026-11-20 | UNH | 10:05 AM @ 345.21 | 341.88 / 351.87 | target 14% / stop 53%, avg R -0.08 | skipped: time machine: leans toward the stop |
| 2026-11-20 | COST | 10:05 AM @ 1110.41 | 1104.6 / 1122.03 | — | skipped: news: risk (Costco Issues Recall for Cheese Product in Ontario Due to E. Coli Risk) |
| 2026-11-20 | BA | 10:00 AM @ 163.69 | 162.06 / 166.95 | target 13% / stop 55%, avg R -0.17 | skipped: time machine: leans toward the stop |
| 2026-11-20 | PLTR | 10:00 AM @ 151.63 | 149.41 / 156.07 | target 11% / stop 52%, avg R -0.15 | skipped: time machine: strongly toward the stop |
| 2026-11-20 | ADBE | 10:00 AM @ 228.29 | 224.98 / 234.91 | target 4% / stop 39%, avg R -0.13 | skipped: time machine: strongly toward the stop |
| 2026-11-20 | META | 10:00 AM @ 586.86 | 579.38 / 601.82 | target 10% / stop 45%, avg R -0.11 | skipped: time machine: strongly toward the stop |
| 2026-11-20 | XOM | 9:55 AM @ 159.71 | 159.07 / 160.99 | target 29% / stop 68%, avg R -0.08 | skipped: time machine: close to break-even |
| 2026-11-20 | TSLA | 9:55 AM @ 371.32 | 367.92 / 378.12 | target 28% / stop 53%, avg R +0.11 | skipped: time machine: close to break-even |
| 2026-11-20 | GOOGL | 9:55 AM @ 280.3 | 276.18 / 288.54 | target 1% / stop 37%, avg R -0.33 | skipped: time machine: strongly toward the stop |
| 2026-11-20 | AMZN | 9:55 AM @ 257.68 | 253.86 / 265.32 | target 2% / stop 26%, avg R -0.08 | skipped: time machine: strongly toward the stop |
| 2026-11-20 | CAT | 9:50 AM @ 533.43 | 527.1 / 546.09 | target 13% / stop 54%, avg R -0.14 | skipped: time machine: leans toward the stop |
| 2026-11-20 | INTC | 9:50 AM @ 54.78 | 53.99 / 56.36 | target 24% / stop 64%, avg R -0.09 | skipped: time machine: leans toward the stop |
| 2026-11-20 | CRM | 9:50 AM @ 186.72 | 185.08 / 190.0 | target 19% / stop 68%, avg R -0.24 | skipped: time machine: leans toward the stop |
| 2026-11-20 | MSFT | 9:50 AM @ 499.16 | 494.69 / 508.1 | target 11% / stop 51%, avg R -0.14 | skipped: time machine: strongly toward the stop |
| 2026-11-19 | MU | 10:05 AM @ 756.99 | 742.46 / 786.05 | target 9% / stop 49%, avg R -0.14 | skipped: time machine: strongly toward the stop |
| 2026-11-19 | WMT | 10:00 AM @ 125.56 | 124.3 / 128.08 | — | skipped: news: earnings (Walmart Raises Fiscal Year Guidance Amid 3Q Earnings Beat) |
| 2026-11-19 | QCOM | 9:50 AM @ 170.71 | 166.58 / 178.97 | target 4% / stop 31%, avg R +0.01 | skipped: time machine: strongly toward the stop |
| 2026-11-19 | INTC | 9:50 AM @ 59.15 | 58.14 / 61.17 | target 19% / stop 57%, avg R -0.07 | skipped: time machine: leans toward the stop |
| 2026-11-19 | JPM | 9:50 AM @ 327.97 | 326.62 / 330.67 | target 22% / stop 74%, avg R -0.27 | skipped: time machine: leans toward the stop |
| 2026-11-19 | AMD | 9:50 AM @ 554.46 | 544.54 / 574.3 | target 14% / stop 54%, avg R -0.09 | skipped: time machine: leans toward the stop |
| 2026-11-19 | MSFT | 9:50 AM @ 525.34 | 521.79 / 532.44 | target 21% / stop 58%, avg R -0.06 | skipped: time machine: leans toward the stop |
| 2026-11-18 | AVGO | 10:20 AM @ 352.63 | 347.02 / 363.85 | target 3% / stop 34%, avg R -0.12 | skipped: time machine: strongly toward the stop |
| 2026-11-18 | UBER | 10:00 AM @ 69.92 | 68.89 / 71.98 | target 2% / stop 22%, avg R +0.04 | skipped: time machine: strongly toward the stop |
| 2026-11-18 | AMZN | 10:00 AM @ 263.28 | 261.36 / 267.12 | target 21% / stop 55%, avg R -0.03 | skipped: time machine: leans toward the stop |
| 2026-11-18 | DIS | 9:50 AM @ 119.06 | 117.83 / 121.52 | — | skipped: news: earnings (Analysts Adjust Price Targets for The Walt Disney Company) |

Compare with the rule-based replay: [[11 - Day Trading Simulator#Scorecard]] · back to [[00 - Bot Dashboard]]
