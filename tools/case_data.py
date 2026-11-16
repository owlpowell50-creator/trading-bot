#!/usr/bin/env python3
"""Fetch the real market and SEC data used by the vault's case notes (runs on GitHub Actions)."""
import gzip, json, os, time, urllib.request
from datetime import date, datetime, timezone

UA_SEC = os.environ.get("SEC_USER_AGENT") or "TradingBotResearch admin@tradingbot-research.example"
UA_WEB = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

PRICES = {   # ticker: (start, end, interval)
    "META": ("2022-01-20", "2022-02-15", "1d"),
    "NVDA": ("2021-11-01", "2023-01-31", "1d"), "AMD": ("2021-11-01", "2023-01-31", "1d"),
    "AMAT": ("2021-11-01", "2023-01-31", "1d"), "LRCX": ("2021-11-01", "2023-01-31", "1d"),
    "MU": ("2021-11-01", "2023-01-31", "1d"), "SOXX": ("2021-11-01", "2023-01-31", "1d"),
    "SPY": ("2021-11-01", "2023-01-31", "1d"),
    "GME": ("2020-12-15", "2021-03-15", "1d"),
    "LQD": ("2020-02-01", "2020-04-30", "1d"), "HYG": ("2020-02-01", "2020-04-30", "1d"),
    "BIIB": ("2019-03-01", "2019-04-15", "1d"),
    "XOM": ("2025-01-01", "2026-11-14", "1d"),
}
MONTHLY = ["COST", "NUE", "RIVN", "CVNA", "FLG", "EG", "MU", "TGT", "BIIB", "SPY"]
SEC_TICKERS = ["COST", "NUE", "RIVN", "CVNA", "FLG", "EG", "MU", "TGT", "BIIB"]
ANNUAL = {"10-K", "10-K/A", "20-F", "10-KT"}


def get(url, ua, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                return {"error": str(e)}
            time.sleep(2 * (k + 1))


def ts(d):
    return int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp())


def yahoo(t, a, b, iv):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1={ts(a)}&period2={ts(b) + 86400}"
         f"&interval={iv}&events=div%2Csplit&includeAdjustedClose=true")
    j = get(u, UA_WEB)
    try:
        r = j["chart"]["result"][0]
        q = r["indicators"]["quote"][0]
        adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
        rows = []
        for i, x in enumerate(r["timestamp"]):
            rows.append({"date": datetime.fromtimestamp(x, timezone.utc).date().isoformat(),
                         "open": q["open"][i], "high": q["high"][i], "low": q["low"][i], "close": q["close"][i],
                         "volume": q["volume"][i], "adjclose": adj[i] if adj else None})
        return {"rows": rows, "events": r.get("events", {})}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{e}: {str(j)[:200]}"}


def sec_annual(cik):
    j = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", UA_SEC)
    if "facts" not in j:
        return {"error": j.get("error")}
    out = {"entity": j.get("entityName")}
    for tax in ("us-gaap",):
        for c, node in j["facts"].get(tax, {}).items():
            for unit, obs in (node.get("units") or {}).items():
                by = {}
                for o in obs:
                    if o.get("form") not in ANNUAL or not o.get("end"):
                        continue
                    if o.get("start"):
                        d = (date.fromisoformat(o["end"]) - date.fromisoformat(o["start"])).days
                        if not 330 <= d <= 400:
                            continue
                    p = by.get(o["end"])
                    if p is None or (o.get("filed") or "") >= (p.get("filed") or ""):
                        by[o["end"]] = o
                if by:
                    out[c] = {"unit": unit, "vals": [[e, by[e]["val"], by[e].get("fy"), by[e].get("filed")]
                                                     for e in sorted(by)][-8:]}
    return out


def main():
    out = {"prices": {}, "monthly": {}, "sec": {}, "fetched": datetime.now(timezone.utc).isoformat()}
    for t, (a, b, iv) in PRICES.items():
        out["prices"][t] = yahoo(t, a, b, iv)
        time.sleep(0.5)
    for t in MONTHLY:
        out["monthly"][t] = yahoo(t, "2016-01-01", date.today().isoformat(), "1mo")
        time.sleep(0.5)
    tick = get("https://www.sec.gov/files/company_tickers.json", UA_SEC)
    m = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in tick.values()} if "error" not in tick else {}
    for t in SEC_TICKERS:
        cik = m.get(t)
        out["sec"][t] = sec_annual(cik) if cik else {"error": "cik not found"}
        out["sec"][t]["cik"] = cik
        time.sleep(0.3)
    with gzip.open("case_data.json.gz", "wt") as f:
        json.dump(out, f)
    print({k: [t for t, v in out[k].items() if "error" in v] for k in ("prices", "monthly", "sec")})


if __name__ == "__main__":
    main()
