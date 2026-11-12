---
type: research
department: quant
department_color: "#06B6D4"
cssclasses:
  - dept-quant
tags:
  - type/research
  - trading-bot
  - model-risk
---
# 09 - Upgrades Tested (2026-11-12)

The rule for any upgrade: decide it **before** looking at results, then keep it only if it improves return per unit of risk (Sharpe) without a worse worst fall. Each idea also had to hold up in both halves of the history (1997–2011 and 2012–2026). Every extra rule that only fits the past makes the future worse. See [[07 - Model Risk and Assumption Failure]].

All results: 1997–2026, costs included, current riskier settings.

| Version | Return/yr | Sharpe | Worst fall | Trades/yr | Verdict |
|---|---|---|---|---|---|
| **CORE (running)** | **10.1%** | **0.97** | **−17.6%** | 5.6 | ✅ keep |
| Ensemble: average of 12 CORE variants | 9.0% | 0.92 | −16.0% | 9.9 | ❌ less return, barely safer |
| CORE + crash brake (sell below 200-day average mid-month) | 8.6% | 0.89 | −17.9% | 11.3 | ❌ whipsaw |
| CORE + crash brake, 150 days | 7.7% | 0.83 | −18.4% | 14.5 | ❌ |
| CORE + crash brake, 100 days | 6.0% | 0.71 | −17.0% | 19.2 | ❌ |
| More risk: tolerate 2 assets instead of 3 | 9.8% | — | −27.2% | — | ❌ more risk, no more return |
| More risk: drop bonds | 9.5% | — | −19.2% | — | ❌ |

**Why the crash brake fails:** most dips below the average recover within days. Selling and buying back costs more than the crashes it avoids, and the month-end crash filter already handles the slow bear markets that do real damage.

## What was added instead (things that make it *work* better, not *guess* better)

- **Alerts:** every trade, warning, block, halt or crash opens a GitHub Issue. GitHub emails you, and the GitHub phone app sends a notification.
- **Red run on problems:** a blocked, halted or crashed run shows red in the Actions tab.
- **Self-tests before every run:** if the code is broken, the run stops before touching the account.

## The biggest real-world levers (bigger than any rule change)

1. **Account type:** in an IRA/Roth it keeps ~10%/yr. In a taxable US account, ~7%.
2. **Costs:** commission-free broker, ETFs with tight spreads (already chosen).
3. **Not overriding it:** the backtest only counts if the rules are followed in the bad months too.
4. **Keeping it running:** handled by GitHub plus the alerts above.

Back to [[00 - Bot Dashboard]] · Evidence: [[03 - Backtest Report]]
