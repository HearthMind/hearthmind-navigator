# Ground Truth — Navigator code state on May 16, 2026

**Author:** Stark
**Purpose:** Reference for upcoming handoffs (CC validator wiring + Codex gemini_search rewrite). Captures the actual state of three load-bearing files so future handoffs ground in reality rather than the v2 schedule's assumptions.

**Reads:** descriptive only. No spec content here.

---

## File 1: `src/routes_v2.py` — what's currently there (OVH, branch state pre-Weekend-1)

**Total lines:** 320.

### `_BARRIER_NOTES` dict (around lines 60-67)

The barrier vocabulary currently in production is broader than v2's `CANONICAL_BARRIERS`:

```python
_BARRIER_NOTES = {
    'focus':           "brain fog / focus is a barrier — keep responses short and concrete",
    'overwhelm':       "they feel overwhelmed — one thing at a time, no long lists",
    'losing_benefits': "they're afraid of losing existing benefits — be cautious before suggesting changes",
    'paperwork':       "paperwork is hard for them — explain forms in plain language",
    'phone':           "phone calls are a barrier — suggest scripts or written alternatives when possible",
    'deadlines':       "they worry about missing deadlines — surface dates and timing clearly",
}
```

**Six barriers** in production, not the four in v2's `constraints.py` spec. Three (`losing_benefits`, `paperwork`, `deadlines`) are not "accessibility barriers" in the same sense as `phone` / `focus` / `overwhelm` — they're session signals that color tone, not constraints that gate contact-method choice. `transport` is absent from production but in v2's spec.

**The "advisory → blocking" tightening (v2 Saturday item)** targets the `phone` line specifically. Current: *"suggest scripts or written alternatives when possible"* — the word "when possible" makes it advisory. Target shape: language that names phone-only output as not acceptable for this user, leading with online / mail / in-person alternatives.

### `_build_system_prompt(session)` (around line 71-90+)

Builds the LLM system prompt from session signals. Reads `name`, `goal`, `barriers`, `urgency`. For barriers: iterates `session['barriers']`, looks each up in `_BARRIER_NOTES`, joins matching notes into a "Known barriers: ..." line appended to the prompt.

**This is the call site that will need to change for the validator wiring.** The system prompt is the *advisory* layer (telling the model about barriers). The reply-side validator is the *enforcement* layer (catching violations the model produces anyway). Both stay; they're complementary.

### Other relevant context

- `from flask import Blueprint, render_template, request, jsonify, current_app` — uses `current_app` (the pre-gemini-off backup did not — confirms recent work).
- `_BASE_SYSTEM_PROMPT` is a string constant at module scope, ~7 lines, the warm-clear-Navigator persona.
- `_STYLE_GUIDANCE` and `_GOAL_FRAMING` are sibling dicts to `_BARRIER_NOTES`, same shape: signal token → prompt-fragment.

---

## File 2: `src/gemini_search.py` — what's currently there (OVH, 121 lines)

**Status:** Real implementation, NOT a stub. Has been on disk since at least March; not invoked from production routes yet (board confirms wire-in deferred for intake-first).

### Auth path (the load-bearing wrongness)

```python
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# inside search_gemini():
api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    return []
# ...
url = f"{GEMINI_API_URL}?key={api_key}"
req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
```

**This is AI Studio (generativelanguage.googleapis.com), not Vertex.** Uses a raw API key, routes billing to the AI Studio prepayment wallet (the empty one from the original 429 problem). The Apr 24 fix that landed on `routes_v2.py` (`vertex-sa.json` + Vertex SDK + `navigator-gemini` GCP project) *was never applied to this module*. v2 schedule item "Rewrite gemini_search.py to Vertex SDK + service account auth" is asking us to do here what April 24 did at the routes layer.

### Function signature (the schedule's interface contract gap)

**Current:** `def search_gemini(query: str, limit: int = 5) -> list:`

**v2 contract:** `search_gemini(query, barriers=None, location=None, language="en") -> list[ResourceResult]`

Three of the four v2 parameters don't exist yet. `limit` is in current but absent from v2. Naming the gap so the rewrite handoff names both: new signature, deprecate `limit` (or fold into kwarg with default 5).

### Discovery schema (pre-v2-hardening)

Current `discovered_resources.json` entries (file-on-disk, not BigQuery):

```python
{
    "title": str,
    "agency_short": str,
    "objectives": str,
    "eligibility": str,
    "url": str,
    "category": str,           # grants/loans/insurance/direct_payments/training/advisory/services/other
    "verified": bool,           # default False
    "source": str,              # "gemini_search"
    "discovered_at": str,       # ISO timestamp
}
```

**v2's hardened schema** wants additional fields: `barriers_active`, `recommended_access_mode`, `discovered_from_query_hash`, `location_scope`, `contact_methods`, `barrier_compatibility`, `verification_status`, `review_notes`, `source_agent`. And v2 wants this in BigQuery `discovered_resources` table, not a JSON file.

**Migration is two-step:**
1. **Saturday (this weekend):** rewrite auth path. Keep current schema; keep JSON-file persistence. Get Vertex SDK + SA working with the existing simple flow.
2. **Weekend 2:** expand schema to v2 shape; migrate from JSON file to BigQuery `discovered_resources` table.

Don't try to do both in the rewrite. Auth path first, schema second.

### What the module already does well

- `ingest_discovered()` does dedup by URL — that survives any schema migration
- Error handling catches HTTPError / URLError / KeyError / JSONDecodeError / IndexError and returns `[]`
- Markdown fence stripping on Gemini's response (`text.strip().lstrip("```json").lstrip("```").rstrip("```")`) — keep this
- `__main__` smoke-test at the bottom — useful, keep

---

## File 3: `routes_v2.py.pre-gemini-off.bak` (OVH, 144 lines)

This is the *pre-disable* snapshot — what `routes_v2.py` looked like before the Gemini wire-in was commented out for the intake-first deferral. **Useful as restore reference** if the rewrite hits trouble.

**Notable difference from current `routes_v2.py`:** the system prompt and barrier dicts (`_BASE_SYSTEM_PROMPT`, `_STYLE_GUIDANCE`, `_GOAL_FRAMING`, `_BARRIER_NOTES`) **are NOT in the backup** — they were added after April 24. The system-prompt-from-session pattern is newer than the Gemini wire-in.

This means: the eventual Gemini wire-in will need to merge two things that weren't both alive at the same time before — the session-aware system prompt AND the Gemini search-and-ingest layer. Both touch `api_chat()`. The CC handoff will need to call these out.

---

## Implications for upcoming handoffs

### CC handoff for validator wiring (next)

- `constraints.py` (from Codex's current PR) is the import target.
- Integration point is `api_chat()` in `src/routes_v2.py` — after model generates response, before return.
- `_BARRIER_NOTES['phone']` tightening is the *advisory* fix; the validator is the *enforcement* fix. Both happen in the same handoff or back-to-back.
- Don't expand `_BARRIER_NOTES` to include `transport` yet — `transport` lives in `constraints.py` as a *constraint-loop* barrier, not a system-prompt-coloring signal. Different vocabularies, intentionally.

### Codex handoff for gemini_search.py rewrite (after CC)

- Replace urllib + AI Studio key with `google-cloud-aiplatform` SDK + service account at `/home/ubuntu/.secrets/vertex-sa.json` (project: `navigator-gemini`, region: `us-central1`, model: `gemini-2.5-flash` per board's Apr 24 entry — verify against current routes_v2 if it picks a different model).
- Update signature to `search_gemini(query, barriers=None, location=None, language="en") -> list[ResourceResult]`.
- **Keep** the schema-as-JSON-file persistence for now. Schema migration to v2's hardened shape happens Weekend 2.
- **Keep** the dedup-by-URL, error handling, fence-stripping, `__main__` smoke test.
- Add a `verified=False` discovery write *path* (already present); the v2 `verified` provenance + barriers_active fields are Weekend 2.

### Weekend 2 (not this PR)

- BigQuery `discovered_resources` table migration
- Hardened schema fields (`barriers_active`, `recommended_access_mode`, `discovered_from_query_hash`)
- Privacy guardrails: hash query before storing

---

## Verification notes

All three files inspected directly via SSH to OVH (`15.204.75.156` / alias `navigator`) on 2026-05-16 evening. Live production state. Branch on OVH appears to be at `main` HEAD pre-Weekend-1; the `navigator-gemini-challenge` branch only exists on Hyperion repo + origin until CC/Codex push their work and we deploy.

**OVH inventory snapshot:**

```
/home/ubuntu/hearthmind-navigator/src/
├── __init__.py
├── app.py
├── app_v2.py
├── benefits.py
├── clients_db.py
├── data_loader.py
├── fetch_211.py
├── gemini_search.py             ← 121 lines, AI Studio impl, the rewrite target
├── routes.py
├── routes_v2.py                 ← 320 lines, current production
├── routes_v2.py.bak             ← 136 lines, older backup
└── routes_v2.py.pre-gemini-off.bak  ← 144 lines, snapshot before Gemini disable
```

`.env` on OVH (Apr 17): contains `GEMINI_API_KEY` (per board entry); not inspected to avoid leaking secrets. Service account JSON: `/home/ubuntu/.secrets/vertex-sa.json` (chmod 600, project `navigator-gemini`, client_email `743603774896-compute@developer.gserviceaccount.com`).

---

*Logged so the next two handoffs ground in reality. Read this before writing CC's validator handoff or Codex's gemini_search rewrite.*
