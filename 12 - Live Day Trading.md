---
type: live-day-trading
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-24
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
| **Equity** | **$98,799.79** (-1.20%) |
| Trades | 12 (5 winners) |
| Average R | -0.16 |

## One-month trial

| | |
|---|---|
| Trial | 2026-11-17 → 2026-12-17 (day 8 of 30) |
| Result so far | -1.20% |
| Expectation | see [[13 - Day Trading Month Simulation]] — the same rules on the previous month of real data |

## Ledger

| Date | Strategy | Sym | Dir | Qty | Entry (UTC) | Exit (UTC) | P&L $ | R |
|---|---|---|---|---|---|---|---|---|
| 2026-11-24 | ORB | QQQ | LONG | 39 | 642.39 (15:00) | 635.73 (15:25) | -259.60 | -1.04 |
| 2026-11-24 | ORB | SPY | LONG | 84 | 718.91 (14:50) | open | +0.00 | +0.00 |
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
| ORB | 12 | 5 | -1,370.19 | -0.16 |
| Skill pack | 0 | 0 | +0.00 | — |

## Skill pack decisions

Every breakout the scanner found and what the pipeline decided. Source: [day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT), vendored in the repo.

| Date | Sym | Breakout | Stop / target | Time machine | Decision |
|---|---|---|---|---|---|
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
| 2026-11-23 | INTC | 10:25 AM @ 59.16 | 58.28 / 60.92 | target 18% / stop 62%, avg R -0.15 | skipped: time machine: leans toward the stop |
| 2026-11-23 | AAPL | 10:25 AM @ 351.0 | 347.61 / 357.78 | target 2% / stop 35%, avg R -0.19 | skipped: time machine: strongly toward the stop |
| 2026-11-23 | DIS | 10:20 AM @ 119.17 | 118.25 / 121.01 | target 9% / stop 40%, avg R +0.01 | skipped: time machine: leans toward the stop |
| 2026-11-23 | UBER | 10:20 AM @ 65.42 | 64.56 / 67.14 | target 2% / stop 34%, avg R -0.14 | skipped: time machine: strongly toward the stop |
| 2026-11-23 | QCOM | 10:20 AM @ 164.59 | 162.56 / 168.65 | target 20% / stop 60%, avg R -0.09 | skipped: time machine: leans toward the stop |
| 2026-11-23 | TSLA | 10:15 AM @ 389.9 | 380.68 / 408.34 | target 0% / stop 16%, avg R -0.09 | skipped: time machine: strongly toward the stop |
| 2026-11-23 | BA | 10:05 AM @ 161.18 | 159.92 / 163.7 | target 17% / stop 66%, avg R -0.25 | skipped: time machine: leans toward the stop |
| 2026-11-23 | CRM | 10:05 AM @ 184.14 | 182.86 / 186.7 | target 21% / stop 72%, avg R -0.26 | skipped: time machine: leans toward the stop |
| 2026-11-23 | XOM | 10:05 AM @ 158.82 | 157.98 / 160.5 | target 23% / stop 63%, avg R -0.11 | skipped: time machine: leans toward the stop |
| 2026-11-23 | MU | 10:00 AM @ 694.8 | 683.18 / 718.04 | target 13% / stop 65%, avg R -0.29 | skipped: time machine: strongly toward the stop |
| 2026-11-23 | UNH | 10:00 AM @ 330.24 | 325.62 / 339.48 | target 4% / stop 39%, avg R -0.12 | skipped: time machine: strongly toward the stop |
| 2026-11-23 | NVDA | 10:00 AM @ 168.56 | 162.03 / 181.62 | target 0% / stop 9%, avg R -0.24 | skipped: time machine: strongly toward the stop |
| 2026-11-23 | LLY | 9:55 AM @ 1371.53 | 1357.55 / 1399.49 | — | skipped: news: deal (Eli Lilly and Company Acquires LoQus23 Therapeutics) |
| 2026-11-23 | ADBE | 9:50 AM @ 220.78 | 219.27 / 223.8 | target 26% / stop 69%, avg R -0.14 | skipped: time machine: leans toward the stop |
| 2026-11-23 | MA | 9:50 AM @ 636.0 | 632.34 / 643.32 | target 19% / stop 53%, avg R -0.03 | skipped: time machine: leans toward the stop |
| 2026-11-23 | V | 9:50 AM @ 410.12 | 407.36 / 415.64 | target 15% / stop 42%, avg R +0.06 | skipped: time machine: leans toward the stop |

## Daily reviews

[[Day Trade Review 2026-11-24|2026-11-24]] · [[Day Trade Review 2026-11-23|2026-11-23]] · [[Day Trade Review 2026-11-20|2026-11-20]] · [[Day Trade Review 2026-11-19|2026-11-19]] · [[Day Trade Review 2026-11-18|2026-11-18]] · [[Day Trade Review 2026-11-17|2026-11-17]]

Compare with the rule-based replay: [[11 - Day Trading Simulator#Scorecard]] · back to [[00 - Bot Dashboard]]
