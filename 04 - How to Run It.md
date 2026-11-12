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
# 04 - How to Run It

Everything lives in `Desktop/Trading bot/trading bot/Bot/`. It needs only the Python 3 that already ran your old engine. No extra packages are needed for paper trading.

## First run (5 minutes)

Open **Terminal** and paste:

```bash
cd ~/Desktop/"Trading bot"/"trading bot"/Bot
python3 run.py test            # 16 self-tests, should end in OK
python3 run.py update-data     # fresh prices from Yahoo
python3 run.py signal          # what it wants to hold right now
python3 run.py daily           # first paper trade + journal note
```

Then open [[00 - Bot Dashboard]] in Obsidian.

## The one-month trial (running now)

A fresh 10,000 paper account started on **2026-11-12** with the riskier settings. Every run adds a line to [[06 - One-Month Trial]], comparing the bot with simply buying the S&P 500 on the same day. Start a new one any time with `python3 run.py start-trial`.

## Commands

| Command | What it does |
|---|---|
| `python3 run.py daily` | The scheduled job: download → check → rebalance if a new month-end signal exists → write notes |
| `python3 run.py daily --dry-run` | Same, but sends nothing |
| `python3 run.py signal` | Shows today's target. Changes nothing |
| `python3 run.py status` | Account, holdings, drawdown |
| `python3 run.py backtest` | Re-runs 1997–today with your current settings and rewrites [[03 - Backtest Report]] |
| `python3 run.py resume` | Clears a drawdown halt after you've looked at what happened |
| `python3 run.py test` | Self-tests: no look-ahead, costs charged, tax rules, risk blocks, paper accounting |

## Run it automatically every weekday

```bash
bash install_schedule.sh
```

This installs a macOS LaunchAgent that runs `daily` every weekday at **10:05 New York time** (35 minutes after the US open), converted to your Mac's clock. For example, that's 16:05 in Rome or 07:05 in California. Running after the open matters for real brokers: sells fill before the buys they pay for. If the Mac was asleep, it runs when it wakes. Logs go to `Bot/logs/`. To remove it: `bash install_schedule.sh --remove`.

> [!warning] macOS privacy blocks background jobs on the Desktop
> The vault is on your Desktop, which macOS protects. If `logs/daily.err` says *Operation not permitted*: open System Settings → Privacy & Security → **Full Disk Access**, click +, press Cmd+Shift+G, and paste the Python path the installer printed. Alternatively, move the vault out of Desktop and run the installer again.

On most days the bot just checks data and writes "HOLD". It trades in the first days of each month.

## Paper → broker paper → real money (in the US)

1. **Paper**: what's running now.
2. **Alpaca paper account** (free, US):
   - Sign up at alpaca.markets and create **paper** API keys.
   - Save them on your Mac (not in the vault): `mkdir -p ~/.config/tradingbot` and put `{"key_id": "PK...", "secret": "..."}` in `~/.config/tradingbot/alpaca.json`.
   - Set `mode: alpaca-paper` and run `python3 run.py daily --dry-run`.
3. **Real money**: `mode: alpaca-live` with live keys and `live_trading_confirmed: true`.
   - **Use an IRA or Roth IRA if you can.** In the backtest the bot keeps 9.8%/yr there, vs 7.0%/yr in a taxable account (short-term gains and bond interest are taxed every year).
   - A Roth IRA needs US earned income to contribute.

Interactive Brokers works too, as below (with `region: us`, it looks up ETFs by symbol).

## Paper → IBKR paper → real money

Do these in order. Don't skip ahead.

1. **Paper (now).** Leave `mode: paper` for at least **2–3 month-ends**. Check that the journal entries make sense and the dashboard equity moves the way the markets moved.
2. **Interactive Brokers paper account.**
   - Open an IBKR account (it works for Italian residents) and enable its free paper account.
   - Install **IB Gateway** or TWS. Log into the *paper* account, then go to Settings → API → enable "ActiveX and Socket Clients" with port **7497** (TWS) or **4002** (Gateway).
   - `pip3 install ib_async`
   - In [[02 - Risk Limits]] set `mode: ibkr-paper` and the matching `broker_port`.
   - `python3 run.py daily --dry-run` — confirm it finds all 8 ETFs by ISIN and plans sensible orders.
   - Then let it run for at least one month-end.
3. **Real money.** Only when steps 1–2 have run cleanly:
   - Start with an amount you can afford to see fall by a third.
   - Log Gateway/TWS into the *live* account on port 7496/4001.
   - Set `mode: ibkr-live`, `broker_port: 7496` and `live_trading_confirmed: true`.
   - The bot refuses live trading if any of these don't match.
   - Read each journal note for the first few months.

> [!important] What the bot can't protect you from
> A flash crash in the middle of a month. A broker outage. A wrong ISIN (checked, but not by a human). Prices from Yahoo being wrong (checked for staleness and jumps, but it's still an unofficial feed). Your Mac being off on the first trading day of the month (it catches up on the next run).

## Taxes in the US — read before going live

- **Which country taxes you decides `region`, not where you physically are.** On a student visa you can stay a "nonresident alien" for US tax for years, and Italy may still consider you resident. Sort this out first; it changes which ETFs you're allowed to hold sensibly.
- In a taxable US account: gains on holdings under 1 year are taxed as ordinary income, over 1 year at long-term rates, and dividends and interest every year. Losses offset gains and carry forward. Set your rates as `us_short_term_rate` / `us_long_term_rate`. If your income is low, your long-term rate may be 0%.
- In an IRA / Roth IRA: no tax on the bot's trades.

## Taxes in Italy — read before going live

- **IBKR is a foreign broker, so you're in the *regime dichiarativo*.** You report and pay tax yourself in your annual return (Modello Redditi: ETF gains in quadro RM, losses and ETC gains in quadro RT), and you declare the account in **quadro RW** (IVAFE on the value).
- **ETF gains are *redditi di capitale*, taxed at 26%. ETF losses are *redditi diversi*, which can't offset ETF gains.** A strategy that switches often realises gains every year and can't use its losses. That's why the backtest shows CORE at about **7.5%/yr after tax vs 9.8% before**, while buy-and-hold S&P 500 loses less to tax (it never sells).
- Gold here is an **ETC**, whose gains *can* be offset by banked losses. The backtest models this.
- Get a *commercialista* to confirm before you trade real money. The backtest's tax model is simplified.

## If something breaks

| Symptom | Fix |
|---|---|
| Journal says **BLOCKED** — data problems | Run `python3 run.py update-data`. If Yahoo is down, wait a day: the bot retries every run and acts on the same month-end signal once data is fresh. |
| **HALTED** | The account fell more than `max_drawdown_halt` from its peak. Read the last journals, decide, then `python3 run.py resume`. |
| IBKR "could not find … by ISIN" | Search that ISIN in TWS. If the listing changed, update `INSTRUMENTS` in `bot/config.py`. |
| You change settings | Run `python3 run.py backtest` so [[03 - Backtest Report]] reflects them. |
