# Claude Code Handoff — Build Navigator: Web (navigator_web.html)

**Date:** April 18, 2026
**Author:** Cloud Stark (via Hyperion), with Robin + Grey on the spec **Build target:** Claude Code **Expected duration:** One focused session

---

## Mission

Port the April 1 Navigator: Web mockup (v5, approved Robin + Stark + Grey) into a deployable Flask template. Replace the existing `/app` consumer face (currently `navigator_client.html`) with a full intake-first experience that feeds both the `/api/programs` filter and the `/api/chat` system prompt.

## The Spec Is Already Written

**Read first:** `/home/hyperion/hearthmind-navigator/docs/specs/navigator_web_v3.html` — this is the v5 approved spec, in artifact-HTML form (450 lines). It IS the visual + behavioral spec: six-screen intake (name → urgency → goal → barriers → location/state → review) → Plan view with pinned Ask chat panel + Save-to-PDF bar. Read it as both spec AND visual reference — every screen, every option label, every state transition, every visual treatment is in there. The structure of the new `navigator_web.html` template should mirror this artifact closely. Treat the artifact as source of truth for UX and content. This handoff is operational and technical only.

**Note:** This handoff was originally written Apr 18 and referenced a markdown spec (`navigator_web_build_spec.md`) that was never authored. The artifact-HTML at `docs/specs/navigator_web_v3.html` (recovered Apr 24) is the v5 spec. There is no separate markdown spec — the artifact is the spec.

## Repo Layout (Hyperion)

```
/home/hyperion/hearthmind-navigator/
├── src/
│   ├── app.py              # Flask app factory
│   ├── app_v2.py           # v2 variant
│   ├── routes_v2.py        # CURRENT ROUTES — this is where /app lives
│   ├── routes.py           # legacy (leave alone)
```
│   ├── data_loader.py      # search_programs(), get_categories(), get_context_for_chat()
│   └── ...
├── templates/
│   ├── navigator_v2.html   # current / (Mission Control style)
│   ├── navigator_client.html   # current /app — BEING REPLACED
│   ├── navigator_sw.html   # /pro
│   ├── navigator_copilot.html  # /copilot
│   └── base.html
├── static/
│   ├── style.css
│   └── img/
└── docs/
    ├── specs/navigator_web_v3.html # READ FIRST — v5 spec (artifact-HTML)
    └── CC_HANDOFF_NAVIGATOR_WEB.md   # THIS FILE
```

OVH production: `/home/ubuntu/hearthmind-navigator/` (roughly mirrors Hyperion). Deploy after local test.

## What to Build

### 1. New template: `templates/navigator_web.html`

Single file. Vanilla HTML + CSS + JS (no framework). Follow the spec exactly for:
- Screen 0 (name intro) through Screen 5 (state)
- Plan view with conditional Action Card (urgency=today gate)
- Next Steps with deterministic mapping from goal + barriers
- Programs section wired to `/api/programs`
- Tools section (phone script helper, letter helper)
- Orient line, save bar, chat drawer

Intake state lives in a single JS object in memory only. No localStorage. No cookies. Discarded on tab close. This is non-negotiable — Navigator: Web is stateless by design.

### 2. Update route: `src/routes_v2.py`

The `/app` route currently renders `navigator_client.html`. Change it:

```python
@bp.route('/app')
def client_app():
    return render_template('navigator_web.html')
```

**Do NOT change `/` yet.** Per spec's build order, `/` stays on `navigator_v2.html` until we've tested the new flow at `/app`. Swap-in of `/` happens in a later step once Robin confirms.

### 3. Wire intake → `/api/programs`

The existing endpoint contract (from `routes_v2.py`):

```
GET /api/programs?q=<query>&category=<cat>&agency=<ag>&limit=50&offset=0
```

Intake → params mapping (derived from spec):
- `q`: optional free-text, not from intake
- `category`: mapped from `goal` value:
  - `benefits` → relevant SAM.gov categories (benefits, assistance)
  - `paperwork` → legal/appeals categories
  - `overwhelm` → resources, support
  - `exploring` → no filter, show mixed
  - `nextsteps` → no filter
- State filtering: existing endpoint does not filter by state. Add client-side filter on returned results using `p.agency_short` and text-match on state name, OR add `state` param to `search_programs()` in `data_loader.py` if the data supports it. Check `data_loader.search_programs()` signature before deciding.

### 4. Wire intake → `/api/chat` system prompt

The existing `/api/chat` endpoint hardcodes a system prompt. Modify it to accept optional session context and inject it:

```python
# In the /api/chat handler:
data = request.get_json(force=True)
message = data.get('message', '').strip()
history = data.get('history', [])
session = data.get('session', {})  # NEW — intake context
```

Build the system prompt from the spec's template (section "AI Chat System Prompt Template" in the v5 spec). Fall back to the current hardcoded prompt if `session` is empty (preserves backward compatibility with `navigator_v2.html`).

The frontend sends the session object from the in-memory intake state on each chat request. Nothing is persisted server-side.

### 5. 508 accessibility (spec section)

Per spec, these are a blocker for VA production — implement during the build, don't defer:
- `aria-label` on icon buttons
- `role` attributes on option buttons
- Skip-nav link at top
- Keyboard focus indicators in CSS
- `aria-live` region on chat messages
- `role="log"` on chat container
- Verify color contrast WCAG AA

### 6. No tests expected for the template itself

Templates are visual and behavior-verified manually. But:
- If you modify `/api/chat` to accept the session param, add a basic test that it still works when `session` is absent (backward compat).
- If you add a `state` param to `search_programs()`, add a test for the filter.

## What NOT to Do

- Don't touch `navigator_v2.html` (current `/`)
- Don't touch `navigator_sw.html` (`/pro`) or `navigator_copilot.html` (`/copilot`)
- Don't add localStorage, cookies, or any persistence
- Don't add account/login UI
- Don't add Gemini — that's task #3 on the board, after this lands
- Don't break the existing `/api/programs` or `/api/categories` contracts
- Don't add new Python dependencies unless absolutely necessary

## Success Criteria

1. `/app` renders the new intake-first experience
2. Intake flows through six screens per spec
3. Name field optional, skippable, and propagates to chat when provided
4. Urgency=today shows Action Card; other values hide it
5. Plan view's Programs section calls `/api/programs` with filter params derived from intake
6. Opening the chat drawer sends a request to `/api/chat` with session context injected into the system prompt
7. Nothing persists after tab close — reload = fresh start
8. Keyboard-navigable end-to-end
9. `/` (navigator_v2) still works unchanged
10. `/pro` and `/copilot` still work unchanged

## After You Finish

Commit to the current branch (don't merge to main yet). Robin will review locally, then we deploy to OVH production (`15.204.75.156`) manually after confirming. OVH deploy is a separate session.

Add a note in the commit message: `"Navigator: Web v5 — intake-first /app, per April 1 spec. /  stays on v2 until swap-in approved."`

---

## Artifacts Referenced

- **Spec (read first):** `/home/hyperion/hearthmind-navigator/docs/specs/navigator_web_v3.html` (artifact-HTML, 450 lines, IS the spec)
- **Original mockup (reference):** Claude chat `https://claude.ai/chat/e3f0598f-706f-4541-b4e8-31d14abecc4c` — interactive HTML mockup with six screens + plan view. If you have browser access, use as visual reference. If not, spec is authoritative.
- **Active board:** `/mnt/c/Users/Vader/HearthMind/HEARTHMIND_ACTIVE_BOARD.md` — this build corresponds to Navigator audit step #3 ("Plug in existing intake work")

---

*Handoff prepared April 18, 2026 by Cloud Stark.*
*If anything is ambiguous, ask Robin. Don't guess.*
