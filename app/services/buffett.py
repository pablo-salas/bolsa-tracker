"""Warren Buffett 13F tracker via SEC EDGAR."""

import json
from xml.etree import ElementTree as ET

import httpx

from app.config import SEC_USER_AGENT

BERKSHIRE_CIK = "0001067983"
SEC_BASE = "https://data.sec.gov"
EDGAR_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json, application/xml, */*"}

# ── CEDEAR mapping ────────────────────────────────────────

CEDEAR_MAP: dict[str, dict] = {
    "AAPL": {"cedear": "AAPL", "ratio": 10},
    "MSFT": {"cedear": "MSFT", "ratio": 5},
    "AMZN": {"cedear": "AMZN", "ratio": 36},
    "GOOGL": {"cedear": "GOOGL", "ratio": 14},
    "META": {"cedear": "META", "ratio": 5},
    "TSLA": {"cedear": "TSLA", "ratio": 15},
    "NVDA": {"cedear": "NVDA", "ratio": 10},
    "BRK.B": {"cedear": "BRK.B", "ratio": 1},
    "JPM": {"cedear": "JPM", "ratio": 3},
    "V": {"cedear": "VISA", "ratio": 3},
    "JNJ": {"cedear": "JNJ", "ratio": 3},
    "WMT": {"cedear": "WMT", "ratio": 5},
    "PG": {"cedear": "PG", "ratio": 4},
    "UNH": {"cedear": "UNH", "ratio": 1},
    "HD": {"cedear": "HD", "ratio": 3},
    "MA": {"cedear": "MA", "ratio": 3},
    "DIS": {"cedear": "DISN", "ratio": 4},
    "KO": {"cedear": "KO", "ratio": 5},
    "PEP": {"cedear": "PEP", "ratio": 4},
    "ABBV": {"cedear": "ABBV", "ratio": 3},
    "MRK": {"cedear": "MRK", "ratio": 5},
    "CVX": {"cedear": "CVX", "ratio": 3},
    "XOM": {"cedear": "XOM", "ratio": 5},
    "BAC": {"cedear": "BAC", "ratio": 5},
    "WFC": {"cedear": "WFC", "ratio": 5},
    "C": {"cedear": "C", "ratio": 3},
    "GS": {"cedear": "GS", "ratio": 1},
    "AXP": {"cedear": "AXP", "ratio": 2},
    "DE": {"cedear": "DE", "ratio": 2},
    "NKE": {"cedear": "NKE", "ratio": 4},
    "MCD": {"cedear": "MCD", "ratio": 3},
    "KO": {"cedear": "KO", "ratio": 5},
    "T": {"cedear": "T", "ratio": 10},
    "VZ": {"cedear": "VZ", "ratio": 5},
    "NFLX": {"cedear": "NFLX", "ratio": 3},
    "AMD": {"cedear": "AMD", "ratio": 5},
    "INTC": {"cedear": "INTC", "ratio": 5},
    "BA": {"cedear": "BA", "ratio": 4},
    "PYPL": {"cedear": "PYPL", "ratio": 5},
    "SBUX": {"cedear": "SBUX", "ratio": 5},
    "PFE": {"cedear": "PFE", "ratio": 10},
    "F": {"cedear": "F", "ratio": 10},
    "GM": {"cedear": "GM", "ratio": 5},
}


def find_cedear(ticker_usa: str) -> dict | None:
    return CEDEAR_MAP.get(ticker_usa.upper())


# ── SEC EDGAR ─────────────────────────────────────────────


async def _find_info_table_url(client: httpx.AsyncClient, cik: str, acc_nodash: str) -> str | None:
    """Find the actual info table XML filename from the filing index."""
    index_url = f"{EDGAR_ARCHIVES}/{cik}/{acc_nodash}/index.json"
    try:
        r = await client.get(index_url)
        r.raise_for_status()
        items = r.json().get("directory", {}).get("item", [])
        for item in items:
            name = item.get("name", "").lower()
            if "infotable" in name and name.endswith(".xml"):
                return f"{EDGAR_ARCHIVES}/{cik}/{acc_nodash}/{item['name']}"
    except Exception:
        pass
    # Fallback: try common names
    for name in ("infotable.xml", "InfoTable.xml", "informationtable.xml"):
        try:
            r = await client.head(f"{EDGAR_ARCHIVES}/{cik}/{acc_nodash}/{name}")
            if r.status_code == 200:
                return f"{EDGAR_ARCHIVES}/{cik}/{acc_nodash}/{name}"
        except Exception:
            pass
    return None


async def get_latest_13f_filings(count: int = 5) -> list[dict]:
    cik_no_pad = BERKSHIRE_CIK.lstrip("0")
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as c:
        r = await c.get(f"{SEC_BASE}/submissions/CIK{BERKSHIRE_CIK}.json")
        r.raise_for_status()

        data = r.json()
        recent = data["filings"]["recent"]
        filings = []

        for i in range(len(recent["form"])):
            if recent["form"][i] == "13F-HR" and len(filings) < count:
                acc = recent["accessionNumber"][i]
                acc_nodash = acc.replace("-", "")

                info_table_url = await _find_info_table_url(c, cik_no_pad, acc_nodash)

                filings.append(
                    {
                        "accession_number": acc,
                        "filing_date": recent["filingDate"][i],
                        "report_date": recent["reportDate"][i],
                        "primary_doc_url": f"{EDGAR_ARCHIVES}/{cik_no_pad}/{acc_nodash}/{recent['primaryDocument'][i]}",
                        "info_table_url": info_table_url or f"{EDGAR_ARCHIVES}/{cik_no_pad}/{acc_nodash}/infotable.xml",
                    }
                )
    return filings


async def parse_info_table(url: str) -> list[dict]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as c:
        r = await c.get(url)
        r.raise_for_status()

    root = ET.fromstring(r.text)
    # Handle XML namespaces
    ns = {"": ""}
    for prefix, uri in [("ns", "http://www.sec.gov/edgar/document/thirteenf/informationtable")]:
        ns[prefix] = uri

    holdings = []
    # Try with namespace first, then without
    entries = root.findall(".//{http://www.sec.gov/edgar/document/thirteenf/informationtable}infoTable")
    if not entries:
        entries = root.findall(".//infoTable")
    if not entries:
        # Try all children
        entries = list(root)

    for entry in entries:
        def txt(tag: str) -> str:
            # Try with namespace
            el = entry.find(f"{{http://www.sec.gov/edgar/document/thirteenf/informationtable}}{tag}")
            if el is None:
                el = entry.find(tag)
            return el.text.strip() if el is not None and el.text else ""

        def num(tag: str) -> int:
            v = txt(tag)
            return int(v) if v else 0

        # Get nested elements
        shramt_el = entry.find("{http://www.sec.gov/edgar/document/thirteenf/informationtable}shrsOrPrnAmt")
        if shramt_el is None:
            shramt_el = entry.find("shrsOrPrnAmt")

        shares = 0
        share_type = "SH"
        if shramt_el is not None:
            sh_el = shramt_el.find("{http://www.sec.gov/edgar/document/thirteenf/informationtable}sshPrnamt")
            if sh_el is None:
                sh_el = shramt_el.find("sshPrnamt")
            st_el = shramt_el.find("{http://www.sec.gov/edgar/document/thirteenf/informationtable}sshPrnamtType")
            if st_el is None:
                st_el = shramt_el.find("sshPrnamtType")
            shares = int(sh_el.text.strip()) if sh_el is not None and sh_el.text else 0
            share_type = st_el.text.strip() if st_el is not None and st_el.text else "SH"

        holdings.append(
            {
                "issuer": txt("nameOfIssuer"),
                "title_of_class": txt("titleOfClass"),
                "cusip": txt("cusip"),
                "value": int(txt("value") or "0"),
                "shares": shares,
                "share_type": share_type,
            }
        )
    return holdings


async def cusip_to_ticker(cusips: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    batch_size = 100
    async with httpx.AsyncClient(timeout=30) as c:
        for i in range(0, len(cusips), batch_size):
            batch = cusips[i : i + batch_size]
            body = [{"idType": "ID_CUSIP", "idValue": cusip} for cusip in batch]
            try:
                r = await c.post(
                    "https://api.openfigi.com/v3/mapping",
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                if r.status_code == 200:
                    results = r.json()
                    for idx, result in enumerate(results):
                        if "data" in result and result["data"]:
                            mapping[batch[idx]] = result["data"][0].get("ticker", "")
            except Exception:
                pass
    return mapping


def diff_holdings(current: list[dict], previous: list[dict]) -> dict[str, dict]:
    prev_map = {h["cusip"]: h for h in previous}
    curr_map = {h["cusip"]: h for h in current}
    changes: dict[str, dict] = {}

    for cusip, curr in curr_map.items():
        prev = prev_map.get(cusip)
        if not prev:
            changes[cusip] = {"change": "new", "change_shares": curr["shares"], "prev_shares": 0}
        elif curr["shares"] > prev["shares"]:
            changes[cusip] = {"change": "increased", "change_shares": curr["shares"] - prev["shares"], "prev_shares": prev["shares"]}
        elif curr["shares"] < prev["shares"]:
            changes[cusip] = {"change": "decreased", "change_shares": prev["shares"] - curr["shares"], "prev_shares": prev["shares"]}
        else:
            changes[cusip] = {"change": "unchanged", "change_shares": 0, "prev_shares": prev["shares"]}

    for cusip, prev in prev_map.items():
        if cusip not in curr_map:
            changes[cusip] = {"change": "exited", "change_shares": -prev["shares"], "prev_shares": prev["shares"]}

    return changes
