---
type: trial
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-12
tags:
  - type/trial
  - department/trading
  - trading-bot
  - paper-trial
---

# 06 - One-Month Paper Trial

**2026-11-12 → 2026-12-12** · paper capital 10,000 · settings: worst month 15% (vol cap 22.3%), max 80% per ETF, region `us`

> [!warning] Day 1: bot -0.5% vs S&P 500 -0.2%
> Equity 9,951 · behind by 0.3 points (prices through 2026-11-12)

## Daily log

| Run | Prices through | Equity | Bot | S&P 500 | Difference |
|---|---|---|---|---|---|
| [[2026-11-12]] | 2026-11-12 | 9,951 | -0.5% | -0.2% | -0.3% |

## How to read this

- One month is **noise**, not evidence. In the 30-year backtest the bot trailed the S&P 500 in about half of all months and still finished with similar returns and a third of the crash damage.
- The bot rebalances once a month, on the first trading day after the month-end. Expect one rebalance inside this trial.
- What to check: that it ran every weekday, followed its rules, and that the journal explains every trade. That is what this month can prove.

Related: [[00 - Bot Dashboard]] · [[03 - Backtest Report]] · [[02 - Risk Limits]]
