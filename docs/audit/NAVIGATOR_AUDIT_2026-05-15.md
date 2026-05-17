# Navigator Read-Only Optimization Audit - 2026-05-15

Audit target: `/home/hyperion/hearthmind-navigator/`  
Observed branch/HEAD: `main` at `71e4195`  
Scope: current Hyperion repo only. OVH deploy copy was not analyzed.  
Mode: analysis/report only. No source edits, refactors, package installs, or commits.

## Executive Summary

Navigator already captures accessibility barriers in structured intake state and passes them into the Azure GPT-4o chat prompt. That is good raw material. The main weakness is that constraints are advisory, not enforced. The phone barrier is acknowledged in prompt text, deterministic next-step prep, and the May 11 benefits action-card fix, but it is not used in resource retrieval, filtering, contact-method ranking, or final recommendation validation.

The specific failure case, "I need food help, but phone calls are really hard for me," is still likely to leak phone-first advice through chat, resource config, 211-derived data, or generic step templates. The committed benefits-goal fix prevents "Call 211" in one urgent benefits action-card branch, but the resource/recommendation layer has no general phone-avoidance policy.

There is also a current-code vs. operational-context split: the prompt says BigQuery is part of the structured data/resource layer, but the repo at `71e4195` routes `/api/programs` through an in-memory SAM.gov CSV loader. BigQuery appears only in `check_bq.py`, not in live Flask routes. This should be treated as an architecture gap or deployment drift until verified.

## 1. Architecture Map

### User-facing chat flow

- `/` renders `templates/navigator_v2.html`, a search-and-chat interface without intake/session context.
- `/app` renders `templates/navigator_web.html`, the public/client intake flow plus plan and chat.
- `/pro` renders `templates/navigator_sw.html`, the caseworker/client-store surface.
- `/copilot` renders `templates/navigator_copilot.html`, the localStorage-persistent personal surface.
- All chat-capable surfaces post to `POST /api/chat` in `src/routes_v2.py`.
- `/app`, `/pro`, and `/copilot` send structured `session` data including `name`, `goal`, `barriers`, `urgency`, `style`, and `state`; `/` sends only message/history.

### Backend/API routes

- `src/app_v2.py` creates the Flask app, preloads programs, and registers `routes_v2.bp`.
- `src/routes_v2.py` owns current live routes:
  - `GET /api/programs`
  - `GET /api/categories`
  - `POST /api/chat`
  - `GET /pro`, `/app`, `/copilot`
  - CRUD-ish `/api/clients` endpoints for the caseworker store.
- `src/app.py` and `src/routes.py` are legacy/static YAML surfaces for `/benefits`, `/resources`, `/checklist`, and `/timeline`.

### Model/provider configuration

- Current chat path is Azure OpenAI Chat Completions, configured by:
  - `AZURE_OPENAI_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_DEPLOYMENT`, defaulting to `gpt-4o`
- The API version is hardcoded as `2024-08-01-preview`.
- The system prompt is assembled by `_build_system_prompt(session)`.
- The proposed Gemini search file at `/home/hyperion/gemini_search.py.from_ovh_20260515` is not wired into `routes_v2.py` and still uses AI Studio direct API (`generativelanguage.googleapis.com`) rather than the working Vertex path described in operational context.

### BigQuery integration

- Live route code does not use BigQuery.
- `src/data_loader.py` explicitly says it reads a SAM.gov CSV and builds an in-memory program list with "no BigQuery, no auth."
- `check_bq.py` queries `navigator_benefits.programs` in project `spheric-duality-466022-p6`, but this is a standalone diagnostic/check script.
- Audit interpretation: BigQuery may exist operationally or historically, but at HEAD `71e4195` it is not in the live user-facing retrieval path.

### Resource lookup flow

- `/api/programs` calls `data_loader.search_programs(query, category, agency, limit, offset)`.
- `search_programs()` does substring search over title, objectives, eligibility, and beneficiary, then filters category and agency.
- `/api/chat` calls `get_context_for_chat(message, limit=6)`, which delegates to the same search path using the raw message.
- Frontend plan surfaces use `buildProgramsParams()` to map only:
  - `benefits -> direct_payments`
  - `paperwork -> advisory`
  - selected state, for some states, into a text query.

### Recommendation generation flow

There are two recommendation paths:

- Deterministic frontend plan:
  - `buildActionCardData()` chooses a single urgent action for `urgency === "today"`.
  - `buildStepsData()` generates next steps from goal plus barrier additions.
  - `loadPrograms()` fetches program cards and renders/saves snapshots.
- LLM chat:
  - Server injects top SAM.gov matches into the user message.
  - GPT-4o generates the final conversational response.
  - There is no post-generation validation before returning the reply.

### Summary/handoff generation

- No separate backend summary/handoff generator was found.
- `/pro` saves a generated `plan` JSON snapshot per client: `action_card`, `next_steps`, `programs_snapshot`, and `generated_at`.
- `/copilot` persists similar plan state to localStorage.
- Chat history is browser-side only in the observed code path.

## 2. Key Files and Functions

### Chat behavior

- `src/routes_v2.py`
  - `_BASE_SYSTEM_PROMPT`
  - `_BARRIER_NOTES`
  - `_build_system_prompt(session)`
  - `api_chat()`
- `templates/navigator_v2.html`
  - Root chat UI without structured intake context.
- `templates/navigator_web.html`
  - `/app` chat sender passes intake as `session`.
- `templates/navigator_sw.html`
  - `/pro` AI Assist with active client context.
- `templates/navigator_copilot.html`
  - `/copilot` localStorage-backed chat and intake context.

### Intake parsing/storage

- Frontend intake objects:
  - `/app`: `intake = { name, goal, barriers, urgency, style, state }`
  - `/pro`: reads/writes client intake via API.
  - `/copilot`: reads/writes `nav_copilot_state` localStorage.
- Backend storage:
  - `src/clients_db.py` stores `intake_json` and `plan_json` in SQLite.
  - `src/routes_v2.py` validates `intake` and `plan` as JSON objects for client APIs.

### BigQuery

- `check_bq.py` only. No live route integration found.

### Resource queries

- `src/data_loader.py`
  - `load_programs()`
  - `search_programs()`
  - `get_context_for_chat()`
  - `get_categories()`
- `src/fetch_211.py`
  - `search_211()`
  - `get_service_detail()`
  - `normalize_detail()`
  - Not wired into current routes.

### Ranking/filtering

- `data_loader.search_programs()` does simple substring filtering and preserves source order.
- Frontend `buildProgramsParams()` maps a few goals to broad SAM categories.
- No contact-method ranking, barrier-aware filtering, or final validation layer was found.

### Final recommendation formatting

- Deterministic:
  - `buildActionCardData()` in `/app`, `/pro`, `/copilot`.
  - `buildStepsData()` in `/app`, `/pro`, `/copilot`.
  - `renderPrograms()` in each template.
- LLM:
  - GPT-4o response from `api_chat()` is returned directly.

### Tests/evals

- `tests/test_chat_session.py` covers `_build_system_prompt()` backward compatibility and session context injection.
- `tests/test_clients_api.py` covers SQLite client API behavior.
- No persisted browser regression harness was found for action-card behavior.
- No eval harness exists for recommendation quality, contact constraints, or LLM safety/constraint adherence.

## 3. Accessibility Constraint Handling

### Capture

The intake UI captures barriers as a structured array. The recognized backend barrier keys are:

- `focus`
- `overwhelm`
- `losing_benefits`
- `paperwork`
- `phone`
- `deadlines`

The `phone` barrier appears in all three intake surfaces. The backend converts it to prompt text: "phone calls are a barrier - suggest scripts or written alternatives when possible."

### Structured storage

- `/app`: barrier state is in-memory during the browser session.
- `/copilot`: barrier state persists in localStorage.
- `/pro`: barrier state persists in SQLite as `intake_json`.
- Chat receives barriers as structured session payload when sent from `/app`, `/pro`, or `/copilot`.

### Use in queries, filters, ranking, or validation

- Queries: no. `buildProgramsParams()` does not include barriers.
- Filters: no. `search_programs()` has no barrier/contact fields.
- Ranking: no. There is no scoring function.
- Final validation: no. GPT-4o output is returned directly, and deterministic recommendations do not pass through a constraint validator.

### Enforced vs. mentioned

Enforced:

- Benefits action card has a phone-barrier branch in `/app`, `/pro`, and `/copilot`.

Mentioned or softened:

- `_build_system_prompt()` tells GPT-4o to suggest scripts or written alternatives.
- `buildStepsData()` prepends a phone-prep step when `phone` is selected.
- The phone script helper supports callers but does not avoid calls.

Not enforced:

- Food, housing, healthcare, mental health, crisis, paperwork, and generic next-step recommendations.
- Resource cards that contain only phone numbers.
- Chat responses that recommend phone calls.
- 211 results if/when `fetch_211.py` or Gemini search is wired in.

## 4. Failure Case Analysis

Scenario: "I need food help, but phone calls are really hard for me."

### What current system likely does

Path depends on surface:

- On `/`: sends the message without structured barriers. GPT-4o receives top CSV matches for raw message text and may infer the barrier from prose, but there is no structured enforcement.
- On `/app`, `/pro`, `/copilot`: if the user previously selected `phone` in intake, the system prompt says phone calls are a barrier. If they only type it in chat, no code extracts and stores it into `session.barriers`.
- The resource panel probably does not target food well unless the query itself searches food; goal-to-category mapping only handles `benefits` and `paperwork`.
- If `urgency === "today"` and `goal === "benefits"` plus `phone` barrier, the action card recommends visiting 211.org rather than calling 211. If the goal is not `benefits`, this specific fix does not apply.

### Where "call 211" or phone-based advice enters

- Deterministic action cards:
  - Benefits/no-phone-barrier branch says "Call 211..."
  - May 11 patch changes only benefits + phone barrier to "Visit 211.org..."
- Static resources:
  - `templates/resources.html` includes a 211 fallback: "Call 211 or visit the website."
  - YAML resources include many phone-only or phone-first entries.
- 211 integration:
  - `src/fetch_211.py` normalizes `phone` into cards and has no alternate-contact schema or barrier-aware ranking.
- LLM:
  - GPT-4o may recommend "call 211" from general knowledge, from a future 211/Gemini result, or from resource snippets, because there is no post-generation constraint check.

### Default template vs retrieval vs fallback vs model

Likely sources:

- For urgent benefits action card without `phone`: deterministic template.
- For food-specific chat: mostly model response plus SAM.gov context. Current CSV retrieval is federal-program-oriented, not local food pantry oriented.
- For local resource pages: static YAML/templates.
- For future 211/Gemini search: retrieved resource contact data and model synthesis.

### Responsible files/functions

- `templates/navigator_web.html`: `renderActionCard()`, `buildStepsData()`, `buildProgramsParams()`, `postChat()`.
- `templates/navigator_sw.html`: `buildActionCardData()`, `buildStepsData()`, `buildProgramsParams()`, client plan persistence.
- `templates/navigator_copilot.html`: same pattern as `/app`.
- `src/routes_v2.py`: `_build_system_prompt()`, `api_chat()`.
- `src/data_loader.py`: `search_programs()`, `get_context_for_chat()`.
- `src/fetch_211.py`: proposed/unwired 211 resource normalization.
- `config/local_resources.yaml` and `config/resources.yaml`: phone-heavy resource metadata.

## 5. Optimization Opportunities

### Constraint extraction

Minimal improvement:

- Add a small deterministic text extractor in `api_chat()` before prompt assembly:
  - Detect phrases like "phone calls are hard", "can't call", "no phone", "text/email only", "online only".
  - Merge detected barriers into a transient `effective_session`.
  - Return detected barriers in the API response for frontend confirmation later.

Better follow-up:

- Persist confirmed extracted barriers into `/copilot` localStorage and `/pro` client intake only after user confirmation.

### Contact method ranking

Introduce normalized contact metadata:

```json
{
  "contact_methods": ["online", "email", "text", "phone", "in_person"],
  "primary_contact": "online",
  "phone_required": false,
  "has_non_phone_path": true
}
```

Then rank resources:

- If `phone` barrier: online/text/email first, phone-only last.
- If `transportation` barrier: remote/online/mail first, in-person last.
- If crisis: preserve emergency phone/text/chat options but label why urgency overrides normal ranking.

### Recommendation validation

Add a final lightweight validator for both deterministic plan objects and LLM replies:

- Input: `effective_session`, candidate action/reply/resource cards.
- Detect forbidden or discouraged contact actions.
- If a mismatch exists, either rewrite deterministic copy or append a correction:
  - "Because phone calls are hard, start with the online form/chat option first."

### Fallback handling when only phone resources exist

Do not hide all options silently. Use a structured fallback:

- "I only found phone-first options for this need."
- "Lowest-phone path: use 211.org search page, ask a support person to call with you, or use a script."
- "Would you like me to help draft a message/request instead?"

### User-facing fit explanation

Every recommendation card should be able to say:

- Need match: "Food assistance"
- Constraint match: "Has website/search option"
- Caveat: "Phone listed, but not required as first step"
- Next action: "Open URL and search by ZIP"

This is challenge-friendly because it makes optimization visible and auditable.

## 6. Google Challenge Readiness

### Track 2: Optimize Existing Agents

Navigator is a good Track 2 candidate because:

- It is an existing working agentic/user-assistive system.
- It has real failure evidence.
- It has structured intake, persistence, resource retrieval, and LLM synthesis.
- The optimization target is concrete: enforce accessibility constraints across retrieval and recommendation.

The strongest story is not "swap Azure for Gemini." It is "make an existing benefits-navigation agent constraint-aware, testable, and safer for disabled/neurodivergent users."

### Gemini Challenge Edition branch

A Gemini branch could:

- Keep current Azure production path stable.
- Add Vertex Gemini 2.5 Flash as the challenge model path.
- Use BigQuery/CSV/211/Gemini Search as retrievers.
- Add evaluator tests for constraint adherence.

### Existing Google Cloud/BigQuery usage

- BigQuery exists as a check script and in operational context, but not in live route code.
- Current code retrieval is local CSV. If BigQuery is live elsewhere, the repo should be reconciled with deployed behavior before making challenge claims.

### What must change to make Gemini central enough

- Replace or branch `api_chat()` provider abstraction so Gemini via Vertex can generate chat responses.
- Port proposed `gemini_search.py` away from AI Studio API key to Vertex service-account auth.
- Wire Gemini search as a fallback/augmentation path, not as unreviewed auto-truth.
- Add citations/source metadata and human-review flags for discovered resources.
- Add eval cases demonstrating Gemini respects phone/no-transport/online-only constraints.

### What should not change yet

- Do not destabilize production Azure GPT-4o chat until a provider abstraction and evals exist.
- Do not wire broken AI Studio `gemini_search.py` directly.
- Do not auto-ingest Gemini-discovered resources into user-visible recommendations without review/verification.
- Do not claim BigQuery is live in this code path until route integration is present or deployment drift is documented.

## 7. Testing/Evaluation Plan

### Unit tests

- `_build_system_prompt()`:
  - Existing phone barrier still appears.
  - Typed "phone calls are hard" extractor adds `phone`.
  - Unknown barriers are ignored or preserved safely.
- `buildActionCardData()` harness:
  - For every goal, phone barrier does not produce phone-first action copy.
  - Benefits/no barrier still matches existing behavior.
- `buildStepsData()`:
  - Phone barrier produces a non-phone alternative step when possible, not only a call-prep step.
- Resource ranking:
  - Online/text/email resources rank above phone-only when `phone` barrier exists.
  - Phone-only resources are retained with caveat when no alternatives exist.

### Browser/e2e tests

Queued Playwright/Selenium should cover:

- `/app`, `/pro`, `/copilot` intake -> plan for each barrier.
- Reload persistence for `/copilot`.
- Client plan persistence for `/pro`.
- Action-card visible/hidden behavior by urgency.
- No "Call 211" text when phone barrier is selected for benefits and other goals after future fix.

### LLM/eval cases

1. Phone calls difficult:
   - "I need food help, but phone calls are really hard for me."
   - Expected: online/text/walk-in alternatives first; no phone-first recommendation.
2. No transportation:
   - "I need housing help but I can't travel."
   - Expected: remote/online/mail options prioritized.
3. Low energy/executive dysfunction:
   - "I need help but can only do one tiny step."
   - Expected: one-step plan, no long list.
4. Needs online-only:
   - "I can only use online forms or chat."
   - Expected: phone/in-person filtered or caveated.
5. Urgent crisis vs non-crisis:
   - Crisis: allow 988 call/text/chat with clear urgency explanation.
   - Non-crisis: avoid crisis escalation and phone-first defaults.
6. Only phone resources available:
   - Expected: transparent fallback, script/support-person option, no false claim that non-phone exists.

### Regression fixtures

Create small synthetic resource fixtures with contact-method combinations:

- online + phone
- phone only
- text only
- in-person only
- unknown contact method

These fixtures make ranking deterministic and independent of SAM.gov/211/Gemini variance.

## 8. Priority Recommendations

### Top 5 highest-impact fixes

1. Add a central `constraints`/`barriers` model that normalizes intake and chat-extracted barriers into one `effective_session`.
2. Add contact-method metadata and barrier-aware ranking for resource cards.
3. Add a final recommendation validator that blocks or rewrites phone-first advice when `phone` is a barrier.
4. Generalize the May 11 phone-barrier action-card fix beyond `benefits` to all goal/action-card branches.
5. Add persisted JS/browser regression tests for action cards and barrier handling.

### Top 5 lowest-risk quick wins

1. Strengthen `_BARRIER_NOTES['phone']` from "suggest scripts or written alternatives when possible" to "do not recommend phone-first steps when a written/online/text option exists."
2. Add a tiny phrase extractor for phone/no-call/online-only constraints in `api_chat()`.
3. Add a "no phone needed" / "phone listed" badge in rendered program/resource cards once metadata exists.
4. Add unit tests around the current benefits phone-branch in all three templates or a shared extracted helper.
5. Add a markdown architecture note documenting current retrieval reality: CSV live path, BigQuery diagnostic only, Gemini proposed/unwired.

### Risks or unknowns

- Deployment drift: OVH may contain untracked `src/gemini_search.py` and possibly behavior not present in Hyperion repo.
- BigQuery drift: operational context says BigQuery participates; current code does not.
- Current resource data lacks normalized contact fields, so barrier-aware ranking needs metadata work.
- GPT-4o may still produce generic "call 211" unless constrained and validated.
- Phone avoidance has crisis exceptions; tests must distinguish urgent safety support from ordinary resource navigation.

### Suggested next Codex pass

Implementation pass, still small and reviewable:

1. Extract a pure Python `constraints.py` helper:
   - `normalize_barriers(session, message)`
   - `has_barrier(effective_session, "phone")`
   - `validate_recommendation_text(text, effective_session)`
2. Add tests for phrase extraction and text validation.
3. Use it inside `api_chat()` to strengthen the system prompt and add a post-response caveat when needed.
4. Extract/shared-test `buildActionCardData()` logic or add a lightweight JS harness to cover `/app`, `/pro`, `/copilot`.
5. Only after that, design the Vertex Gemini branch with provider abstraction and evals.

