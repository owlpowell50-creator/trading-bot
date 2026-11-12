---
type: dashboard
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-12
tags:
  - type/dashboard
  - department/trading
  - trading-bot
  - type/dashboard
---

# Trading Bot — Dashboard

> [!success] 🤖 Bot is ACTIVE — last run 2026-11-12 at 16:40: **TRADED**
> Rebalanced on the 2026-10-30 signal: 4 orders.
> Next scheduled rebalance: **2026-12-01** (first trading day of the month). Every other weekday it checks prices and risk, and writes a journal.

**Mode:** `alpaca-paper` · **Region:** `us` · **Strategy:** `CORE` · **Data through:** 2026-11-12

## Account

| | |
|---|---|
| Equity | 99,989 |
| Started with | 100,000 |
| Return since start | -0.0% |
| Peak | 100,000 |
| Drawdown | +0.0% (halt at -25%) |

## Holdings now

| Asset | Weight | Instrument |
|---|---|---|
| US stocks (S&P 500) | 39.1% | VOO (US-listed) |
| Developed ex-US stocks | 36.9% | IEFA (US-listed) |
| Commodities | 23.4% | PDBC (US-listed) |
| Cash (T-bills) | 0.5% | SGOV (US-listed) |

```mermaid
pie showData title What the bot holds now
    "US stocks (S&P 500) (VOO)" : 39.1
    "Developed ex-US stocks (IEFA)" : 36.9
    "Commodities (PDBC)" : 23.4
    "Cash (T-bills) (SGOV)" : 0.5
```

## Recent runs

| Date | Status | Equity |
|---|---|---|
| [[2026-11-12]] | TRADED | 99,989 |

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
