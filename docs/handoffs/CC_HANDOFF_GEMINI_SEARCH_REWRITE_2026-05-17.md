# Codex Handoff: gemini_search.py Rewrite
**Date:** 2026-05-17  
**From:** Stark  
**To:** Codex  
**Branch:** navigator-gemini-challenge  
**Repo:** /home/hyperion/hearthmind-navigator/

---

## What exists

`src/gemini_search.py` (rescued from OVH, not yet on branch -- copy from
`/home/hyperion/gemini_search.py.from_ovh_20260515`)

Current state is a working draft that uses the wrong auth path and wrong
signature. Do not build on it -- rewrite it.

---

## What to build

### Locked interface contract (do not change this signature)

```python
def search_gemini(
    query: str,
    barriers: list[str] | None = None,
    location: str | None = None,
    language: str = "en"
) -> list[ResourceResult]:
```

`ResourceResult` is a TypedDict defined in `src/constraints.py`
(Codex built it yesterday -- import from there, do not redefine).

If `ResourceResult` is not yet in `src/constraints.py`, define it there
first and import it here. Fields:

```python
class ResourceResult(TypedDict):
    title: str
    source_url: str
    snippet: str
    contact_methods: list[str]          # e.g. ["online", "in-person", "phone"]
    recommended_access_mode: str        # e.g. "online" -- central field
    barriers_active: list[str]          # barriers this resource triggers
```

### Auth

Use Vertex AI SDK, not AI Studio endpoint. No raw API key.

```python
import vertexai
from vertexai.generative_models import GenerativeModel, Tool, grounding

vertexai.init(project="navigator-gemini", location="us-central1")
```

Service account credentials are at `/home/ubuntu/.secrets/vertex-sa.json`
on OVH. On Hyperion, ADC is active (`gcloud auth application-default login`
already run). The code must work with both: check for
`GOOGLE_APPLICATION_CREDENTIALS` env var first; fall back to ADC.

Model: `gemini-2.5-flash`

### Grounding

Use `Tool.from_google_search_retrieval()` -- same grounding behavior as the
old AI Studio `google_search` tool, but via the Vertex SDK.

### Prompt

The prompt must:
1. Pass `barriers` as explicit context: "The user cannot use: {barriers}"
2. Pass `location` if provided
3. Pass `language` -- if `language != "en"`, instruct Gemini to return
   results in that language
4. Ask for `contact_methods` explicitly in the JSON schema
5. Ask for `recommended_access_mode` explicitly -- "how should someone
   without phone access reach this program?"
6. Return JSON only (no markdown fences) -- same pattern as existing file

### Return value

Parse Gemini's JSON response into `list[ResourceResult]`. Log parse errors
but return `[]` on failure -- never raise to caller.

Tag each result with `[web]` in title if caller needs to distinguish from
SAM.gov results. Actually: add a `source: str` field to ResourceResult
(`"gemini"` vs `"samgov"`) -- cleaner than title-tagging.

### Flat-file write path (Weekend 1 scope)

Keep `ingest_discovered()` writing to
`data/discovered_resources.json` for now. Weekend 2 replaces this with
BigQuery. Do not wire BigQuery this weekend.

Schema for the JSON entry should match the hardened schema from v2 schedule
(use `discovered_from_query_hash` not raw query -- hash with `hashlib.sha256`):

```python
{
    "resource_id": str,           # uuid4
    "source_url": str,
    "source_title": str,
    "source_snippet": str,
    "need_category": str,
    "location_scope": str | None,
    "contact_methods": list[str],
    "barriers_active": list[str],
    "barrier_compatibility": list[str],   # barriers this resource works WITH
    "recommended_access_mode": str,
    "discovered_from_query_hash": str,    # sha256 of query, never raw
    "discovered_at": str,                 # ISO 8601 UTC
    "verified": bool,                     # always False at write time
    "verification_status": str,           # "pending"
    "review_notes": str,                  # ""
    "source_agent": str                   # "gemini_search"
}
```

### Tests

File: `tests/test_gemini_search.py`

Required cases (use `unittest.mock.patch` to avoid real API calls):
1. Happy path -- mock returns valid JSON, assert `list[ResourceResult]` shape
2. Barriers passed through -- assert prompt contains barrier text
3. Language != "en" -- assert prompt instructs non-English response
4. Parse failure -- mock returns garbage JSON, assert returns `[]`
5. Auth failure (HTTPError 403) -- assert returns `[]`, logs error
6. `ingest_discovered` deduplication -- same URL twice, only one entry written

---

## What NOT to do

- Do not change `src/constraints.py` -- that's Codex's file from yesterday,
  treat it as read-only except to add `ResourceResult` if it's missing
- Do not wire `search_gemini()` into routes -- CC does that next
- Do not touch `routes_v2.py` at all
- Do not add BigQuery write path -- Weekend 2
- Do not use AI Studio endpoint or raw `GEMINI_API_KEY` for Vertex calls

---

## Commit shape

Two commits:
1. This handoff doc: `docs/handoffs/CC_HANDOFF_GEMINI_SEARCH_REWRITE_2026-05-17.md`
   Message: `docs: gemini_search rewrite handoff spec 2026-05-17`
2. Implementation: `src/gemini_search.py` + `tests/test_gemini_search.py`
   Message (use exactly):
   `feat(gemini): rewrite gemini_search to Vertex SDK + v2 interface contract`

---

## Verification

Before committing:
```bash
pytest tests/test_gemini_search.py -v     # all 6 cases pass
python -c "from src.gemini_search import search_gemini, ResourceResult"
git diff --stat                            # only src/ and tests/ touched
```

Working tree clean before you start. Current HEAD: `a3ab0ca`
