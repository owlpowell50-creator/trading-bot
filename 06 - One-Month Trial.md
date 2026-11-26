---
type: trial
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-26
tags:
  - type/trial
  - department/trading
  - trading-bot
  - paper-trial
---

# 06 - One-Month Paper Trial

**2026-11-12 → 2026-12-12** · account `alpaca-paper` starting at 100,000 · settings: worst month 15% (vol cap 22.3%), max 80% per ETF, region `us`

> [!success] Day 11: bot -5.2% vs S&P 500 -5.8%
> Equity 94,848 · ahead by 0.6 points (prices through 2026-11-25)

## Daily log

| Run | Prices through | Equity | Bot | S&P 500 | Difference |
|---|---|---|---|---|---|
| [[2026-11-12]] | 2026-11-12 | 99,989 | -0.0% | +0.0% | -0.0% |
| [[2026-11-13]] | 2026-11-13 | 99,471 | -0.5% | -1.3% | +0.7% |
| [[2026-11-16]] | 2026-11-13 | 99,231 | -0.8% | -0.8% | +0.1% |
| [[2026-11-17]] | 2026-11-17 | 97,159 | -2.8% | -4.0% | +1.2% |
| [[2026-11-18]] | 2026-11-18 | 96,244 | -3.8% | -3.9% | +0.2% |
| [[2026-11-19]] | 2026-11-19 | 95,889 | -4.1% | -4.2% | +0.1% |
| [[2026-11-20]] | 2026-11-20 | 93,690 | -6.3% | -7.1% | +0.7% |
| [[2026-11-23]] | 2026-11-23 | 95,021 | -5.0% | -4.8% | -0.1% |
| [[2026-11-24]] | 2026-11-24 | 94,051 | -5.9% | -6.2% | +0.3% |
| [[2026-11-25]] | 2026-11-25 | 92,968 | -7.0% | -8.2% | +1.2% |
| [[2026-11-26]] | 2026-11-25 | 94,848 | -5.2% | -5.8% | +0.6% |

```mermaid
xychart-beta
    title "Return since start (%)"
    x-axis ["11-12", "11-13", "11-16", "11-17", "11-18", "11-19", "11-20", "11-23", "11-24", "11-25", "11-26"]
    y-axis "%" -9 --> 1
    line [-0.0, -0.5, -0.8, -2.8, -3.8, -4.1, -6.3, -5.0, -5.9, -7.0, -5.2]
    line [0.0, -1.3, -0.8, -4.0, -3.9, -4.2, -7.1, -4.8, -6.2, -8.2, -5.8]
```
*Lines: first = **Bot** · second = **S&P 500***

## How to read this

- One month is **noise**, not evidence. In the 30-year backtest the bot trailed the S&P 500 in about half of all months and still finished with similar returns and a third of the crash damage.
- The bot rebalances once a month, on the first trading day after the month-end. Expect one rebalance inside this trial.
- What to check: that it ran every weekday, followed its rules, and that the journal explains every trade. That is what this month can prove.

Related: [[00 - Bot Dashboard]] · [[03 - Backtest Report]] · [[02 - Risk Limits]]
