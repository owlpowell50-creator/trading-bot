---
type: dashboard
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-24
tags:
  - type/dashboard
  - department/trading
  - trading-bot
  - type/dashboard
---

# Trading Bot — Dashboard

> [!info] 🤖 Bot is ACTIVE — last run 2026-11-24 at 16:13: **HOLD**
> No rebalance due (signal of 2026-10-30 already acted on).
> Next scheduled rebalance: **2026-12-01** (first trading day of the month). Every other weekday it checks prices and risk, and writes a journal.

**Mode:** `alpaca-paper` · **Region:** `us` · **Strategy:** `CORE` · **Data through:** 2026-11-24

## Account

| | |
|---|---|
| Equity | 94,051 |
| Started with | 100,000 |
| Return since start | -5.9% |
| Peak | 99,989 |
| Drawdown | -5.9% (halt at -25%) |

## Holdings now

| Asset | Weight | Instrument |
|---|---|---|
| US stocks (S&P 500) | 39.0% | VOO (US-listed) |
| Developed ex-US stocks | 37.0% | IEFA (US-listed) |
| Commodities | 23.4% | PDBC (US-listed) |
| Cash (T-bills) | 0.5% | SGOV (US-listed) |

```mermaid
pie showData title What the bot holds now
    "US stocks (S&P 500) (VOO)" : 39.0
    "Developed ex-US stocks (IEFA)" : 37.0
    "Commodities (PDBC)" : 23.4
    "Cash (T-bills) (SGOV)" : 0.5
```

## Recent runs

| Date | Status | Equity |
|---|---|---|
| [[2026-11-24]] | HOLD | 94,051 |
| [[2026-11-23]] | HOLD | 95,021 |
| [[2026-11-20]] | HOLD | 93,690 |
| [[2026-11-19]] | HOLD | 95,889 |
| [[2026-11-18]] | HOLD | 96,244 |
| [[2026-11-17]] | HOLD | 97,159 |
| [[2026-11-16]] | HOLD | 99,231 |
| [[2026-11-16]] | HOLD | 99,240 |
| [[2026-11-13]] | HOLD | 99,471 |
| [[2026-11-12]] | TRADED | 99,989 |

## Equity
```mermaid
xychart-beta
    title "Paper account value"
    x-axis ["11-12", "11-13", "11-16", "11-17", "11-18", "11-19", "11-20", "11-23", "11-24"]
    y-axis "Value" 93060 --> 100619
    line [99989.1, 99470.6, 99230.9, 97159.3, 96244.1, 95888.9, 93690.1, 95020.8, 94050.6]
```

## Notes

- [[06 - One-Month Trial]] — **live paper trial vs the S&P 500**
- [[07 - Trade Log]] — every buy and sell
- [[08 - Last 12 Months Replay]] — every trade it would have made in the past year
- [[09 - Upgrades Tested]] — ideas tested to make it smarter, and why most were rejected
- [[01 - How the Bot Works]] — the rules, in plain words
- [[02 - Risk Limits]] — **edit this to change the bot's settings**
- [[03 - Backtest Report]] — 1997–2026 evidence incl. every crash
- [[04 - How to Run It]] — commands, schedule, going live
- [[05 - Fixes to the Old Engine]] — what was broken and what changed
