---
type: guide
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
tags:
  - type/guide
  - department/trading
  - trading-bot
---
# 01 - How the Bot Works

## In one paragraph

Once a month the bot looks at 7 big asset classes — US stocks, other developed-market stocks, 7–10 year Treasuries, 20+ year Treasuries, US real estate, gold and commodities. It keeps the **3 with the strongest recent trend**, but only if each is beating plain T-bills. It splits money between them so each carries similar risk, and **shrinks everything toward T-bills when markets get violent** (with the current riskier settings, only in very violent markets). Everything else sits in T-bills. That's it. No stock picking, no day trading, no leverage, no shorting.

## The rules (strategy `CORE`)

| Step | Rule | Why | Vault note |
|---|---|---|---|
| 1. When | Last trading day of the month, after the close. Orders go out the next morning. | Monthly is slow enough that costs and tax stay low, fast enough to step aside in long bear markets. | [[07 - Turnover, Capacity, and Trading Costs]] |
| 2. Score | Average of each asset's 3-, 6- and 12-month total return. | Blending three lookbacks avoids betting on one lucky window. | [[02 - Momentum and Trend Following]] |
| 3. Pick | Top 3 scores. | Diversified across asset classes, not inside one. | [[02 - Concentration and Correlation]] |
| 4. Crash filter | A pick must also beat T-bills over the same windows, otherwise its slot goes to T-bills. | "Absolute momentum": the thing that got it out of 2000–02, 2008 and most of 2022. | [[02 - Momentum and Trend Following]] (momentum crashes) |
| 5. Size | Each pick weighted by 1 ÷ its recent volatility (bonds get more money than stocks for the same risk). | Equal risk, not equal money. | [[12 - Factor Exposures and Risk Budgeting]] |
| 6. Cap | If the whole book's expected volatility is above the cap (22% with the current riskier settings, 11.9% with the calmer default), scale it down. No ETF above 80% (60% calmer). Never above 100% invested. | Limits derived from the worst month you can live with. | [[08 - Risk Limits and Escalation]], [[07 - Kelly Criterion and Estimation Error]] |
| 7. Don't fidget | Skip changes smaller than 10 percentage points or €200. | Every unnecessary trade costs spread — and in Italy, 26% tax on any gain. | [[11 - Is the Potential Edge Bigger Than the Costs?]] |

## What it actually buys

Signals come from long US histories (back to 1986). Orders go to the ETFs that suit **the country that taxes you** (`region` in [[02 - Risk Limits]]):

| Asset | `region: us` (US taxpayer) | `region: eu` (Italy/EU taxpayer) |
|---|---|---|
| US stocks | VOO | CSPX `IE00B5BMR087` |
| Developed ex-US stocks | IEFA | XUSE `IE000R4ZNTN3` |
| Treasuries 7–10y | IEF | CBU0 `IE00B3VWN518` |
| Treasuries 20y+ | TLT | IDTL `IE00BSKRJZ44` |
| US real estate | VNQ | IDUP `IE00B1FZSF77` |
| Gold | GLDM | SGLN `IE00B4ND3602` |
| Commodities | PDBC (no K-1 form) | ICOM `IE00BDFL4P12` |
| T-bills / cash | SGOV | IB01 `IE00BGSF1X88` |

> [!warning] Don't mix them up
> A US taxpayer holding the European funds is caught by the PFIC rules (punitive tax). An EU investor can't buy the US funds at all. Check each instrument in your broker before the first live order.

## Every run, in order

1. Download fresh prices (Yahoo, same source your old engine used).
2. **Data checks:** prices older than 4 days, or a >25% one-day jump, block trading on a rebalance day.
3. Value the account. If it is 25% below its peak, **halt** and wait for you (`python3 run.py resume`).
4. If a new month-end signal exists: compute targets → cap → no-trade band → orders.
5. **Pre-trade checks:** only whitelisted ETFs, no order bigger than the account, no selling what isn't held, no overdraft. Any failure means nothing is sent.
6. Execute: paper account, or Interactive Brokers.
7. Write a note in `Bot/Journal/` and update [[00 - Bot Dashboard]], including a "How much could I lose?" table that replays 2008, 2020, 2022 and 2000–02 on today's holdings.

## What it does *not* do

- It does not use the 31,800 notes or the 1,199-company warehouse to pick stocks. Your own strategy lab shows that kind of stock-picking signal is not reliable yet: under an honest test, 80–98% of attempts fail to beat simply holding the stock (see [[05 - Fixes to the Old Engine]]). The library's role is the **rules** — risk limits, sizing, cost discipline, data integrity, crash scenarios — which are all wired in above.
- It does not react inside a month. Very fast crashes (Q4 2018, April 2025) hurt before the month-end signal sees them.
- It does not know about your taxes beyond the backtest estimate. See [[04 - How to Run It]].

Evidence: [[03 - Backtest Report]] · Settings: [[02 - Risk Limits]]
