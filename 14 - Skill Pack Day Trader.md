---
type: bot-note
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-18
tags:
  - type/bot-note
  - department/trading
  - trading-bot
  - day-trading
---
# 14 - Skill Pack Day Trader

> [!info] A second day-trading strategy, running next to the SPY/QQQ breakout
> The open-source **day-trader-skill** pack ([github.com/Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill), MIT licence) is copied into the bot at `vendor/day-trader-skill` and its tools run as a pipeline inside the GitHub day-trader job, in the same separate Alpaca paper account. Results land in [[12 - Live Day Trading]] (ledger, *By strategy* and *Skill pack decisions*).

## The pipeline (every 20 seconds, 9:50 to 11:30 New York)

| Step | Pack tool | What the bot does with it |
|---|---|---|
| 1 Scan | `trader-scanner` → `orb_hit()` | 30 liquid stocks (AAPL, MSFT, NVDA, AMZN, META, GOOGL, TSLA, AMD …). A hit is the first 5-minute close above the 15-minute opening-range high. Only fresh hits count. |
| 2 Plan | `trader-exit` defaults | Stop at the opening-range midpoint, target 2R. |
| 3 News | `trader-news` keyword tags | Today's headlines (Alpaca news feed). Earnings, halt, deal or risk news → skip. |
| 4 Odds | `trader-timemachine` | 10,000 replays on the stock's own last ~40 sessions (seed 19), plus the same rule replayed on each of those days. Only *Leans/Strongly toward the target* with average R above 0 passes. |
| 5 Size | `trader-budget` / `trader-risk` rules | $500 at risk per trade, at most 1× the account in one stock, max 3 trades a day, reward/risk ≥ 1, stop required, no entries after 11:30. |
| 6 Order | bot's own paper code | Market entry + stop + target as one bracket order (`dts-…` order ids). Flat by 15:55 with everything else. |

## Shared guard rails

- One shared budget of **$5,000 of risk a day** for both strategies: today's losses so far plus what every open trade would lose at its stop can never add up to more than $5,000. New trades are shrunk to fit what is left; once it is used up, nothing new opens until a trade closes in profit.
- Paper account only, and it refuses to trade if the long-term portfolio's ETFs show up in the account.
- Long only (the pack's v2 is buy-only).
- The pack's own `trader-broker` asks a human "yes" for every order; the bot doesn't use it — it places its own paper orders, which is why this runs on practice money only.

Back to [[00 - Bot Dashboard]] · [[11 - Day Trading Simulator]] · [[13 - Day Trading Month Simulation]]
