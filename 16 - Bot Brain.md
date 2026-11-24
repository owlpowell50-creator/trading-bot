---
type: bot-brain
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-23
tags:
  - type/bot-note
  - trading-bot
  - brain
---
# 16 - Bot Brain

> [!abstract] What the bot is thinking — 2026-11-23 (prices through 2026-11-23)
> The bot reviews itself after every daily run: it previews the next rebalance, measures how close each decision is to flipping, checks volatility, stress and the day trader, and flags anything unusual. It never trades from here.

## Thoughts

- if the month ended today I would hold cash 67%, commodities 33%
- that would mean cash 1% → 67%; commodities 23% → 33%; US stocks 39% → 0%; foreign stocks 37% → 0% at the next rebalance (1 Dec)
- real estate would get in after a 0.8% rise (others unchanged)
- US stocks would get in after a 2.9% rise (others unchanged)
- 7-10y Treasuries would get in after a 3.5% rise (others unchanged)
- portfolio volatility 13.0% against a cap of 22.3%
- S&P 500 is -0.9% vs its 200-day average and -7.1% from its 1-year high
- live account -5.0% from its high
- worst stress scenario for today's holdings: equity crash -20.7%
- day trader last 5 sessions: 7 closed trades, 4 winners, avg R +0.19
- skill pack looked at 47 breakouts; most common decision: time machine (42)

## Alerts

- 🟠 real estate is within 0.8% of entering the portfolio
- 🟠 US stocks volatility 32% (1 month) vs 15% normal
- 🔴 day trader has trades with no recorded exit: SPY 2026-11-18, SPY 2026-11-23, QQQ 2026-11-23 — check the day-trading account is flat

## If the month ended today

| Asset | Score (avg 3/6/12-month return) | Held now | Would hold | Move that flips it |
|---|---|---|---|---|
| commodities | +7.6% (beats T-bills) | 23% | 33% | 5.1% fall → drop out |
| real estate | +1.3% | 0% | 0% | 0.8% rise → get in |
| US stocks | -0.7% | 39% | 0% | 2.9% rise → get in |
| 7-10y Treasuries | -1.3% | 0% | 0% | 3.5% rise → get in |
| foreign stocks | -1.7% | 37% | 0% | 3.9% rise → get in |
| 20y+ Treasuries | -2.6% | 0% | 0% | 4.9% rise → get in |
| gold | -16.9% | 0% | 0% | 22.8% rise → get in |
| cash (T-bills) | +2.1% | 1% | 67% | — |

*Flip moves assume the other assets stand still; the score is the average of the 3-, 6- and 12-month returns, and the bot holds up to three assets that beat T-bills.*

## Volatility

| Asset | 1 month | 3 months | 1 year |
|---|---|---|---|
| US stocks | 32% | 20% | 15% |
| foreign stocks | 25% | 17% | 17% |
| 7-10y Treasuries | 7% | 6% | 5% |
| 20y+ Treasuries | 11% | 11% | 10% |
| real estate | 20% | 16% | 14% |
| gold | 34% | 26% | 30% |
| commodities | 19% | 19% | 21% |

Portfolio volatility now **13.0%**, planned **6.2%**, cap 22.3%.

## Stress test on today's holdings

| Scenario | One-month loss |
|---|---|
| Equity crash | -20.7% |
| Credit crisis | -19.9% |
| Everything falls | -13.8% |
| Inflation shock | -5.3% |
| Rate shock | -3.8% |

*Scenarios from [[26 - Stress Scenario Library]].*

## Day trader

- Sessions reviewed: 2026-11-17, 2026-11-18, 2026-11-19, 2026-11-20, 2026-11-23
- Closed trades 7, winners 4, P&L $47.31, average R +0.19
- Skill pack decisions: time machine (42), news (5)

---

[[00 - Bot Dashboard]] · [[12 - Live Day Trading]] · [[15 - Crisis Simulation]] · [[39 - The Monthly Rebalance, Step by Step]] · [[18 - Daily Risk Dashboard and Checks]]
