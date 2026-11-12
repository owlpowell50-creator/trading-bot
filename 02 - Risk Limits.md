---
type: bot-config
department: risk
department_color: "#EF4444"
cssclasses:
  - dept-risk
tags:
  - type/bot-config
  - department/risk
  - trading-bot
region: us                   # us = US ETFs (VOO, IEF...) if the US taxes you | eu = UCITS ETFs if Italy/EU taxes you
account_type: taxable        # us only, for the report: taxable | ira  (run it in an IRA/Roth if you can)
us_short_term_rate: 0.29     # your federal + state rate on short-term gains and interest
us_long_term_rate: 0.20      # your federal + state rate on long-term gains and qualified dividends
mode: alpaca-paper                  # paper | alpaca-paper | alpaca-live | ibkr-paper | ibkr-live
strategy: CORE               # CORE (recommended) | GEM | TREND | SPY-TREND | 60/40 | SPY
capital: 10000               # starting PAPER capital
worst_month_loss: 0.15       # the 1-in-100 bad month you can live with -> vol cap (0.15 = 22%, riskier; 0.08 = 11.9% default)
max_single_asset: 0.80       # no single ETF above this share of the account (riskier; default 0.60)
max_drawdown_halt: 0.25      # if the account falls this far from its peak the bot stops and waits for you
no_trade_band: 0.10          # leave a holding alone unless it is this far off target (saves cost and tax)
min_trade_value: 200         # never send an order smaller than this
cost_bps: 10                 # assumed spread + commission + slippage per side, in basis points
data_max_age_days: 4         # refuse to trade on prices older than this
broker_host: 127.0.0.1
broker_port: 7497            # IBKR TWS: 7497 paper, 7496 live  (IB Gateway: 4002 paper, 4001 live)
broker_client_id: 17
live_trading_confirmed: false   # must be true AND a *-live mode before real money is touched
---
# 02 - Risk Limits (the bot's settings)

**Edit the block above to change how the bot behaves.** The bot reads it at the start of every run. Nothing else needs touching.

## Where each number comes from

| Setting | Rule | Vault source |
|---|---|---|
| `worst_month_loss` | Volatility cap = worst month ÷ 2.326 × √12. With 8% this is **11.9% a year**. The bot shrinks positions (rest to T-bills) when its expected volatility is above the cap. | [[08 - Risk Limits and Escalation]] |
| No leverage | Target weights can never add up to more than 100%. Kelly sizing on noisy estimates says bet *less* than the optimum, never more. | [[07 - Kelly Criterion and Estimation Error]] |
| `max_single_asset` | Concentration limit per ETF. | [[02 - Concentration and Correlation]] |
| `max_drawdown_halt` | A **pause for human review**, not a panic sale. The strategy's own crash filter does the selling; this stops the bot if something is going wrong that the rules did not foresee. Clear it with `python3 run.py resume`. | [[05 - Drawdowns and Recovery]], [[14 - Incident Escalation and Operational Risk]] |
| `no_trade_band`, `min_trade_value` | Don't trade when the expected benefit is smaller than the cost — and in Italy every trim of a winning ETF triggers 26% tax. | [[11 - Is the Potential Edge Bigger Than the Costs?]] |
| `data_max_age_days` + 25% one-day jump check | Stale or broken prices block trading on a rebalance day. | [[11 - Data Sources and Integrity]] |
| Scenario table in every journal | Past crashes replayed on today's holdings. | [[13 - How Much Could I Lose?]] |

## Choosing `worst_month_loss`

| You can live with a bad month of | Vol cap | What it means |
|---|---|---|
| 5% | 7.4% | Very defensive; more time in T-bills |
| 8% | 11.9% | The original, calmer setting |
| 12% | 17.9% | |
| **15% (now set — riskier)** | **22.3%** | With 80% max per ETF. Backtest: 10.1%/yr vs 9.8%, same −17.6% worst fall, bigger single bets |

Changing it changes the evidence: re-run `python3 run.py backtest` afterwards so [[03 - Backtest Report]] matches your settings.

## Region — which ETFs it buys

| | `region: us` | `region: eu` |
|---|---|---|
| Use when | the **US** taxes you (US resident for tax) | **Italy/EU** taxes you |
| Buys | VOO, IEFA, IEF, TLT, VNQ, GLDM, PDBC, SGOV | CSPX, XUSE, CBU0, IDTL, IDUP, SGLN, ICOM, IB01 |
| Why not the other list | European UCITS funds are PFICs for US taxpayers (punitive tax + Form 8621) | US-listed ETFs can't be sold to EU retail investors |

Being *physically* in America isn't what matters — **which country taxes you** is. On a student visa you can stay non-resident for US tax for years. Check before going live.

## Modes

- `paper` — simulated account in `Bot/state/`. Uses real prices, charges costs, no broker needed. **Start here.**
- `alpaca-paper` / `alpaca-live` — Alpaca (US broker, simple API, free paper account). Keys go in `~/.config/tradingbot/alpaca.json`, never in a note.
- `ibkr-paper` / `ibkr-live` — Interactive Brokers through TWS/IB Gateway.
- Any `-live` mode is refused unless `live_trading_confirmed: true`. See [[04 - How to Run It]].
