---
type: research
department: trading
department_color: "#22C55E"
cssclasses:
  - dept-trading
generated: trading-bot
updated: 2026-11-27
tags:
  - type/research
  - department/trading
  - trading-bot
  - day-trading
  - research
---

# 17 - Day Trader Research

The live day trader's exact rules replayed on every session since 2016 for SPY and QQQ (5,482 symbol-days of real 5-minute prices), measured in R (1R = the planned risk on a trade, so +0.10 means each trade earns a tenth of what it risks, on average). Costs of 2 bp per round trip are included.

**Live rules:** 5,352 trades, 48% winners, average **-0.021R**, profit factor 0.96. Exits: 2,281 stops, 1,842 targets, 1,229 at the 15:55 close.

A change only counts if it improves **both** halves of the history (2016-2020 and 2021-now). Anything that helps in one half only is probably luck.

## Targets

| Version | Trades | Win | Avg R | PF | Avg R 2016-20 | Avg R 2021-now | Worst run (R) |
|---|---|---|---|---|---|---|---|
| 1.5x range (live) | 5352 | 48% | -0.021 | 0.96 | -0.074 | +0.021 | -191.4 |
| 1.0x range | 5352 | 54% | -0.048 | 0.89 | -0.087 | -0.017 | -264.5 |
| 2.0x range | 5352 | 44% | -0.008 | 0.99 | -0.065 | +0.039 | -170.8 |
| 3.0x range | 5352 | 42% | +0.007 | 1.01 | -0.048 | +0.052 | -127.8 |
| no target, hold to 15:55 | 5352 | 41% | +0.006 | 1.01 | -0.048 | +0.050 | -152.6 |

## Filters (on the live 1.5x target)

| Filter | Trades | Win | Avg R | PF | Avg R 2016-20 | Avg R 2021-now | Worst run (R) |
|---|---|---|---|---|---|---|---|
| Trend: trade only with the 20-day average | 2887 | 50% | +0.025 | 1.05 | -0.038 | +0.076 | -67.7 |
| Trend: trade only with the 50-day average | 2883 | 49% | +0.005 | 1.01 | -0.043 | +0.045 | -78.3 |
| Skip wide ranges (range > 60% of daily ATR) | 5069 | 47% | -0.022 | 0.96 | -0.073 | +0.018 | -175.9 |
| Skip narrow ranges (range < 20% of daily ATR) | 4429 | 48% | -0.014 | 0.97 | -0.060 | +0.023 | -144.1 |
| Breakout before 10:30 only | 4775 | 48% | -0.014 | 0.97 | -0.063 | +0.023 | -142.6 |
| Breakout after 10:30 only | 577 | 45% | -0.079 | 0.82 | -0.151 | +0.003 | -63.8 |
| Trade with the gap (gap and breakout same way) | 2667 | 48% | -0.004 | 0.99 | -0.047 | +0.030 | -66.2 |
| Skip big gaps (over 1%) | 4710 | 47% | -0.030 | 0.94 | -0.082 | +0.014 | -195.9 |
| Skip high-volatility regimes (20-day vol > 25%) | 4551 | 48% | -0.021 | 0.96 | -0.071 | +0.020 | -158.8 |
| Only high-volatility regimes (20-day vol > 18%) | 1750 | 46% | -0.050 | 0.90 | -0.074 | -0.034 | -101.5 |
| Longs only | 2784 | 50% | +0.002 | 1.00 | -0.024 | +0.024 | -53.4 |
| Shorts only | 2568 | 45% | -0.047 | 0.91 | -0.129 | +0.018 | -154.7 |
| SPY and QQQ break the same way | 4306 | 52% | +0.065 | 1.15 | +0.013 | +0.107 | -38.9 |
| Against yesterday's move (mean reversion) | 2695 | 47% | -0.034 | 0.93 | -0.075 | +0.002 | -119.9 |
| With the 5-day move | 2661 | 49% | -0.002 | 1.00 | -0.048 | +0.037 | -83.8 |

Passes both halves: Trend: trade only with the 20-day average, Trend: trade only with the 50-day average, Skip narrow ranges (range < 20% of daily ATR), Breakout before 10:30 only, Trade with the gap (gap and breakout same way), Longs only, SPY and QQQ break the same way, With the 5-day move

## Combinations that beat either filter alone in both halves

| Version | Trades | Win | Avg R | PF | Avg R 2016-20 | Avg R 2021-now | Worst run (R) |
|---|---|---|---|---|---|---|---|
| Trend: trade only with the 20-day average + Skip narrow ranges (range < 20% of daily ATR) | 2409 | 50% | +0.030 | 1.07 | -0.035 | +0.085 | -62.6 |
| Trend: trade only with the 20-day average + Trade with the gap (gap and breakout same way) | 1668 | 52% | +0.064 | 1.14 | +0.016 | +0.104 | -26.6 |
| Trend: trade only with the 20-day average + SPY and QQQ break the same way | 2341 | 55% | +0.118 | 1.28 | +0.042 | +0.179 | -32.9 |
| Trend: trade only with the 50-day average + Skip narrow ranges (range < 20% of daily ATR) | 2379 | 49% | +0.008 | 1.02 | -0.041 | +0.051 | -66.1 |
| Trend: trade only with the 50-day average + Trade with the gap (gap and breakout same way) | 1635 | 51% | +0.051 | 1.11 | +0.009 | +0.086 | -25.0 |
| Trend: trade only with the 50-day average + SPY and QQQ break the same way | 2340 | 53% | +0.093 | 1.22 | +0.036 | +0.140 | -29.1 |
| Skip narrow ranges (range < 20% of daily ATR) + Breakout before 10:30 only | 3901 | 48% | -0.004 | 0.99 | -0.047 | +0.030 | -108.6 |
| Skip narrow ranges (range < 20% of daily ATR) + Trade with the gap (gap and breakout same way) | 2221 | 48% | -0.003 | 0.99 | -0.044 | +0.031 | -63.5 |
| Breakout before 10:30 only + Trade with the gap (gap and breakout same way) | 2382 | 49% | +0.006 | 1.01 | -0.028 | +0.032 | -44.5 |
| Trade with the gap (gap and breakout same way) + Longs only | 1565 | 51% | +0.033 | 1.07 | +0.004 | +0.057 | -25.7 |
| Trade with the gap (gap and breakout same way) + SPY and QQQ break the same way | 2152 | 53% | +0.093 | 1.21 | +0.052 | +0.125 | -23.1 |
| Trade with the gap (gap and breakout same way) + With the 5-day move | 1354 | 51% | +0.041 | 1.09 | +0.032 | +0.048 | -19.2 |
| SPY and QQQ break the same way + With the 5-day move | 2134 | 53% | +0.101 | 1.23 | +0.052 | +0.141 | -27.1 |

## The pair rule without hindsight

The 'SPY and QQQ break the same way' filter above peeks ahead: at SPY's breakout you may not yet know which way QQQ will go. Here each symbol is entered only after BOTH have broken out the same way, at the next bar after the later breakout - exactly what the live bot could do.

| Version | Trades | Win | Avg R | PF | Avg R 2016-20 | Avg R 2021-now | Worst run (R) |
|---|---|---|---|---|---|---|---|
| Confirmed pair, target 1.5x range (live) | 4305 | 50% | -0.002 | 1.00 | -0.055 | +0.039 | -123.6 |
| Confirmed pair, target 1.0x range | 4305 | 56% | -0.032 | 0.92 | -0.077 | +0.003 | -185.7 |
| Confirmed pair, target 2.0x range | 4305 | 47% | +0.015 | 1.03 | -0.041 | +0.058 | -99.3 |
| Confirmed pair, target 3.0x range | 4305 | 44% | +0.023 | 1.05 | -0.031 | +0.066 | -95.6 |
| Confirmed pair, target no target, hold to 15:55 | 4305 | 43% | +0.023 | 1.05 | -0.033 | +0.067 | -110.6 |
| Confirmed pair + Trend: trade only with the 20-day average | 2360 | 53% | +0.051 | 1.12 | -0.024 | +0.110 | -61.8 |
| Confirmed pair + With the 5-day move | 2134 | 52% | +0.036 | 1.08 | -0.013 | +0.076 | -48.7 |
| Confirmed pair + Trade with the gap (gap and breakout same way) | 2152 | 51% | +0.023 | 1.05 | -0.018 | +0.055 | -52.1 |
| Confirmed pair + Skip narrow ranges (range < 20% of daily ATR) | 3594 | 49% | -0.001 | 1.00 | -0.049 | +0.037 | -109.4 |

## Exits and stops on the rule now live (pair confirmed + 20-day trend)

| Version | Trades | Win | Avg R | PF | Avg R 2016-20 | Avg R 2021-now | Worst run (R) |
|---|---|---|---|---|---|---|---|
| Live rule now, target 1.5x range (live) | 2360 | 53% | +0.051 | 1.12 | -0.024 | +0.110 | -41.3 |
| Live rule now, target 1.5x range (live), stop at the range middle | 2359 | 41% | +0.022 | 1.03 | -0.068 | +0.093 | -94.5 |
| Live rule now, target 1.0x range | 2360 | 58% | +0.011 | 1.03 | -0.039 | +0.052 | -38.3 |
| Live rule now, target 1.0x range, stop at the range middle | 2359 | 46% | -0.032 | 0.94 | -0.091 | +0.016 | -123.6 |
| Live rule now, target 2.0x range | 2360 | 50% | +0.067 | 1.15 | -0.021 | +0.136 | -39.7 |
| Live rule now, target 2.0x range, stop at the range middle | 2359 | 38% | +0.046 | 1.07 | -0.063 | +0.133 | -89.0 |
| Live rule now, target 3.0x range | 2360 | 48% | +0.086 | 1.18 | +0.002 | +0.152 | -33.6 |
| Live rule now, target 3.0x range, stop at the range middle | 2359 | 36% | +0.078 | 1.12 | -0.037 | +0.168 | -79.5 |
| Live rule now, target no target, hold to 15:55 | 2360 | 47% | +0.090 | 1.19 | +0.012 | +0.151 | -39.9 |
| Live rule now, target no target, hold to 15:55, stop at the range middle | 2359 | 36% | +0.086 | 1.13 | -0.026 | +0.174 | -82.4 |

## By year: original rules vs the rules now live

| Year | Original trades | Original avg R | Original total R | Now-live trades | Now-live avg R | Now-live total R |
|---|---|---|---|---|---|---|
| 2016 | 401 | -0.095 | -38.2 | 184 | -0.117 | -21.4 |
| 2017 | 498 | -0.112 | -55.6 | 201 | -0.098 | -19.7 |
| 2018 | 498 | -0.041 | -20.5 | 223 | +0.146 | +32.6 |
| 2019 | 498 | -0.046 | -23.0 | 222 | +0.019 | +4.2 |
| 2020 | 500 | -0.079 | -39.7 | 215 | +0.030 | +6.5 |
| 2021 | 502 | +0.083 | +41.5 | 236 | +0.179 | +42.4 |
| 2022 | 500 | +0.021 | +10.3 | 227 | +0.169 | +38.3 |
| 2023 | 498 | -0.007 | -3.6 | 224 | +0.157 | +35.2 |
| 2024 | 504 | -0.003 | -1.3 | 212 | +0.119 | +25.1 |
| 2025 | 500 | +0.049 | +24.6 | 214 | +0.202 | +43.2 |
| 2026 | 453 | -0.020 | -9.1 | 202 | +0.080 | +16.1 |

## Recommendation

**SPY and QQQ break the same way + With the 5-day move** — keeps 40% of trades; average R +0.052 in 2016-20 and +0.141 in 2021-now (live rules: -0.074 / +0.021).

Back to [[12 - Live Day Trading]] · [[16 - Bot Brain]]
