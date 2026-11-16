#!/usr/bin/env python3
"""
Download real reported financials for every company page in the vault from the
SEC (companyfacts + submissions APIs) and save a compact summary per company.

Runs on GitHub Actions (the SEC is not reachable from the research sandbox).
  python tools/sec_fundamentals.py tools/ciks.tsv out.jsonl.gz [--limit N]

Rate: stays under the SEC's 10 requests/second limit.
"""
import gzip
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

UA = "TradingBotResearch github.com/owlpowell50-creator/trading-bot"

# XBRL concept -> standard label (same mapping as Company/_build/statement_analysis.py)
LINES = {
    "Revenues": "Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
    "SalesRevenueNet": "Revenue", "RevenuesNetOfInterestExpense": "Revenue",
    "RegulatedAndUnregulatedOperatingRevenue": "Revenue", "ElectricUtilityRevenue": "Revenue",
    "OilAndGasRevenue": "Revenue", "Revenue": "Revenue", "RevenueFromContractsWithCustomers": "Revenue",
    "CostOfRevenue": "Cost of revenue", "CostOfGoodsAndServicesSold": "Cost of revenue",
    "GrossProfit": "Gross profit",
    "OperatingIncomeLoss": "Operating income", "ProfitLossFromOperatingActivities": "Operating income",
    "ResearchAndDevelopmentExpense": "R&D expense",
    "NetIncomeLoss": "Net income", "ProfitLoss": "Net income",
    "EarningsPerShareDiluted": "Diluted EPS", "DilutedEarningsLossPerShare": "Diluted EPS",
    "InterestExpense": "Interest expense",
    "Assets": "Total assets", "Liabilities": "Total liabilities",
    "AssetsCurrent": "Current assets", "CurrentAssets": "Current assets",
    "LiabilitiesCurrent": "Current liabilities", "CurrentLiabilities": "Current liabilities",
    "StockholdersEquity": "Shareholders' equity", "Equity": "Shareholders' equity",
    "CashAndCashEquivalentsAtCarryingValue": "Cash", "CashAndCashEquivalents": "Cash",
    "LongTermDebtNoncurrent": "Long-term debt", "LongTermDebt": "Long-term debt",
    "NoncurrentBorrowings": "Long-term debt",
    "NetCashProvidedByUsedInOperatingActivities": "Operating cash flow",
    "CashFlowsFromUsedInOperatingActivities": "Operating cash flow",
    "PaymentsToAcquirePropertyPlantAndEquipment": "Capex", "PurchaseOfPropertyPlantAndEquipment": "Capex",
    "PaymentsToAcquireProductiveAssets": "Capex",
    "PaymentsOfDividends": "Dividends paid", "PaymentsOfDividendsCommonStock": "Dividends paid",
    "PaymentsForRepurchaseOfCommonStock": "Buybacks",
}
PREF = list(LINES)            # earlier in LINES wins ties
FLOW = {"Revenue", "Cost of revenue", "Gross profit", "Operating income", "R&D expense", "Net income",
        "Diluted EPS", "Interest expense", "Operating cash flow", "Capex", "Dividends paid", "Buybacks"}
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A", "10-KT"}

_lock = threading.Lock()
_next = [0.0]


def get(url, tries=4):
    for k in range(tries):
        with _lock:                                    # global pacing: <= 8 requests / second
            wait = _next[0] - time.time()
            if wait > 0:
                time.sleep(wait)
            _next[0] = max(time.time(), _next[0]) + 0.125
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (403, 429, 503) and k < tries - 1:
                time.sleep(5 * (k + 1))
                continue
            raise
        except Exception:  # noqa: BLE001
            if k < tries - 1:
                time.sleep(3 * (k + 1))
                continue
            raise
    return None


def _days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def annual(facts):
    """label -> [{end, val, filed, form, fy, concept}] (last 6 fiscal years)."""
    best = {}
    for tax in ("us-gaap", "ifrs-full"):
        for concept, node in (facts.get(tax) or {}).items():
            label = LINES.get(concept)
            if not label:
                continue
            units = node.get("units") or {}
            unit = next((u for u in ("USD", "USD/shares", "shares") if u in units), None)
            if unit is None:
                unit = next(iter(units), None)          # e.g. EUR for some foreign filers
            if unit is None:
                continue
            by_end = {}
            for o in units[unit]:
                if o.get("form") not in ANNUAL_FORMS or not o.get("end"):
                    continue
                if label in FLOW:
                    if not o.get("start") or not (330 <= _days(o["start"], o["end"]) <= 400):
                        continue
                elif o.get("start"):
                    continue
                prev = by_end.get(o["end"])
                if prev is None or (o.get("filed") or "") >= (prev.get("filed") or ""):
                    by_end[o["end"]] = o
            if not by_end:
                continue
            ser = [{"end": e, "val": by_end[e]["val"], "filed": by_end[e].get("filed"),
                    "form": by_end[e].get("form"), "fy": by_end[e].get("fy"), "concept": concept, "unit": unit}
                   for e in sorted(by_end)][-6:]
            cur = best.get(label)
            if cur is None or ser[-1]["end"] > cur[-1]["end"] or \
                    (ser[-1]["end"] == cur[-1]["end"] and PREF.index(concept) < PREF.index(cur[-1]["concept"])):
                best[label] = ser
    return best


def one(row):
    cik, ticker = row
    c10 = cik.zfill(10)
    out = {"cik": c10, "ticker": ticker}
    try:
        sub = get(f"https://data.sec.gov/submissions/CIK{c10}.json")
        if sub:
            rec = sub.get("filings", {}).get("recent", {})
            forms = rec.get("form", [])
            last10k = next((i for i, f in enumerate(forms) if f in ANNUAL_FORMS), None)
            out.update(name=sub.get("name"), sic=sub.get("sic"), sic_desc=sub.get("sicDescription"),
                       tickers=sub.get("tickers"), exchanges=sub.get("exchanges"),
                       state=sub.get("stateOfIncorporation"), fiscal_year_end=sub.get("fiscalYearEnd"),
                       category=sub.get("category"),
                       last_filing={"form": forms[0], "date": rec.get("filingDate", [None])[0]} if forms else None,
                       last_annual={"form": forms[last10k], "date": rec["filingDate"][last10k],
                                    "accession": rec["accessionNumber"][last10k],
                                    "doc": rec.get("primaryDocument", [""] * (last10k + 1))[last10k]}
                       if last10k is not None else None)
        cf = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c10}.json")
        if cf:
            out["entity"] = cf.get("entityName")
            out["annual"] = annual(cf.get("facts") or {})
            so = ((cf.get("facts") or {}).get("dei") or {}).get("EntityCommonStockSharesOutstanding", {})
            pts = [o for u in (so.get("units") or {}).values() for o in u if o.get("end")]
            if pts:
                p = max(pts, key=lambda o: (o["end"], o.get("filed") or ""))
                out["shares_out"] = {"val": p["val"], "end": p["end"]}
        out["status"] = "ok" if cf else ("no-xbrl" if sub else "not-found")
    except Exception as e:  # noqa: BLE001
        out["status"] = f"error: {e}"[:200]
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    rows = [tuple((l.rstrip("\n").split("\t") + [""])[:2]) for l in open(src) if l.strip()]
    rows = rows[:limit] if limit else rows
    t0 = time.time()
    done = 0
    stats = {}
    with gzip.open(dst, "wt") as f, ThreadPoolExecutor(8) as ex:
        for r in ex.map(one, rows):
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
            done += 1
            k = r["status"].split(":")[0]
            stats[k] = stats.get(k, 0) + 1
            if done % 250 == 0:
                print(f"{done}/{len(rows)}  {time.time() - t0:.0f}s  {stats}", flush=True)
    print("done", stats, f"{time.time() - t0:.0f}s",
          datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if stats.get("error", 0) > 0.2 * len(rows):
        sys.exit(1)


if __name__ == "__main__":
    main()
