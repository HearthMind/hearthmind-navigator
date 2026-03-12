"""
Navigator — 211 NDP Fetcher (V2)
==================================
Queries the 211 National Data Platform Search V2 + Query V2 APIs.
Returns HSDS-normalized results for Navigator's synthesis layer.

Requires: API_211_KEY in .env
Docs: https://apiportal.211.org

Two-step pattern (per 211 docs):
  1. search_211()        → abbreviated results with idServiceAtLocation
  2. get_service_detail() → full details (eligibility, hours, accessibility)
"""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

BASE_SEARCH = "https://api.211.org/resources/v2/search"
BASE_QUERY  = "https://api.211.org/resources/v2/query"

API_KEY = os.environ.get("API_211_KEY", "")

# ---------------------------------------------------------------------------
# AIRS Taxonomy shortcuts — plain language → 211 taxonomy code
# Expand as we learn which codes return the best results
# ---------------------------------------------------------------------------
TAXONOMY_MAP = {
    "food":              "BD-1800",
    "food pantry":       "BD-1800.2000",
    "shelter":           "BH-1800",
    "housing":           "BH",
    "mental health":     "RP-1500",
    "trauma therapy":    "RP-1500.1700",
    "counseling":        "RP-1500",
    "medicaid":          "NL-2000",
    "disability":        "NL-3000",
    "veteran":           "LV",
    "substance abuse":   "RP-1500.8000",
    "crisis":            "RP-1500.1300",
    "domestic violence": "PH-1500",
    "childcare":         "CC",
    "transportation":    "BT",
    "utility":           "NL-6000",
    "legal":             "LH",
}

def get_taxonomy_code(plain: str) -> Optional[str]:
    return TAXONOMY_MAP.get(plain.lower().strip())

def _headers() -> Dict:
    return {"Api-Key": API_KEY, "Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# SEARCH — Step 1: get abbreviated results
# ---------------------------------------------------------------------------
def search_211(
    zip_code: str,
    keyword: str = "",
    taxonomy_code: str = "",
    radius_miles: int = 10,
    limit: int = 10,          # trial tier max = 10
) -> List[Dict]:
    """
    Search 211 NDP by zip code. Returns abbreviated results.
    Each result contains idServiceAtLocation for detail lookup.
    """
    if not API_KEY:
        logger.warning("[211] No API key — skipping live query")
        return []
    if not requests:
        logger.error("[211] requests not installed")
        return []

    tax_code = taxonomy_code or get_taxonomy_code(keyword) or ""

    params = {
        "location": zip_code,
        "distance": radius_miles,
        "size":     min(limit, 10),   # trial hard cap
        "skip":     0,                # trial locked to first page
    }
    if tax_code:
        params["taxonomyCode"] = tax_code
    elif keyword:
        params["keyword"] = keyword

    try:
        resp = requests.get(
            f"{BASE_SEARCH}/keyword",
            params=params,
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"[211] Search failed: {e}")
        return []

    results = data.get("records", data.get("results", []))
    logger.info(f"[211] zip={zip_code} '{keyword}' → {len(results)} results")
    return results

# ---------------------------------------------------------------------------
# QUERY — Step 2: get full detail for a chosen result
# ---------------------------------------------------------------------------
def get_service_detail(id_service_at_location: str) -> Optional[Dict]:
    """
    Fetch full service-at-location detail by ID.
    Includes eligibility, hours, accessibility, languages, temp messages.
    """
    if not API_KEY or not requests:
        return None
    try:
        resp = requests.get(
            f"{BASE_QUERY}/service-at-location-details/{id_service_at_location}",
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[211] Detail fetch failed for {id_service_at_location}: {e}")
        return None


def get_locations_for_org(org_id: str) -> List[Dict]:
    """Fetch all locations for an organization."""
    if not API_KEY or not requests:
        return []
    try:
        resp = requests.get(
            f"{BASE_QUERY}/locations-for-organization/{org_id}",
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[211] Locations fetch failed for org {org_id}: {e}")
        return []

# ---------------------------------------------------------------------------
# NORMALIZE — shape detail response for Navigator cards
# ---------------------------------------------------------------------------
def normalize_detail(detail: Dict) -> Dict:
    """
    Normalize a Query V2 service-at-location detail into Navigator card format.
    Surfaces accessibility, hours, language, and status info.
    """
    loc  = detail.get("location", {})
    svc  = detail.get("service", {})
    meta = detail.get("meta", {})

    # Hours — build human-readable schedule
    hours = []
    for sched in loc.get("schedules", []):
        if sched.get("type") == "Regular":
            for day in sched.get("open", []):
                hours.append(f"{day['day']}: {day.get('opensAt','')}–{day.get('closesAt','')}")

    # Accessibility flags
    access_types = loc.get("accessibility", {}).get("types", "")
    wheelchair = "WheelChairAccess" in str(access_types)

    # Languages
    lang_codes = loc.get("languages", {}).get("codes", [])
    speaks_spanish = "Spanish" in lang_codes
    speaks_asl = "SignLanguage" in lang_codes

    # Status / temporary message
    status = meta.get("status", "Active")
    reason_inactive = meta.get("reasonInactive", "")
    temp_msg = meta.get("temporaryMessage", {}).get("message", "")
    last_verified = meta.get("lastVerified", "")

    # Address
    address = ""
    addresses = loc.get("addresses", [])
    if addresses:
        a = addresses[0]
        address = f"{a.get('street','')} {a.get('city','')} {a.get('state','')} {a.get('postalCode','')}".strip()

    # Phone
    phone = ""
    phones = loc.get("phones", [])
    if phones:
        phone = phones[0].get("number", "")

    return {
        "source":           "211",
        "title":            svc.get("name", ""),
        "description":      svc.get("description", "")[:600],
        "eligibility":      svc.get("eligibility", "")[:400],
        "application":      svc.get("applicationProcess", ""),
        "fees":             svc.get("fees", ""),
        "wait_time":        svc.get("waitTime", ""),
        "address":          address,
        "phone":            phone,
        "url":              svc.get("url", "") or loc.get("url", ""),
        "hours":            hours,
        "wheelchair":       wheelchair,
        "spanish":          speaks_spanish,
        "asl":              speaks_asl,
        "status":           status,
        "reason_inactive":  reason_inactive,
        "temp_message":     temp_msg,
        "last_verified":    last_verified,
    }

# ---------------------------------------------------------------------------
# SMOKE TEST
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    API_KEY = os.environ.get("API_211_KEY", "")

    if not API_KEY:
        print("❌ Set API_211_KEY in .env to test")
    else:
        print("🔍 Searching 99201 for trauma therapy...")
        results = search_211("99201", keyword="trauma therapy")
        print(f"   → {len(results)} results")
        for r in results[:3]:
            sal_id = r.get("idServiceAtLocation") or r.get("id", "")
            name   = r.get("name", r.get("title", ""))
            print(f"   {name} | id={sal_id}")

        if results:
            first_id = results[0].get("idServiceAtLocation") or results[0].get("id")
            if first_id:
                print(f"\n📋 Fetching detail for {first_id}...")
                detail = get_service_detail(first_id)
                if detail:
                    card = normalize_detail(detail)
                    print(f"   Title:       {card['title']}")
                    print(f"   Address:     {card['address']}")
                    print(f"   Phone:       {card['phone']}")
                    print(f"   Wheelchair:  {card['wheelchair']}")
                    print(f"   Spanish:     {card['spanish']}")
                    print(f"   Status:      {card['status']}")
                    if card['hours']:
                        print(f"   Hours:       {card['hours'][0]}")
