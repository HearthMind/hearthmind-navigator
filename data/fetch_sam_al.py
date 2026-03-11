"""
FetchAgent - SAM.gov Assistance Listings (v2)
Uses the new Assistance Listings Public API (released Feb 2, 2026)
Endpoint: https://api.sam.gov/assistance-listings/v1/search
Docs: https://open.gsa.gov/api/assistance-listings-api/

Key difference: pageSize=1000 supported, so ~3 requests gets the full catalog.
"""

import requests
import time
import json
import os
from pathlib import Path
from config import SAM_API_KEY, REQUEST_DELAY_SEC, MAX_RETRIES, STAGING_DIR

# New endpoint
ASSISTANCE_LISTINGS_URL = "https://api.sam.gov/assistance-listings/v1/search"


def fetch_assistance_listings(page_size=1000) -> list[dict]:
    """
    Fetch all active federal assistance listings from SAM.gov Assistance Listings API.
    Uses pageSize=1000 to minimize API calls (10/day limit for non-federal accounts).
    Returns list of normalized program dicts.
    """
    if not SAM_API_KEY:
        raise ValueError("SAM_API_KEY not set. Get one free at https://sam.gov/profile/details")

    programs = []
    page = 1
    total_fetched = 0

    print(f"[SAM-AL] Starting fetch from Assistance Listings API...")
    print(f"[SAM-AL] Using pageSize={page_size} (max 1000)")

    while True:
        params = {
            "api_key": SAM_API_KEY,
            "status": "Active",
            "pageSize": page_size,
            "pageNumber": page,
        }

        for attempt in range(MAX_RETRIES):
            try:
                print(f"[SAM-AL] Requesting page {page}...")
                resp = requests.get(ASSISTANCE_LISTINGS_URL, params=params, timeout=60)

                # Rate limit check
                if resp.status_code == 429:
                    try:
                        body = resp.json()
                        next_access = body.get("nextAccessTime", "tomorrow")
                    except:
                        next_access = "unknown"
                    print(f"[SAM-AL] Rate limit hit after {len(programs)} programs. Quota resets: {next_access}")
                    return programs

                resp.raise_for_status()
                data = resp.json()
                break
            except requests.exceptions.HTTPError:
                raise
            except Exception as e:
                print(f"[SAM-AL] Attempt {attempt + 1} failed: {e}")
                if attempt == MAX_RETRIES - 1:
                    print(f"[SAM-AL] Max retries reached. Saving {len(programs)} programs fetched so far.")
                    return programs
                time.sleep(2 ** attempt)

        results = data.get("assistanceListingsData", [])
        if not results:
            print(f"[SAM-AL] No results on page {page}. Done.")
            break

        for listing in results:
            programs.append(_normalize_listing(listing))

        total_fetched += len(results)
        total_records = data.get("totalRecords", 0)
        total_pages = data.get("totalPages", 0)
        print(f"[SAM-AL] Page {page}/{total_pages}: fetched {len(results)} (total: {total_fetched}/{total_records})")

        if total_fetched >= total_records:
            break

        page += 1
        time.sleep(REQUEST_DELAY_SEC)

    print(f"[SAM-AL] Complete. Total programs: {len(programs)}")
    return programs


def _normalize_listing(raw: dict) -> dict:
    """Normalize an Assistance Listings API record to Navigator programs schema."""

    # Extract org info
    fed_org = raw.get("federalOrganization", {})
    agency = fed_org.get("agency", "") or fed_org.get("department", "")

    # Extract overview
    overview = raw.get("overview", {})
    objective = overview.get("objective", "") or ""
    description = overview.get("assistanceListingDescription", "") or ""

    # Use whichever is more substantive
    desc_text = description if len(description) > len(objective) else objective

    # Extract eligibility
    criteria = raw.get("criteriaForApplying", {})
    applicant = criteria.get("applicant", {})
    beneficiary = criteria.get("beneficiary", {})
    eligibility_text = beneficiary.get("description", "") or applicant.get("description", "")

    # Map assistance types
    fin_info = raw.get("financialInformation", {})
    obligations = fin_info.get("obligations", [])
    assistance_types = [o.get("assistanceType", {}).get("name", "") for o in obligations]
    category = _map_assistance_type(assistance_types)

    listing_id = raw.get("assistanceListingId", "")

    return {
        "source": "sam.gov",
        "source_id": listing_id,
        "name": raw.get("title", "").strip(),
        "agency": agency,
        "category": category,
        "description": desc_text[:10000],  # BigQuery STRING limit safety
        "eligibility_text": eligibility_text[:10000],
        "url": f"https://sam.gov/fal/{listing_id}" if listing_id else "",
        "cfda_number": listing_id,
        "status": raw.get("status", ""),
        "last_updated": raw.get("publishedDate", ""),
    }


def _map_assistance_type(type_names: list) -> str:
    """Map Assistance Listings type names to Navigator categories."""
    type_map = {
        "Grant": "grants",
        "Cooperative Agreement": "grants",
        "Direct Loan": "loans",
        "Loan Guarantee": "loan_guarantees",
        "Indemnity/Insurance (non-loan)": "insurance",
        "Direct Payment for Specified Use": "direct_payments",
        "Direct Payment with Unrestricted Use": "direct_payments",
        "Training": "training",
        "Advisory Services": "advisory",
        "Provision of Specialized Services": "services",
        "Dissemination of Technical Information": "information",
        "Investigation of Complaints": "services",
    }
    for name in type_names:
        mapped = type_map.get(name)
        if mapped:
            return mapped
    return "other"


def save_staging(programs: list[dict], filename="sam_assistance_listings.json"):
    """Save fetched programs to local staging file."""
    Path(STAGING_DIR).mkdir(exist_ok=True)
    path = os.path.join(STAGING_DIR, filename)
    with open(path, "w") as f:
        json.dump(programs, f, indent=2, default=str)
    print(f"[SAM-AL] Staged {len(programs)} programs to {path}")
    return path


if __name__ == "__main__":
    programs = fetch_assistance_listings()
    save_staging(programs)
