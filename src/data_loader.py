"""
Navigator Data Loader
=====================
Reads the SAM.gov bulk CSV once at startup.
Builds clean in-memory program list — no BigQuery, no auth.

CSV: /home/hyperion/hearthmind/data/raw/sam_assistance_listings_20260207.csv
"""

import csv
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

CSV_PATH = Path(__file__).parent.parent / "data" / "raw" / "sam_assistance_listings_20260207.csv"

ASSISTANCE_TYPE_MAP = {
    "PROJECT GRANTS": "grants",
    "FORMULA GRANTS": "grants",
    "COOPERATIVE AGREEMENTS": "grants",
    "DIRECT LOANS": "loans",
    "GUARANTEED/INSURED LOANS": "loans",
    "INSURANCE": "insurance",
    "DIRECT PAYMENTS FOR SPECIFIED USE": "direct_payments",
    "DIRECT PAYMENTS WITH UNRESTRICTED USE": "direct_payments",
    "TRAINING": "training",
    "ADVISORY SERVICES AND COUNSELING": "advisory",
    "PROVISION OF SPECIALIZED SERVICES": "services",
    "DISSEMINATION OF TECHNICAL INFORMATION": "information",
    "INVESTIGATION OF COMPLAINTS": "services",
    "SALE, EXCHANGE, OR DONATION OF PROPERTY AND GOODS": "other",
    "USE OF PROPERTY, FACILITIES, AND EQUIPMENT": "other",
}

SKIP_VALUES = {"Not Applicable", "N/A", "None", "null", ""}


def _clean(val: str) -> str:
    return val.strip() if val and val.strip() not in SKIP_VALUES else ""


def _map_type(raw_type: str) -> str:
    upper = raw_type.upper().strip()
    for key, val in ASSISTANCE_TYPE_MAP.items():
        if key in upper:
            return val
    return "other"


def _simplify_agency(raw: str) -> str:
    """Extract the department name from the long agency string."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[-2].title()
    if len(parts) == 2:
        return parts[0].title()
    return raw.title()[:50]


def _normalize(row: Dict) -> Optional[Dict]:
    title = _clean(row.get("Program Title", ""))
    if not title or title == "Not Applicable":
        return None

    objectives = _clean(row.get("Objectives (050)", ""))
    if not objectives:
        return None

    agency_raw = row.get("Federal Agency (030)", "")
    assistance_raw = row.get("Types of Assistance (060)", "")

    return {
        "title": title,
        "number": _clean(row.get("Program Number", "")),
        "agency": _clean(agency_raw),
        "agency_short": _simplify_agency(agency_raw),
        "category": _map_type(assistance_raw),
        "assistance_type": _clean(assistance_raw),
        "objectives": objectives[:600],
        "eligibility": _clean(row.get("Applicant Eligibility (081)", ""))[:400],
        "beneficiary": _clean(row.get("Beneficiary Eligibility (082)", ""))[:400],
        "uses": _clean(row.get("Uses and Use Restrictions (070)", ""))[:400],
        "url": _clean(row.get("URL", "")),
        "published": _clean(row.get("Published Date", "")),
    }


_PROGRAMS: List[Dict] = []


def load_programs() -> List[Dict]:
    global _PROGRAMS
    if _PROGRAMS:
        return _PROGRAMS

    programs = []
    with open(CSV_PATH, encoding="latin-1") as f:
        for row in csv.DictReader(f):
            normalized = _normalize(row)
            if normalized:
                programs.append(normalized)

    _PROGRAMS = programs
    print(f"[Navigator] Loaded {len(programs)} programs from SAM.gov CSV")
    return _PROGRAMS


def search_programs(
    query: str = "",
    category: str = "",
    agency: str = "",
    limit: int = 50,
    offset: int = 0,
) -> Dict:
    programs = load_programs()
    results = programs

    # Text search across title + objectives + eligibility
    if query:
        q = query.lower()
        results = [
            p for p in results
            if q in p["title"].lower()
            or q in p["objectives"].lower()
            or q in p["eligibility"].lower()
            or q in p["beneficiary"].lower()
        ]

    if category and category != "all":
        results = [p for p in results if p["category"] == category]

    if agency:
        a = agency.lower()
        results = [p for p in results if a in p["agency"].lower()]

    total = len(results)
    page = results[offset: offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": page,
    }


def get_context_for_chat(query: str, limit: int = 8) -> List[Dict]:
    """Return top programs relevant to a chat query for Gemini context."""
    result = search_programs(query=query, limit=limit)
    return result["results"]


def get_categories() -> List[Dict]:
    programs = load_programs()
    from collections import Counter
    counts = Counter(p["category"] for p in programs)
    return [{"id": k, "label": k.replace("_", " ").title(), "count": v}
            for k, v in counts.most_common()]


if __name__ == "__main__":
    progs = load_programs()
    print(f"Loaded: {len(progs)}")
    r = search_programs(query="disability", limit=3)
    print(f"Search 'disability': {r['total']} results")
    for p in r["results"]:
        print(f"  {p['title'][:60]} | {p['agency_short']}")
