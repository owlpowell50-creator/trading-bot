"""
broker.py - where orders go.

PaperBroker   (default) a simulated account stored in state/paper_account.json.
              Holdings are tracked in units of each asset's total-return index,
              so dividends are included; every fill pays half the assumed
              spread/slippage on each side. Fills use the last available close
              (the same prices the signal used) - no hand-typed fill prices.
AlpacaBroker  Alpaca (US). Plain HTTPS, no extra packages. Keys are read from
              ~/.config/tradingbot/alpaca.json  {"key_id": "...", "secret": "..."}
              or the APCA_API_KEY_ID / APCA_API_SECRET_KEY environment variables -
              never from vault notes. alpaca-paper uses the free paper account.
IBKRBroker    Interactive Brokers via TWS / IB Gateway and the `ib_async`
              library (pip3 install ib_async). US ETFs by symbol, UCITS by ISIN.
              Port 7497 = paper account, 7496 = live. Live orders are refused
              unless the Risk Limits note says live_trading_confirmed: true.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import os
import time
import urllib.error
import urllib.request

from .data import ROOT

STATE = ROOT / "state"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PaperBroker:
    kind = "paper"

    def __init__(self, capital: float, cost_bps: float, path: Path = STATE / "paper_account.json"):
        self.path = path
        self.cost = cost_bps / 10000.0
        if path.exists():
            self.acct = json.loads(path.read_text())
        else:
            self.acct = {"created": now(), "starting_capital": capital,
                         "units": {}, "cash_value": capital, "fills": []}

    # cash outside the T-bill ETF is held as plain cash (no interest)
    def values(self, prices: Dict[str, float]) -> Dict[str, float]:
        v = {a: u * prices[a] for a, u in self.acct["units"].items() if u > 0}
        cash = self.acct["cash_value"]
        if abs(cash) > 0.005:
            v["CASH"] = v.get("CASH", 0.0) + cash
        return v

    def equity(self, prices: Dict[str, float]) -> float:
        return sum(self.values(prices).values())

    def execute(self, orders: List[dict], prices: Dict[str, float], date: str) -> List[dict]:
        fills = []
        for o in orders:
            a, side, value = o["asset"], o["side"], o["value"]
            px = prices[a]
            held = self.acct["units"].get(a, 0.0)
            if side == "BUY":
                fee = value * self.cost            # spread + slippage + commission
                units = (value - fee) / px
                self.acct["units"][a] = held + units
                self.acct["cash_value"] -= value
            else:
                # for CASH, plain uninvested cash needs no sale - only T-bill ETF units are sold
                units = min(value / px, held)
                if units <= 1e-12:
                    continue
                fee = units * px * self.cost
                self.acct["units"][a] = held - units
                self.acct["cash_value"] += units * px - fee
            f = {"date": date, "asset": a, "side": side, "units": units, "price": px,
                 "value": units * px, "fee": fee, "at": now(), "environment": "PAPER"}
            fills.append(f)
            self.acct["fills"].append(f)
        self.acct["units"] = {a: u for a, u in self.acct["units"].items() if u > 1e-12}
        return fills

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.acct, indent=1))
        tmp.replace(self.path)


class IBKRBroker:
    """Thin wrapper around ib_async. Equity and positions come from the real
    account; orders are market orders on the resolved UCITS contracts."""
    kind = "ibkr"

    def __init__(self, cfg: dict, instruments: Dict[str, dict]):
        try:
            from ib_async import IB  # type: ignore
        except ImportError:
            try:
                from ib_insync import IB  # type: ignore
            except ImportError as e:
                raise RuntimeError("Install the IBKR library first:  pip3 install ib_async") from e
        live = cfg["mode"] == "ibkr-live"
        if live and not cfg.get("live_trading_confirmed"):
            raise RuntimeError("mode is ibkr-live but live_trading_confirmed is false in "
                               "'02 - Risk Limits' - refusing to trade real money.")
        if not live and cfg["broker_port"] in (7496, 4001):
            raise RuntimeError("mode is ibkr-paper but the port is a LIVE port (7496/4001).")
        self.cfg = cfg
        self.instruments = instruments
        self.ib = IB()
        self.ib.connect(cfg["broker_host"], int(cfg["broker_port"]), clientId=int(cfg["broker_client_id"]),
                        timeout=20)
        self._contracts: Dict[str, object] = {}

    def contract(self, asset: str):
        if asset in self._contracts:
            return self._contracts[asset]
        from ib_async import Contract, Stock  # type: ignore
        ins = self.instruments[asset]
        if ins.get("isin"):
            c = Contract(secIdType="ISIN", secId=ins["isin"], exchange="SMART", currency=ins["currency"])
        else:
            c = Stock(ins["symbol"], "SMART", ins["currency"])
        details = self.ib.reqContractDetails(c)
        if not details:
            raise RuntimeError(f"IBKR could not find {ins['symbol']} ({ins['isin']}) in {ins['currency']}")
        self._contracts[asset] = details[0].contract
        return details[0].contract

    def account_summary(self) -> Dict[str, float]:
        vals = {v.tag: v for v in self.ib.accountSummary()}
        return {"NetLiquidation": float(vals["NetLiquidation"].value),
                "TotalCashValue": float(vals["TotalCashValue"].value),
                "currency": vals["NetLiquidation"].currency}

    def values(self) -> Dict[str, float]:
        """Market value per asset class in the account's base currency."""
        by_con = {}
        for a in self.instruments:
            try:
                by_con[self.contract(a).conId] = a
            except RuntimeError:
                continue
        out: Dict[str, float] = {}
        for p in self.ib.portfolio():
            a = by_con.get(p.contract.conId)
            if a:
                out[a] = out.get(a, 0.0) + float(p.marketValue)
        cash = self.account_summary()["TotalCashValue"]
        out["CASH"] = out.get("CASH", 0.0) + cash
        return out

    def execute(self, orders: List[dict], date: str) -> List[dict]:
        from ib_async import MarketOrder  # type: ignore
        fills = []
        for o in orders:
            c = self.contract(o["asset"])
            [tk] = self.ib.reqTickers(c)
            px = tk.marketPrice() or tk.close
            if not px or px != px:
                raise RuntimeError(f"no price for {o['asset']} - order not sent")
            qty = int(o["value"] / px)
            if o["side"] == "SELL":
                held = sum(p.position for p in self.ib.positions() if p.contract.conId == c.conId)
                qty = min(qty, int(held))
            if qty <= 0:
                continue
            trade = self.ib.placeOrder(c, MarketOrder(o["side"], qty))
            self.ib.sleep(2)
            for _ in range(60):
                if trade.isDone():
                    break
                self.ib.sleep(1)
            fills.append({"date": date, "asset": o["asset"], "side": o["side"], "units": qty,
                          "price": trade.orderStatus.avgFillPrice, "status": trade.orderStatus.status,
                          "value": qty * (trade.orderStatus.avgFillPrice or px), "at": now(),
                          "environment": self.cfg["mode"].upper()})
        return fills

    def close(self):
        self.ib.disconnect()


class AlpacaBroker:
    """Alpaca REST API v2. Market orders in dollar amounts ('notional'), day
    orders only. Run it during US market hours (the scheduler does) so sells
    fill before the buys they pay for. Sells never exceed what is held - on
    Alpaca, selling a symbol you do not own would open a SHORT position."""
    kind = "alpaca"
    KEYFILE = Path.home() / ".config" / "tradingbot" / "alpaca.json"

    def __init__(self, cfg: dict, instruments: Dict[str, dict], http=None):
        live = cfg["mode"] == "alpaca-live"
        if live and not cfg.get("live_trading_confirmed"):
            raise RuntimeError("mode is alpaca-live but live_trading_confirmed is false in "
                               "'02 - Risk Limits' - refusing to trade real money.")
        self.base = "https://api.alpaca.markets" if live else "https://paper-api.alpaca.markets"
        self.cfg = cfg
        self.instruments = instruments
        self.by_symbol = {v["symbol"]: a for a, v in instruments.items()}
        self.http = http or self._http
        key, sec = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
        if not (key and sec) and self.KEYFILE.exists():
            k = json.loads(self.KEYFILE.read_text())
            key, sec = k.get("key_id"), k.get("secret")
        if not (key and sec) and http is None:
            raise RuntimeError(f"Alpaca keys not found. Put them in {self.KEYFILE} as "
                               '{"key_id": "...", "secret": "..."}')
        self.headers = {"APCA-API-KEY-ID": key or "", "APCA-API-SECRET-KEY": sec or "",
                        "Content-Type": "application/json"}

    def _http(self, method: str, path: str, body: Optional[dict] = None):
        req = urllib.request.Request(self.base + path, method=method, headers=self.headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                txt = r.read().decode()
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Alpaca {method} {path}: HTTP {e.code} {e.read().decode()[:300]}") from e

    def positions(self) -> Dict[str, dict]:
        return {p["symbol"]: p for p in self.http("GET", "/v2/positions")}

    def values(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for sym, p in self.positions().items():
            a = self.by_symbol.get(sym)
            if a:
                out[a] = out.get(a, 0.0) + float(p["market_value"])
        cash = float(self.http("GET", "/v2/account")["cash"])
        out["CASH"] = out.get("CASH", 0.0) + cash
        return out

    def _wait(self, oid: str, seconds: int = 90) -> dict:
        o = {}
        for _ in range(seconds // 3):
            o = self.http("GET", f"/v2/orders/{oid}")
            if o.get("status") in ("filled", "canceled", "expired", "rejected"):
                break
            time.sleep(3)
        return o

    def execute(self, orders: List[dict], date: str) -> List[dict]:
        clock = self.http("GET", "/v2/clock")
        if not clock.get("is_open"):
            raise RuntimeError("US market is closed - Alpaca orders not sent (run during market hours)")
        fills = []
        for o in orders:                       # sells come first (risk.plan_orders sorts them)
            sym = self.instruments[o["asset"]]["symbol"]
            if o["side"] == "SELL":
                pos = self.positions().get(sym)
                if not pos:
                    continue                   # e.g. CASH held as plain cash: nothing to sell
                held_qty, held_val = float(pos["qty"]), float(pos["market_value"])
                if held_qty <= 0:
                    continue
                if o["value"] >= 0.98 * held_val:
                    qty = held_qty             # close it fully (no dust, never short)
                else:
                    qty = round(held_qty * o["value"] / held_val, 6)
                body = {"symbol": sym, "qty": str(qty), "side": "sell", "type": "market",
                        "time_in_force": "day"}
            else:
                body = {"symbol": sym, "notional": f"{o['value'] * 0.995:.2f}", "side": "buy",
                        "type": "market", "time_in_force": "day"}   # 0.5% buffer for slippage
            sent = self.http("POST", "/v2/orders", body)
            done = self._wait(sent["id"])
            fills.append({"date": date, "asset": o["asset"], "side": o["side"],
                          "units": float(done.get("filled_qty") or 0),
                          "price": float(done.get("filled_avg_price") or 0),
                          "value": float(done.get("filled_qty") or 0) * float(done.get("filled_avg_price") or 0),
                          "status": done.get("status"), "order_id": sent["id"], "at": now(),
                          "environment": self.cfg["mode"].upper()})
            if done.get("status") != "filled":
                raise RuntimeError(f"{sym} order {sent['id']} ended as {done.get('status')} - stopping; "
                                   "check Alpaca before the next run")
        return fills

    def close(self):
        pass
