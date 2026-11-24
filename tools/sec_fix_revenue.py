#!/usr/bin/env python3
"""Second pass over the SEC data: fill in revenue (and other lines) the first pass missed.

1. Companies whose filings use less common revenue tags (banks, insurers, REITs, utilities, foreign IFRS filers):
   re-read their XBRL facts with a wider list of revenue concepts.
2. Companies whose ticker now points at a brand-new holding company with no annual report yet (e.g. ExxonMobil
   Holdings): look up the predecessor registrant on EDGAR by name and use its reported financials.

    python tools/sec_fix_revenue.py in.jsonl.gz out.jsonl.gz
Runs on GitHub Actions (SEC not reachable from the sandbox).
"""
import difflib
import gzip
import json
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sec_fundamentals as sf  # noqa: E402

EXTRA_REVENUE = [
    "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet", "SalesRevenueServicesNet",
    "RevenuesNetOfInterestExpense", "InterestAndDividendIncomeOperating", "InterestIncomeOperating",
    "OperatingLeasesIncomeStatementLeaseRevenue", "RealEstateRevenueNet", "OperatingLeaseLeaseIncome",
    "PremiumsEarnedNet", "HealthCareOrganizationRevenue", "RegulatedOperatingRevenue", "UtilitiesOperatingRevenue",
    "TotalRevenuesAndOtherIncome", "RevenueMineralSales", "BrokerageCommissionsRevenue", "InvestmentBankingRevenue",
    "FinancialServicesRevenue", "RevenueNotFromContractWithCustomer", "RevenuesExcludingInterestAndDividends",
    "NoninterestIncome", "InterestAndFeeIncomeLoansAndLeases",
]
for c in EXTRA_REVENUE:
    sf.LINES.setdefault(c, "Revenue")
# keep the original preference order first, extras last (so a company's main "Revenues" tag still wins)
sf.PREF[:] = list(sf.LINES)
# bank revenue = net interest + non-interest income is not a single tag; prefer RevenuesNetOfInterestExpense, then the rest
FUND_SIC = {"6726", "6221"}
DEBUG = False


def has_recent_revenue(d, since="2024-01-01"):
    return any(x["end"] >= since for x in (d.get("annual") or {}).get("Revenue", []))


def refetch(d):
    c10 = d["cik"]
    cf = sf.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c10}.json")
    if cf:
        ann = sf.annual(cf.get("facts") or {})
        if ann:
            d["annual"] = ann
            d.setdefault("fixes", []).append("wider revenue tags")
    return d


def edgar_search(name):
    q = re.sub(r"\b(holdings?|corp(oration)?|inc|co|ltd|plc|group|sa|nv|ag)\b\.?", "", name, flags=re.I)
    q = re.sub(r"[^A-Za-z0-9 &]", " ", q).strip()
    q = " ".join(q.split()[:3])
    if len(q) < 3:
        return []
    url = "https://www.sec.gov/cgi-bin/browse-edgar?" + urllib.parse.urlencode(
        {"company": q, "type": "10-K", "dateb": "", "owner": "include", "count": "40", "action": "getcompany", "output": "atom"})
    req = sf.urllib.request.Request(url, headers={"User-Agent": sf.UA})
    try:
        raw = sf.urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return []
    ents = re.findall(r"<cik>(\d+)</cik>.*?<(?:conformed-name|name)>([^<]+)</", raw, re.S)
    if not ents:  # atom company list: <title>NAME</title> ... CIK=0000034088
        for e in re.findall(r"<entry>(.*?)</entry>", raw, re.S):
            t = re.search(r"<title>([^<]+)</title>", e); c = re.search(r"CIK=(\d{4,10})|<cik>(\d+)</cik>", e)
            if t and c:
                ents.append((c.group(1) or c.group(2), t.group(1)))
    if DEBUG:
        print("search", q, "->", ents[:6], "| raw starts:", raw[:200].replace("\n", " "), flush=True)
    return [(c.zfill(10), n.strip()) for c, n in ents]


def predecessor(d):
    name = d.get("name") or d.get("entity") or ""
    norm = lambda x: re.sub(r"[^a-z0-9]", "", re.sub(r"\b(holdings?|corp(oration)?|inc|co|ltd|plc|group)\b", "", x.lower()))
    best = None
    for cik, nm in edgar_search(name):
        if cik == d["cik"]:
            continue
        sim = difflib.SequenceMatcher(None, norm(nm), norm(name)).ratio()
        if sim < 0.75:
            continue
        cf = sf.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        if not cf:
            continue
        ann = sf.annual(cf.get("facts") or {})
        rev = ann.get("Revenue", [])
        if rev and rev[-1]["end"] >= "2024-01-01" and (best is None or sim > best[0]):
            best = (sim, cik, nm, ann)
    if best:
        d["annual"] = best[3]
        d["data_cik"] = best[1]
        d.setdefault("fixes", []).append(f"financials from predecessor registrant {best[2]} (CIK {best[1]})")
    return d


def work(d):
    try:
        if d.get("status") != "ok" or d.get("sic") in FUND_SIC:
            return d
        if not d.get("annual"):
            if (d.get("last_annual") or {}).get("form") is None:
                d = predecessor(d)
            else:
                d = refetch(d)
        elif not has_recent_revenue(d):
            d = refetch(d)
    except Exception as e:  # noqa: BLE001
        d.setdefault("fixes", []).append(f"retry failed: {e}"[:120])
    return d


def main():
    global DEBUG
    src, dst = sys.argv[1], sys.argv[2]
    rows = [json.loads(l) for l in gzip.open(src, "rt")]
    DEBUG = True
    xom = next((d for d in rows if d.get("ticker") == "XOM"), None)
    if xom:
        print("XOM test:", predecessor(dict(xom)).get("fixes"), flush=True)
    DEBUG = False
    before = sum(has_recent_revenue(d) for d in rows)
    t0 = time.time(); out = []
    with ThreadPoolExecutor(8) as ex:
        for k, d in enumerate(ex.map(work, rows), 1):
            out.append(d)
            if k % 500 == 0:
                print(k, len(rows), f"{time.time() - t0:.0f}s", flush=True)
    after = sum(has_recent_revenue(d) for d in out)
    with gzip.open(dst, "wt") as f:
        for d in out:
            f.write(json.dumps(d, separators=(",", ":")) + "\n")
    fixed = [d for d in out if d.get("fixes")]
    print(f"recent revenue: {before} -> {after} companies; {len(fixed)} records touched")
    for d in fixed[:40]:
        print(" ", d.get("ticker"), d.get("name"), "|", "; ".join(d["fixes"]))


if __name__ == "__main__":
    main()
