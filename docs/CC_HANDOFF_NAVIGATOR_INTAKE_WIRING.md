# Claude Code Handoff — Wire Intake into /pro and /copilot

**Date:** May 11, 2026
**Author:** Cloud Stark (via Hyperion), with Robin on the scope call
**Build target:** Claude Code
**Expected duration:** One focused session (larger than the Apr 26 `/app` build — two surfaces, plus persistence layer)

---

## Mission

Wire intake persistence into Navigator's two non-public surfaces:

- **`/pro`** (caseworker) — port the intake flow from `/app`, add a **SQLite-backed client store** with REST API, add a **client list + switcher**, persist intake + plan per client. Demo-grade caseworker identity (no real auth this pass).
- **`/copilot`** (local user) — port the intake flow from `/app`, persist intake + plan to **browser localStorage**. Restore plan on revisit with a "Start over" affordance.

`/app` is **untouched**. Its stateless-by-design intake remains the source-of-truth for the intake UI/UX — both new surfaces reproduce the same six screens with identical content and styling.

## The Intake UI Already Exists

**Read first:** `/home/hyperion/hearthmind-navigator/templates/navigator_web.html` (44KB, Apr 26 build). This is `/app`. It contains the six-screen intake (name → goal → barriers → urgency → style → state) → Plan view (Action Card with urgency=today gate + Next Steps + Programs + Tools + Save bar). Treat this file as the **canonical visual + behavioral spec for the intake portion** of both `/pro` and `/copilot`. The intake screens must match: same labels, same option chips, same transitions, same accessibility scaffolding.

**Implementation note:** you may either (a) factor the intake screens out into a shared module (`static/js/intake.js` + matching CSS) and include from all three templates, OR (b) duplicate the intake HTML/CSS/JS inline in each template. Either is acceptable. (a) is cleaner long-term, (b) is faster and matches the current codebase pattern. Your call. If you factor it out, `/app` should be migrated to use the shared module too, and its behavior must remain identical.

## Repo Layout

```
/home/hyperion/hearthmind-navigator/
├── src/
│   ├── routes_v2.py          # CURRENT ROUTES — modify here
│   ├── data_loader.py        # search_programs(), get_categories(), get_context_for_chat()
│   └── (NEW) clients_db.py   # SQLite layer (see §3)
├── templates/
│   ├── navigator_v2.html     # /  — UNTOUCHED
│   ├── navigator_web.html    # /app — UNTOUCHED (visual spec for intake)
│   ├── navigator_sw.html     # /pro — REBUILD
│   └── navigator_copilot.html # /copilot — REBUILD
├── data/
│   ├── (existing data files)
│   └── (NEW) navigator.db    # SQLite store — gitignored
├── tests/
│   └── (NEW) test_clients_api.py
└── docs/
    └── CC_HANDOFF_NAVIGATOR_INTAKE_WIRING.md   # THIS FILE
```

OVH production: `/home/ubuntu/hearthmind-navigator/` (roughly mirrors Hyperion). Local test first; OVH deploy is a separate session.

---

## What to Build

### 1. `/copilot` — local-first persistence (smaller; tackle this first)

**File:** `templates/navigator_copilot.html` (full rebuild — keep filename, replace contents).

**Behavior:**
- **First visit:** show intake flow (six screens, identical to `/app`) → Plan view → autosave intake + plan to `localStorage` under key `nav_copilot_state` as JSON `{ intake: {...}, plan: {...}, saved_at: <iso8601> }`.
- **Subsequent visit:** if `nav_copilot_state` exists, **skip intake, load Plan view directly** from saved data. Show a "saved {time-ago}" indicator and a **Start over** button (top-right) that clears localStorage on confirm and restarts the intake.
- **Edit intake:** affordance from Plan view ("Edit my answers") that reopens the intake flow pre-filled with current values; saving overwrites the stored intake. Plan regenerates accordingly.
- Chat drawer wires through `/api/chat` with the current intake passed as `session` (existing endpoint contract — see `routes_v2.py:103`).
- Programs panel calls `/api/programs` with params derived from intake (same mapping as `/app`).

**No server-side change** for `/copilot`. The route `@bp.route('/copilot')` already exists and renders `navigator_copilot.html` — leave it.

**`localStorage` schema:**
```json
{
  "intake": {
    "name": "string|null",
    "goal": "benefits|paperwork|nextsteps|overwhelm|exploring",
    "barriers": ["focus","overwhelm","losing_benefits","paperwork","phone","deadlines"],
    "urgency": "today|week|planning",
    "style": "direct|gentle|fast|minimal",
    "state": "string|null"
  },
  "plan": {
    "action_card": { "title": "...", "steps": [...] } | null,
    "next_steps": [ "...", "..." ],
    "programs_snapshot": [ {id, title, agency_short, url}, ... ],
    "generated_at": "2026-05-11T..."
  },
  "saved_at": "2026-05-11T..."
}
```

---

### 2. `/pro` — caseworker, client store, switcher (the larger half)

**File:** `templates/navigator_sw.html` (full rebuild — keep filename, replace contents).

**Caseworker identity (demo-grade, no real auth this pass):**
- On first visit, prompt: *"Welcome — are you a new caseworker, or do you have an existing ID?"* with two options:
  - **New** → generate UUID, store as `nav_caseworker_id` in localStorage, optionally accept a display name + agency (also localStorage, keys `nav_caseworker_name`, `nav_caseworker_agency`).
  - **Existing** → text input for ID, validate format, store to localStorage.
- All subsequent API calls send `caseworker_id` either as a query param or in request body.
- This is **demo-grade**. Real SSO/org auth is a deferred TODO — leave a comment at the top of `navigator_sw.html` noting this and at the top of `clients_db.py`.

**Main view structure (replaces current hardcoded mockup):**
- **Left rail:** caseworker chip (ID + name + agency), active-client block (or "No client selected" empty state), list of clients with search filter.
- **Main area:** when a client is selected — Plan view (same shape as `/app`) for that client + "Edit intake" affordance + chat panel (the AI Assist panel from the current Apr 24 build, reworked to use real client context).
- **New client button** (top-left or under client list) → intake flow → save → load Plan view for the new client.
- **Archive client** (acts as soft delete — sets `archived_at`, hides from default list, "Show archived" toggle reveals).
- **Switch client** warning matches the existing copy: *"Switching clients ends your current session view. Complete any open notes before switching."* Honor it — confirm before switching if unsaved changes exist.

**Chat panel context:** when sending to `/api/chat`, pass the **active client's intake** as the `session` payload, plus a caseworker context prefix in the user message (preserve the Apr 24 pattern — see `navigator_sw.html:323-329` for the original, but use real values from localStorage + active client instead of hardcoded `CW-2291`/`NV-7742`).

---

### 3. SQLite client store — new module `src/clients_db.py`

**Location of DB file:** `/home/hyperion/hearthmind-navigator/data/navigator.db` (relative path: `data/navigator.db`). Add `data/navigator.db` to `.gitignore`.

**Schema (create on import if absent):**

```sql
CREATE TABLE IF NOT EXISTS clients (
    id            TEXT PRIMARY KEY,
    caseworker_id TEXT NOT NULL,
    name          TEXT NOT NULL,
    state         TEXT,
    intake_json   TEXT,   -- the intake blob (see localStorage schema, same shape)
    plan_json     TEXT,   -- the plan blob (action_card, next_steps, programs_snapshot, generated_at)
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at   TEXT             -- NULL = active, ISO8601 = archived
);
CREATE INDEX IF NOT EXISTS idx_clients_caseworker ON clients(caseworker_id);
CREATE INDEX IF NOT EXISTS idx_clients_active     ON clients(caseworker_id, archived_at);
```

**Module surface (`clients_db.py`):**
- `init_db(db_path: str = "data/navigator.db") -> None` — idempotent schema create.
- `create_client(caseworker_id, name, state=None, intake=None, plan=None) -> dict` — generates UUID id (format: `CL-` + 6 hex chars uppercase, e.g. `CL-7F4DAE`), returns full record.
- `get_client(client_id) -> dict | None`
- `list_clients(caseworker_id, include_archived=False) -> list[dict]` — sorted by `updated_at` desc.
- `update_client(client_id, *, name=None, state=None, intake=None, plan=None) -> dict` — partial update; only provided fields change; bumps `updated_at`.
- `archive_client(client_id) -> dict` — sets `archived_at`.
- `unarchive_client(client_id) -> dict` — clears `archived_at`.

All functions take an optional `db_path` argument that defaults to the module's configured path. Use `sqlite3` from stdlib — no new dependency.

**JSON columns:** store as `json.dumps(...)` text; deserialize on read. Provide a `_row_to_dict(row)` helper that handles the JSON parse + None handling.

---

### 4. REST API — extend `src/routes_v2.py`

Add these endpoints (all under existing `bp` blueprint):

```
POST   /api/clients
       body: { caseworker_id, name, state?, intake?, plan? }
       → 201 { id, caseworker_id, name, state, intake, plan, created_at, updated_at, archived_at }

GET    /api/clients?caseworker_id=<id>&include_archived=<bool>
       → 200 { clients: [...] }

GET    /api/clients/<client_id>
       → 200 { ...full record... }  or 404

PUT    /api/clients/<client_id>
       body: any of { name, state, intake, plan }
       → 200 { ...updated record... }  or 404

POST   /api/clients/<client_id>/archive
       → 200 { ...record with archived_at set... }  or 404

POST   /api/clients/<client_id>/unarchive
       → 200 { ...record with archived_at cleared... }  or 404
```

**No authentication this pass.** Trust the `caseworker_id` from the client. Add a `# TODO: real auth` comment at the top of the route group.

**Input validation:** require `caseworker_id` and `name` on create. Require valid JSON on `intake`/`plan` if provided. Return `400` with a clear `{ error: "..." }` body for validation failures.

**Backward compat:** do not alter `/api/chat`, `/api/programs`, `/api/categories`. They stay exactly as they are.

---

### 5. 508 accessibility — match `/app` standard

The Apr 26 `/app` build set the bar: skip-nav, `role`/`aria` attributes on interactive elements, focus-visible CSS, `aria-live` on chat, `role="log"` on chat container, keyboard navigation end-to-end, WCAG AA color contrast. **`/pro` and `/copilot` must meet the same bar.** Don't defer this.

---

### 6. Tests

Add `tests/test_clients_api.py`:
- `test_create_client_minimal` — POST with just `caseworker_id` + `name`, expect 201 + valid id format.
- `test_create_client_full` — POST with all fields, verify round-trip.
- `test_list_clients_filters_by_caseworker` — create clients for two different caseworkers, verify list isolation.
- `test_list_clients_excludes_archived_by_default` — verify `include_archived=false` (default) hides archived.
- `test_update_client_partial` — PUT with just `plan`, verify other fields unchanged + `updated_at` bumped.
- `test_get_nonexistent_client_returns_404`
- `test_archive_and_unarchive_roundtrip`
- `test_validation_rejects_missing_caseworker_id`
- `test_validation_rejects_missing_name`

Use a temp DB file per test (or `:memory:` if your test setup supports it). Don't pollute `data/navigator.db`.

**Existing tests must still pass.** `tests/test_chat_session.py` (5 tests from the Apr 26 build) covers `/api/chat` backward compat.

---

## What NOT to Do

- Don't touch `/` (navigator_v2.html) or `/app` (navigator_web.html) — except optionally to migrate `/app` to a shared intake module if you factor one out, in which case behavior must remain identical.
- Don't add real auth/login/SSO. Demo-grade caseworker ID in localStorage is the scope.
- Don't add Gemini — that's a separate handoff (Navigator queue, the board).
- Don't deploy to OVH from this session. Local test only. Robin will deploy after review.
- Don't add new Python dependencies. `sqlite3` is stdlib; that's all you need.
- Don't break the existing `/pro` AI Assist panel UX — preserve the Apr 24 collapsible right-rail pattern, just wire it to real client context instead of the hardcoded mockup values.
- Don't migrate the `CW-2291`/`NV-7742`/`Sarah W.` demo data into the new DB. Those were a mockup. The new flow starts empty — the caseworker creates their first real (or test) client through the new flow.

## Success Criteria

1. `/copilot` shows intake on first visit, plan on revisit, "Start over" wipes localStorage.
2. `/copilot` intake/plan survives browser reload but not localStorage clear.
3. `/pro` first-visit prompt creates a caseworker ID in localStorage; subsequent visits skip it.
4. `/pro` shows an empty client list initially; "New client" runs intake → saves → loads Plan for that client.
5. `/pro` client list filters by caseworker (test with two browsers/profiles).
6. `/pro` Plan view loads existing intake + plan from API for selected client.
7. `/pro` Edit intake → Save updates DB + Plan regenerates.
8. `/pro` Archive client → hides from default list; "Show archived" toggle reveals.
9. `/pro` chat panel sends correct caseworker + client context to `/api/chat`.
10. `/api/clients` endpoints behave per spec; `data/navigator.db` is gitignored.
11. All new tests pass; all existing tests still pass.
12. `/` and `/app` work unchanged.
13. Keyboard navigation works end-to-end on both new surfaces.

## After You Finish

Commit to the current branch (don't merge to main yet). One commit per logical chunk is fine, or one all-up commit — your call.

Suggested commit message for the all-up version:
```
Navigator: wire intake into /pro (SQLite + client switcher) and /copilot (localStorage)

- New: src/clients_db.py (SQLite client store, demo-grade caseworker ID)
- New: /api/clients endpoints (CRUD + archive/unarchive)
- /pro: full rebuild using shared intake from /app + new client list/switcher
- /copilot: full rebuild using shared intake + localStorage persistence
- /app and / unchanged. Backward-compatible with /api/chat session payload.
- TODO: real caseworker auth (SSO/org) — deferred, comment in clients_db.py
```

Robin reviews locally, then OVH deploy is a separate session.

---

## Artifacts Referenced

- **Intake visual + behavioral source:** `/home/hyperion/hearthmind-navigator/templates/navigator_web.html` (the `/app` build, Apr 26)
- **Original `/pro` AI assist pattern:** `templates/navigator_sw.html:323-329` (Apr 24 — frontend-only context injection; preserve the *pattern*, replace the *data*)
- **Existing `/api/chat` session contract:** `src/routes_v2.py:103` onward
- **Apr 26 precedent handoff:** `docs/CC_HANDOFF_NAVIGATOR_WEB.md` (same shape, smaller scope)
- **Active board reference:** the "Navigator queued items" → "Intake wiring across all three surfaces" item

---

*Handoff prepared May 11, 2026 by Cloud Stark.*
*If anything is ambiguous, ask Robin. Don't guess.*
