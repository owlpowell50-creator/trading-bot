---
type: live-day-trading
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-25
tags:
  - type/live-day-trading
  - department/trading
  - trading-bot
  - day-trading
  - alpaca
---

# 12 - Live Day Trading

> [!success] Real orders in a separate Alpaca paper account
> Two strategies, one account: the Opening Range Breakout rules from [[11 - Day Trading Simulator]] on SPY and QQQ, and the **day-trader-skill pack** ([[14 - Skill Pack Day Trader]]: scanner → exit plan → news → time machine → sizing) on 30 liquid stocks. Real bracket orders, practice money. Risk: **$500 per trade (a second same-direction SPY/QQQ trade gets half), $5,000 a day** across both (losses so far + what open trades could lose at their stops). Flat every day by 15:55 New York.

## Account

| | |
|---|---|
| Started | 2026-11-17 with $100,000.00 |
| **Equity** | **$98,236.05** (-1.76%) |
| Trades | 14 (7 winners) |
| Average R | -0.18 |

## One-month trial

| | |
|---|---|
| Trial | 2026-11-17 → 2026-12-17 (day 9 of 30) |
| Result so far | -1.76% |
| Expectation | see [[13 - Day Trading Month Simulation]] — the same rules on the previous month of real data |

## Ledger

| Date | Strategy | Sym | Dir | Qty | Entry (UTC) | Exit (UTC) | P&L $ | R |
|---|---|---|---|---|---|---|---|---|
| 2026-11-25 | ORB | QQQ | LONG | 25 | 617.73 (15:00) | 632.00 (18:46) | +356.69 | +1.48 |
| 2026-11-25 | ORB | SPY | LONG | 66 | 703.19 (15:00) | 714.55 (18:20) | +750.21 | +1.50 |
| 2026-11-24 | ORB | QQQ | LONG | 39 | 642.39 (15:00) | 635.73 (15:25) | -259.60 | -1.04 |
| 2026-11-24 | ORB | SPY | LONG | 84 | 718.91 (14:50) | 697.75 (14:42) | -1,777.44 | -3.60 |
| 2026-11-23 | ORB | QQQ | LONG | 35 | 656.79 (15:25) | 637.36 (14:37) | -680.14 | -1.38 |
| 2026-11-23 | ORB | SPY | LONG | 39 | 726.68 (15:25) | 713.53 (14:37) | -512.86 | -1.04 |
| 2026-11-20 | ORB | SPY | LONG | 28 | 715.49 (14:55) | 711.86 (15:19) | -101.50 | -1.03 |
| 2026-11-20 | ORB | QQQ | LONG | 31 | 640.17 (14:55) | 633.93 (15:18) | -193.36 | -1.07 |
| 2026-11-19 | ORB | QQQ | SHORT | 29 | 667.58 (15:15) | 661.69 (15:31) | +170.73 | +0.93 |
| 2026-11-19 | ORB | SPY | SHORT | 27 | 733.67 (15:15) | 727.64 (15:36) | +162.81 | +1.07 |
| 2026-11-18 | ORB | QQQ | SHORT | 30 | 654.44 (16:40) | 662.01 (17:29) | -226.97 | -0.96 |
| 2026-11-18 | ORB | SPY | SHORT | 27 | 728.94 (14:50) | 727.64 (15:36) | +35.10 | +0.25 |
| 2026-11-17 | ORB | QQQ | SHORT | 30 | 658.73 (15:10) | 653.93 (15:40) | +144.03 | +1.16 |
| 2026-11-17 | ORB | SPY | SHORT | 27 | 736.78 (15:10) | 733.39 (15:40) | +91.57 | +1.20 |

## By strategy

| Strategy | Trades | Winners | P&L $ | Avg R |
|---|---|---|---|---|
| ORB | 14 | 7 | -2,040.73 | -0.18 |
| Skill pack | 0 | 0 | +0.00 | — |

## Skill pack decisions

Every breakout the scanner found and what the pipeline decided. Source: [day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT), vendored in the repo.

| Date | Sym | Breakout | Stop / target | Time machine | Decision |
|---|---|---|---|---|---|
| 2026-11-25 | ADBE | 10:05 AM @ 233.75 | 230.66 / 239.93 | target 5% / stop 43%, avg R -0.15 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | CAT | 10:00 AM @ 524.07 | 516.77 / 538.67 | target 8% / stop 48%, avg R -0.16 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | BA | 10:00 AM @ 162.13 | 160.53 / 165.33 | — | skipped: news: deal (Philippines Expresses Intent to Acquire Six Boeing CH-47 Chinook Helicopters) |
| 2026-11-25 | PLTR | 10:00 AM @ 155.94 | 153.57 / 160.68 | target 10% / stop 55%, avg R -0.20 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | QCOM | 10:00 AM @ 160.62 | 159.0 / 163.86 | target 27% / stop 68%, avg R -0.11 | skipped: time machine: close to break-even |
| 2026-11-25 | MU | 10:00 AM @ 580.37 | 568.45 / 604.21 | target 9% / stop 57%, avg R -0.27 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | CRM | 10:00 AM @ 193.25 | 190.0 / 199.75 | target 2% / stop 39%, avg R -0.21 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | UNH | 10:00 AM @ 340.64 | 337.69 / 346.54 | target 19% / stop 60%, avg R -0.12 | skipped: time machine: leans toward the stop |
| 2026-11-25 | BAC | 10:00 AM @ 47.8 | 47.34 / 48.72 | target 4% / stop 43%, avg R -0.19 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | JPM | 10:00 AM @ 312.42 | 310.85 / 315.56 | target 19% / stop 69%, avg R -0.25 | skipped: time machine: leans toward the stop |
| 2026-11-25 | AVGO | 10:00 AM @ 287.32 | 282.87 / 296.22 | target 8% / stop 52%, avg R -0.24 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | AMD | 10:00 AM @ 387.71 | 378.27 / 406.59 | target 7% / stop 51%, avg R -0.20 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | META | 10:00 AM @ 585.34 | 573.5 / 609.02 | target 1% / stop 23%, avg R -0.14 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | NVDA | 10:00 AM @ 145.62 | 143.12 / 150.62 | target 4% / stop 56%, avg R -0.38 | skipped: time machine: strongly toward the stop |
| 2026-11-25 | GOOGL | 9:55 AM @ 266.01 | 264.24 / 269.55 | target 19% / stop 71%, avg R -0.29 | skipped: time machine: leans toward the stop |
| 2026-11-25 | XOM | 9:50 AM @ 159.17 | 157.73 / 162.05 | target 7% / stop 43%, avg R -0.10 | skipped: time machine: strongly toward the stop |
| 2026-11-24 | ORCL | 10:00 AM @ 111.82 | 110.58 / 114.3 | target 27% / stop 64%, avg R -0.06 | skipped: time machine: close to break-even |
| 2026-11-24 | AVGO | 10:00 AM @ 308.05 | 301.02 / 322.11 | target 1% / stop 32%, avg R -0.22 | skipped: time machine: strongly toward the stop |
| 2026-11-24 | META | 10:00 AM @ 598.96 | 592.84 / 611.2 | target 17% / stop 56%, avg R -0.14 | skipped: time machine: leans toward the stop |
| 2026-11-24 | LLY | 9:55 AM @ 1407.41 | 1388.76 / 1444.71 | target 4% / stop 45%, avg R -0.23 | skipped: time machine: strongly toward the stop |
| 2026-11-24 | WMT | 9:55 AM @ 131.32 | 130.5 / 132.96 | target 21% / stop 47%, avg R +0.10 | skipped: time machine: close to break-even |
| 2026-11-24 | XOM | 9:55 AM @ 159.01 | 157.99 / 161.05 | target 17% / stop 58%, avg R -0.13 | skipped: time machine: leans toward the stop |
| 2026-11-24 | DIS | 9:50 AM @ 121.26 | 120.13 / 123.52 | — | skipped: news: deal (Disney Secures Bundesliga Highlight Rights in Sublicensing Deal with RTL) |
| 2026-11-24 | UBER | 9:50 AM @ 64.74 | 64.11 / 66.0 | target 14% / stop 53%, avg R -0.10 | skipped: time machine: leans toward the stop |
| 2026-11-24 | PLTR | 9:50 AM @ 161.76 | 159.77 / 165.74 | target 18% / stop 64%, avg R -0.19 | skipped: time machine: leans toward the stop |
| 2026-11-24 | ADBE | 9:50 AM @ 231.68 | 226.15 / 242.74 | target 0% / stop 16%, avg R -0.07 | skipped: time machine: strongly toward the stop |
| 2026-11-24 | CRM | 9:50 AM @ 192.07 | 187.57 / 201.07 | target 0% / stop 23%, avg R -0.16 | skipped: time machine: strongly toward the stop |
| 2026-11-24 | MA | 9:50 AM @ 641.98 | 637.49 / 650.96 | target 13% / stop 43%, avg R -0.00 | skipped: time machine: leans toward the stop |
| 2026-11-24 | V | 9:50 AM @ 412.7 | 409.74 / 418.62 | target 13% / stop 37%, avg R +0.09 | skipped: time machine: leans toward the stop |
| 2026-11-24 | UNH | 9:50 AM @ 336.63 | 332.44 / 345.01 | target 8% / stop 49%, avg R -0.14 | skipped: time machine: strongly toward the stop |
| 2026-11-24 | COST | 9:50 AM @ 1079.15 | 1073.36 / 1090.73 | target 27% / stop 48%, avg R +0.18 | skipped: time machine: close to break-even |
| 2026-11-24 | BAC | 9:50 AM @ 48.51 | 48.16 / 49.21 | target 12% / stop 60%, avg R -0.24 | skipped: time machine: strongly toward the stop |
| 2026-11-24 | JPM | 9:50 AM @ 317.18 | 315.44 / 320.66 | target 18% / stop 67%, avg R -0.25 | skipped: time machine: leans toward the stop |
| 2026-11-24 | NFLX | 9:50 AM @ 58.58 | 57.91 / 59.92 | target 3% / stop 50%, avg R -0.31 | skipped: time machine: strongly toward the stop |
| 2026-11-24 | AMZN | 9:50 AM @ 254.0 | 251.97 / 258.06 | — | skipped: news: deal (AWS CEO Matt Garman Advocates for Architectural Containment in AI Security) |
| 2026-11-24 | MSFT | 9:50 AM @ 494.18 | 490.95 / 500.64 | target 20% / stop 66%, avg R -0.20 | skipped: time machine: leans toward the stop |
| 2026-11-24 | AAPL | 9:50 AM @ 352.9 | 349.13 / 360.44 | target 3% / stop 35%, avg R -0.13 | skipped: time machine: strongly toward the stop |
| 2026-11-23 | BAC | 11:15 AM @ 48.51 | 48.06 / 49.41 | target 1% / stop 26%, avg R -0.09 | skipped: time machine: strongly toward the stop |
| 2026-11-23 | WMT | 10:35 AM @ 128.21 | 126.89 / 130.85 | — | skipped: news: deal (Walmart and Other Retailers Contacted Regarding Potential Grubhub Acquisition) |
| 2026-11-23 | PLTR | 10:25 AM @ 160.47 | 157.99 / 165.43 | target 7% / stop 44%, avg R -0.12 | skipped: time machine: strongly toward the stop |

## Daily reviews

[[Day Trade Review 2026-11-25|2026-11-25]] · [[Day Trade Review 2026-11-24|2026-11-24]] · [[Day Trade Review 2026-11-23|2026-11-23]] · [[Day Trade Review 2026-11-20|2026-11-20]] · [[Day Trade Review 2026-11-19|2026-11-19]] · [[Day Trade Review 2026-11-18|2026-11-18]] · [[Day Trade Review 2026-11-17|2026-11-17]]

Compare with the rule-based replay: [[11 - Day Trading Simulator#Scorecard]] · back to [[00 - Bot Dashboard]]
