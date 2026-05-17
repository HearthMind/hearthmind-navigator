"""
Navigator Gemini Search
=======================
Augments local SAM.gov data with live web search via Gemini.
Discovered resources are auto-ingested into discovered_resources.json
with verified=False for human review.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

DISCOVERED_PATH = Path(__file__).parent.parent / "data" / "discovered_resources.json"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _load_discovered() -> list:
    if DISCOVERED_PATH.exists():
        with open(DISCOVERED_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_discovered(resources: list) -> None:
    DISCOVERED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DISCOVERED_PATH, "w", encoding="utf-8") as f:
        json.dump(resources, f, indent=2)


def _already_known(url: str, existing: list) -> bool:
    return any(r.get("url", "").strip("/") == url.strip("/") for r in existing)


def ingest_discovered(resource: dict) -> bool:
    """Add a new resource to discovered_resources.json. Returns True if added."""
    existing = _load_discovered()
    url = resource.get("url", "")
    if url and _already_known(url, existing):
        return False
    resource.setdefault("verified", False)
    resource.setdefault("source", "gemini_search")
    resource.setdefault("discovered_at", datetime.now(timezone.utc).isoformat())
    resource.setdefault("category", "other")
    resource.setdefault("agency_short", "")
    existing.append(resource)
    _save_discovered(existing)
    return True


def load_discovered() -> list:
    """Return all discovered resources (verified and unverified)."""
    return _load_discovered()


def search_gemini(query: str, limit: int = 5) -> list:
    """
    Search the web via Gemini for benefit programs matching query.
    Returns a list of normalized resource dicts, ingests new ones.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return []

    prompt = f"""You are a benefits research assistant. Search for federal, state, or nonprofit 
assistance programs related to: "{query}"

Return ONLY a JSON array (no markdown, no explanation) of up to {limit} programs.
Each item must have these exact keys:
- title: program name
- agency_short: agency or org abbreviation  
- objectives: one sentence description
- eligibility: who qualifies
- url: direct link to the program
- category: one of grants, loans, insurance, direct_payments, training, advisory, services, other

Focus on programs NOT commonly found in SAM.gov — local orgs, state programs, nonprofits, 211 resources."""


    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500}
    }).encode()

    url = f"{GEMINI_API_URL}?key={api_key}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())

        text = result["candidates"][0]["content"]["parts"][0]["text"]
        text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        resources = json.loads(text)

        added = []
        for r in resources:
            if isinstance(r, dict) and r.get("title") and r.get("url"):
                ingest_discovered(r)
                added.append(r)

        return added

    except (urllib.error.HTTPError, urllib.error.URLError, KeyError,
            json.JSONDecodeError, IndexError) as e:
        print(f"[Gemini] Search error: {e}")
        return []


if __name__ == "__main__":
    results = search_gemini("rental assistance neurodivergent adults", limit=3)
    print(f"Found {len(results)} results:")
    for r in results:
        print(f"  {r['title']} | {r.get('agency_short')} | {r.get('url')}")
