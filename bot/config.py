"""
config.py - the bot's settings live in an Obsidian note you can edit:
    Bot/02 - Risk Limits.md   (the YAML block at the top)

The volatility cap is derived exactly as in the vault note
"Independent Risk Committee/08 - Risk Limits and Escalation":
    monthly sigma cap = worst tolerable 1-in-100 month / 2.326
    annual sigma cap  = monthly cap * sqrt(12)
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict

from .data import ROOT

NOTE = ROOT / "02 - Risk Limits.md"

DEFAULTS: Dict[str, Any] = {
    "region": "us",                # us = US-listed ETFs (US tax resident) | eu = UCITS ETFs (Italy/EU)
    "account_type": "taxable",     # us only: taxable | ira  (IRA/Roth: no tax on the bot's trades)
    "us_short_term_rate": 0.29,    # federal + state on gains held < 1 year and on interest
    "us_long_term_rate": 0.20,     # federal + state on gains held > 1 year and qualified dividends
    "mode": "paper",               # paper | alpaca-paper | alpaca-live | ibkr-paper | ibkr-live
    "strategy": "CORE",
    "capital": 10000.0,            # starting paper capital (USD-equivalent)
    "worst_month_loss": 0.08,      # 1-in-100 bad month you can live with
    "max_single_asset": 0.60,      # no ETF above this share of the account
    "max_drawdown_halt": 0.25,     # stop and ask you if equity falls this far from its peak
    "no_trade_band": 0.10,         # leave a holding alone unless off target by more than this
    "min_trade_value": 200.0,      # never send an order smaller than this
    "cost_bps": 10.0,              # assumed spread + commission + slippage per unit traded
    "data_max_age_days": 4,
    "broker_host": "127.0.0.1",
    "broker_port": 7497,           # IBKR: 7497 paper TWS, 7496 live TWS (4002/4001 Gateway)
    "broker_client_id": 17,
    "live_trading_confirmed": False,
}

# What the bot actually buys. Signals always come from the long US histories.
#  us: US-domiciled ETFs. For a US tax resident, European UCITS funds are
#      PFICs (punitive tax + Form 8621), so never use the eu list in the US.
#  eu: UCITS ETFs - US-listed ETFs are not sold to EU retail investors.
# VERIFY each instrument in your broker before going live.
US_INSTRUMENTS = {
    "US":        {"name": "Vanguard S&P 500 ETF", "symbol": "VOO", "isin": "", "currency": "USD"},
    "INTL":      {"name": "iShares Core MSCI EAFE ETF", "symbol": "IEFA", "isin": "", "currency": "USD"},
    "BONDS":     {"name": "iShares 7-10 Year Treasury Bond ETF", "symbol": "IEF", "isin": "", "currency": "USD"},
    "LONGBONDS": {"name": "iShares 20+ Year Treasury Bond ETF", "symbol": "TLT", "isin": "", "currency": "USD"},
    "REIT":      {"name": "Vanguard Real Estate ETF", "symbol": "VNQ", "isin": "", "currency": "USD"},
    "GOLD":      {"name": "SPDR Gold MiniShares", "symbol": "GLDM", "isin": "", "currency": "USD"},
    "COMMOD":    {"name": "Invesco Optimum Yield Diversified Commodity No K-1 ETF", "symbol": "PDBC", "isin": "", "currency": "USD"},
    "CASH":      {"name": "iShares 0-3 Month Treasury Bond ETF", "symbol": "SGOV", "isin": "", "currency": "USD"},
}

INSTRUMENTS = {
    "US":        {"name": "iShares Core S&P 500 UCITS (Acc)", "symbol": "CSPX", "isin": "IE00B5BMR087", "currency": "USD"},
    "INTL":      {"name": "iShares MSCI World ex-USA UCITS (Acc)", "symbol": "XUSE", "isin": "IE000R4ZNTN3", "currency": "EUR"},
    "BONDS":     {"name": "iShares $ Treasury 7-10yr UCITS (Acc)", "symbol": "CBU0", "isin": "IE00B3VWN518", "currency": "USD"},
    "LONGBONDS": {"name": "iShares $ Treasury 20+yr UCITS (Dist)", "symbol": "IDTL", "isin": "IE00BSKRJZ44", "currency": "USD"},
    "REIT":      {"name": "iShares US Property Yield UCITS (Dist)", "symbol": "IDUP", "isin": "IE00B1FZSF77", "currency": "USD"},
    "GOLD":      {"name": "iShares Physical Gold ETC", "symbol": "SGLN", "isin": "IE00B4ND3602", "currency": "USD"},
    "COMMOD":    {"name": "iShares Diversified Commodity Swap UCITS", "symbol": "ICOM", "isin": "IE00BDFL4P12", "currency": "USD"},
    "CASH":      {"name": "iShares $ Treasury 0-1yr UCITS (Acc)", "symbol": "IB01", "isin": "IE00BGSF1X88", "currency": "USD"},
}


def _parse_value(v: str):
    v = v.split(" #")[0].strip().strip('"').strip("'")
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    try:
        return int(v) if v.lstrip("-").isdigit() else float(v)
    except ValueError:
        return v


def read_frontmatter(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith((" ", "-", "#")):
            k, v = line.split(":", 1)
            if v.strip():
                out[k.strip()] = _parse_value(v)
    return out


EU_INSTRUMENTS = INSTRUMENTS


def instruments(cfg: Dict[str, Any]) -> Dict[str, dict]:
    return US_INSTRUMENTS if str(cfg.get("region", "us")).lower() == "us" else EU_INSTRUMENTS


def load(path: Path = NOTE) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in read_frontmatter(path).items() if k in DEFAULTS})
    cfg["vol_cap"] = vol_cap(cfg["worst_month_loss"])
    cfg["instruments"] = instruments(cfg)
    return cfg


def vol_cap(worst_month_loss: float) -> float:
    return worst_month_loss / 2.326 * math.sqrt(12)
