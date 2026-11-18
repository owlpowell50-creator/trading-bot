---
type: live-day-trading
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-18
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
| **Equity** | **$99,957.04** (-0.04%) |
| Trades | 4 (2 winners) |
| Average R | +0.35 |

## One-month trial

| | |
|---|---|
| Trial | 2026-11-17 → 2026-12-17 (day 2 of 30) |
| Result so far | -0.04% |
| Expectation | see [[13 - Day Trading Month Simulation]] — the same rules on the previous month of real data |

## Ledger

| Date | Strategy | Sym | Dir | Qty | Entry (UTC) | Exit (UTC) | P&L $ | R |
|---|---|---|---|---|---|---|---|---|
| 2026-11-18 | ORB | QQQ | SHORT | 30 | 654.44 (16:40) | 662.01 (17:29) | -226.97 | -0.96 |
| 2026-11-18 | ORB | SPY | SHORT | 27 | 728.94 (14:50) | open | +0.00 | +0.00 |
| 2026-11-17 | ORB | QQQ | SHORT | 30 | 658.73 (15:10) | 653.93 (15:40) | +144.03 | +1.16 |
| 2026-11-17 | ORB | SPY | SHORT | 27 | 736.78 (15:10) | 733.39 (15:40) | +91.57 | +1.20 |

## By strategy

| Strategy | Trades | Winners | P&L $ | Avg R |
|---|---|---|---|---|
| ORB | 4 | 2 | +8.63 | +0.35 |
| Skill pack | 0 | 0 | +0.00 | — |

## Skill pack decisions

Every breakout the scanner found and what the pipeline decided. Source: [day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT), vendored in the repo.

| Date | Sym | Breakout | Stop / target | Time machine | Decision |
|---|---|---|---|---|---|
| 2026-11-18 | AVGO | 10:20 AM @ 352.63 | 347.02 / 363.85 | target 3% / stop 34%, avg R -0.12 | skipped: time machine: strongly toward the stop |
| 2026-11-18 | UBER | 10:00 AM @ 69.92 | 68.89 / 71.98 | target 2% / stop 22%, avg R +0.04 | skipped: time machine: strongly toward the stop |
| 2026-11-18 | AMZN | 10:00 AM @ 263.28 | 261.36 / 267.12 | target 21% / stop 55%, avg R -0.03 | skipped: time machine: leans toward the stop |
| 2026-11-18 | DIS | 9:50 AM @ 119.06 | 117.83 / 121.52 | — | skipped: news: earnings (Analysts Adjust Price Targets for The Walt Disney Company) |

Compare with the rule-based replay: [[11 - Day Trading Simulator#Scorecard]] · back to [[00 - Bot Dashboard]]
