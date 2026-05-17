# Navigator Read-Only Optimization Audit — Claude Code

- **Author:** Claude Code (Opus 4.7, 1M context)
- **Date:** 2026-05-15
- **Audit target:** `/home/hyperion/hearthmind-navigator/`
- **Observed HEAD:** `71e4195` on `main`
- **Scope:** current Hyperion repo only. The OVH deploy copy was not examined.
- **Mode:** analysis only — no source edits, refactors, installs, or commits.

A companion Codex pass exists at `docs/audit/NAVIGATOR_AUDIT_2026-05-15.md`. This report was written independently against the same HEAD.

---

## Executive summary

Navigator is structurally close to enforcing accessibility constraints but does not actually do so today. Barriers are captured as structured data on three of four surfaces, included in the Azure GPT-4o system prompt as soft guidance, and reflected in one deterministic surface — the urgent-benefits Action Card — via the May 11 fix at commit `71e4195`. Everywhere else (chat reply text, retrieval, non-benefits Action Cards, legacy template fallbacks, and the public `/` surface) the phone barrier is acknowledged but not enforced.

The food-help failure case is still likely to surface "call 211" or similar phone-first advice. The dominant reason is not the Action Card — that branch is now correct for `goal=benefits + urgency=today + barriers∋'phone'`. The reasons are:

1. The retrieval layer (`get_context_for_chat`) substring-matches the user's full sentence against SAM.gov CSV text, which almost always returns zero results for a conversational message like "I need food help, but phone calls are really hard for me." The model then answers from training-data priors with no retrieved grounding — and training-data priors say "call 211" for food help.
2. The system-prompt barrier text is advisory ("suggest scripts or written alternatives **when possible**"), not blocking. GPT-4o is free to lead with a phone recommendation.
3. The public `/` route (`navigator_v2.html`) does not send session at all (`templates/navigator_v2.html:355`). Anyone arriving without going through intake gets the base prompt with no barrier awareness.
4. Phone-aware Action Card text exists only for the `benefits` goal branch in `buildActionCardData`. The other goals (`paperwork`, `nextsteps`, `overwhelm`, `exploring`, default) are not phone-aware.
5. Universal step text references "a phone call" as a default action mode (`templates/navigator_web.html:857`, mirrored in `_sw` and `_copilot`).
6. Legacy `templates/resources.html:182-188` ships a literal "Call 211" fallback card with no barrier awareness. Currently routed via `/resources` on the legacy `app.py` blueprint.

The most leveraged single change is a **reply-side validator** on `/api/chat` that intercepts phone-first patterns when `session.barriers ∋ 'phone'`. This enforces the constraint regardless of model output and is implementable in well under 50 lines.

---

## 1. Architecture Map

### Two parallel Flask apps

The repo contains two non-overlapping Flask apps that both register a `Blueprint('main', ...)`:

| File | Role | Entry | Blueprint | Templates |
|---|---|---|---|---|
| `src/app_v2.py` | Current product | `run_v2.sh` → `python3 src/app_v2.py` | `routes_v2.bp` | `navigator_v2`, `navigator_web`, `navigator_sw`, `navigator_copilot` |
| `src/app.py` | Legacy YAML surfaces | `run.py` → `create_app()` | `routes.bp` | `index`, `benefits`, `resources`, `checklist`, `timeline` |

`src/app.py` and `src/benefits.py` are both 0 lines (`wc -l src/__init__.py src/app.py src/benefits.py` → 0). `run.py` imports `from app import create_app` and would fail to start — meaning **`run.py` is dead** and the canonical entry is `run_v2.sh`. Both blueprints share the name `main`, so they cannot coexist in one app even if revived.

Implication: the `/resources` and `/benefits` routes from `routes.py` are not actually exposed in production. The "Call 211" fallback HTML at `templates/resources.html:170-189` is dormant but not deleted. It is worth either deleting or wiring through a barrier-aware path.

### Surface → template → session-aware?

| Route | Template | Sends `session`? |
|---|---|---|
| `GET /` | `navigator_v2.html` | **No** — only message + history (line 355) |
| `GET /app` | `navigator_web.html` | Yes (line 1062) |
| `GET /pro` | `navigator_sw.html` | Yes (line 1333), plus caseworker context prefix prepended to message |
| `GET /copilot` | `navigator_copilot.html` | Yes (line 995) |

`navigator_client.html` exists (474 lines) and contains a fetch to `/api/chat` at line 440 but is not bound to any route in `routes_v2.py`. Likely orphaned.

### Chat data flow (current)

```
User message
  → [client] fetch /api/chat with { message, history, session? }
  → [routes_v2.api_chat]
  → data_loader.get_context_for_chat(message, limit=6)
       → search_programs(query=message) — substring match on SAM.gov CSV
  → _build_system_prompt(session) — adds goal/barriers/urgency/style/state framing
  → Azure OpenAI Chat Completions (gpt-4o, api-version 2024-08-01-preview)
  → return { reply, programs[:3] }
```

### Resource layer

- **SAM.gov CSV** is the only live retrieval source, read once at startup from a hardcoded path: `/home/hyperion/hearthmind-navigator/data/raw/sam_assistance_listings_20260207.csv` (`src/data_loader.py:16`). That `raw/` directory is **not present in the repo at HEAD** (`ls data/` shows only `fetch_sam_al.py`, `spokane_*.json`, `wa_providers_npi.json`). Whether OVH has the file is a deployment-state question outside this audit's scope.
- **BigQuery** is referenced only by `check_bq.py` against `spheric-duality-466022-p6.navigator_benefits.programs`. Not wired into any route. Operationally relevant: the audit prompt mentions BigQuery as part of "the structured data/resource layer" — that is not true in the live code at this HEAD.
- **211 NDP** is implemented in `src/fetch_211.py` (253 lines, with taxonomy map and accessibility normalization), but is not imported by any route or by `data_loader`. Currently a standalone smoke-test script.
- **Spokane / WA provider JSON** (`data/spokane_*.json`, `data/wa_providers_npi.json`) is not loaded by any route. These files are phone-only contact records — if/when wired, they are pure phone-first data and need access-mode tagging before use.
- **Legacy YAML** (`config/resources.yaml`, `config/local_resources.yaml`, `config/benefits.yaml`) feeds only the dormant `routes.py` blueprint.

### Recommendation generation / handoff generation

There is no server-side recommendation generation or handoff generation. The Action Card, Steps, and chat opener are all generated client-side from the local `intake` object via `buildActionCardData()`, `buildStepsData()`, and `renderChatOpener()` in each intake-aware template. Server-side, only the chat reply is generated, and it consists of one Azure OpenAI call per user message with no recommendation post-processing.

---

## 2. Key Files and Functions

| Concern | File | Key symbols |
|---|---|---|
| Chat behavior | `src/routes_v2.py` | `api_chat`, `_build_system_prompt`, `_BASE_SYSTEM_PROMPT`, `_BARRIER_NOTES`, `_GOAL_FRAMING`, `_STYLE_GUIDANCE` |
| Intake capture (client) | `templates/navigator_web.html` | `toggleBarrier`, `intake` (line 698), payload at line 1062 |
| Intake capture (pro) | `templates/navigator_sw.html` | `toggleBarrier`, `intake` (line 678), `prefillBarriers` (line 1206) |
| Intake capture (copilot) | `templates/navigator_copilot.html` | `toggleBarrier`, `intake` (line 556), `prefillBarriers` (line 726) |
| Resource retrieval | `src/data_loader.py` | `load_programs`, `search_programs`, `get_context_for_chat` |
| Action Card logic | three surface templates | `buildActionCardData` / `renderActionCard` (web: line 806; sw: line 832 + builder at 891; copilot: line 832 + builder at 742) |
| Steps logic | same | `buildStepsData` / `renderSteps` (web: line 847; sw: line 920; copilot: line 775) |
| Client store | `src/clients_db.py`, `src/routes_v2.py:232-320` | `create_client`, `list_clients`, `get_client`, `update_client`, archive/unarchive |
| 211 integration (unused) | `src/fetch_211.py` | `search_211`, `get_service_detail`, `normalize_detail` (has `wheelchair`, `spanish`, `asl` flags — accessibility primitives already exist here) |
| Proposed Gemini layer | `/home/hyperion/gemini_search.py.from_ovh_20260515` | `search_gemini`, `ingest_discovered`, `load_discovered`. Uses AI Studio direct URL (broken). |
| Tests — prompt builder | `tests/test_chat_session.py` | 4 tests, all covering `_build_system_prompt` |
| Tests — client store | `tests/test_clients_api.py` | 200 lines, CRUD validation |
| **Missing tests** | — | reply path, retrieval, action card (only ephemeral May 11 harness), end-to-end |

---

## 3. Accessibility Constraint Handling

### Capture

The barrier `'phone'` is one of six structured values: `focus`, `overwhelm`, `losing_benefits`, `paperwork`, `phone`, `deadlines`. Captured identically on `/app`, `/pro`, `/copilot`. **Not captured on `/`**. The chat free-text channel is the only way a barrier can enter the prompt on the public root surface, and `/` does not parse the message for barriers — it sends only `{ message, history }`.

### Stored

- Client-side: in the `intake` object (per-template, mostly in-memory; `/copilot` persists to localStorage; `/pro` posts to `/api/clients` and the SQLite store at `data/navigator.db`).
- Server-side: as JSON in the `intake` column of the `clients` table for `/pro` clients only.

### Used in queries

**No.** `get_context_for_chat(message, limit=6)` does not see the session at all (`src/routes_v2.py:128`). Retrieval is keyed only on the raw message text. Barriers do not influence which SAM.gov programs are surfaced.

### Used in filtering / ranking

**No.** Each retrieved program is rendered into the context block with only `title`, `agency_short`, `objectives`, `eligibility`, and `url`. No `access_mode` or contact-method metadata. No re-rank by barrier.

### Used in final validation

**No.** The Azure response is returned to the client verbatim (`src/routes_v2.py:183-184`). There is no post-processing layer that checks the reply against the session's barriers.

### Where barriers actually take effect

1. `_build_system_prompt` (`src/routes_v2.py:71-106`) — soft guidance:
   ```python
   'phone': "phone calls are a barrier — suggest scripts or written alternatives when possible"
   ```
2. Action Card text for `goal=benefits + urgency=today` (`templates/navigator_web.html:815-824`, mirrored in `_sw` and `_copilot`). Branches to "Visit 211.org and search by your ZIP" when phone is a barrier. **Only for the `benefits` goal.** Other goals share their text irrespective of `phone`.
3. Steps adjustments (`templates/navigator_web.html:885-887`, mirrors): inserts a "Write your one phone question on paper before you call" step. This **assumes the call will happen** and provides script-prep, rather than substituting a non-phone alternative. It contradicts rather than respects the barrier.
4. The `openTool('phone')` Phone Script Helper modal — useful as a coping aid but again presupposes a call.

### Where barriers are mentioned but ineffective

- The first-step copy in the `paperwork` goal includes `"a phone call"` as one of three example asks (`templates/navigator_web.html:857`, mirrored on `_sw:929` and `_copilot:784`). This text is constant regardless of barrier.
- The chat opener for `goal=benefits` says "want me to walk through how to figure out which one fits first?" with no phone-mode awareness.

---

## 4. Failure Case Analysis — "I need food help, but phone calls are really hard for me."

### What happens path-by-path

**Path A: user arrives on `/` (no intake).**
- Session = none. `_build_system_prompt({})` returns the base prompt only, which contains no barrier guidance.
- `get_context_for_chat("I need food help, but phone calls are really hard for me", limit=6)` substring-matches the full sentence against `title`, `objectives`, `eligibility`, `beneficiary`. Probability of zero matches: very high — SAM.gov text never contains conversational phrasing. The retrieval block becomes `"No specific programs found."`.
- GPT-4o is asked to help with no retrieved programs and no barrier framing. Most likely output: "I'm sorry to hear that. You can call 211 for local food assistance, or visit your nearest food bank…" — the canonical training-data response. **High failure probability.**

**Path B: user goes through `/app` intake, checks `phone` barrier, picks `benefits` goal + `today` urgency.**
- Action Card correctly says "Visit 211.org and search by your ZIP" (the May 11 fix). Good.
- User types "I need food help" in chat. Session includes `barriers=['phone']`.
- Retrieval: substring match on "I need food help" — also likely zero matches (SAM.gov objectives don't say "food help"; they say "Supplemental Nutrition Assistance Program," "Emergency Food Assistance," etc.).
- System prompt includes "phone calls are a barrier — suggest scripts or written alternatives when possible." This is soft and conditional ("when possible"). GPT-4o may still produce "call SNAP at 1-800-..." or "call 211" because it has no other surfaced alternative and the prompt does not prohibit it.

**Path C: same as B but `goal != benefits` (e.g., `nextsteps`).**
- Action Card is **not** phone-aware (no branch for non-benefits goals). The text "Write down the one thing weighing on you most right now" is fine here, but only because none of the non-benefits defaults happened to recommend a phone action. The lack of branching is a latent bug — the next time someone edits the non-benefits text to recommend a contact action, the phone barrier won't fire.

### Where "call 211" / phone-first advice can enter

| Entry point | Mechanism | Mitigation present? |
|---|---|---|
| Azure GPT-4o training-data default | "211 is the canonical answer for food help" | Only advisory system-prompt text |
| Retrieved SAM.gov program text | objectives/eligibility may mention phone numbers | None — passed verbatim to the model |
| `templates/resources.html:182-188` | static "Call 211" card | None — but route is dormant |
| Legacy `config/resources.yaml` crisis block | `phone: "988"` etc. | None — but route is dormant |
| Hardcoded Action Card text (non-benefits goals) | "Call X" could be added by future edit | None — only `benefits` goal has the branch |
| The "Write your one phone question on paper before you call" Steps insertion | Presupposes a call will be made | None — barrier flag *triggers* phone-coping prep, not phone substitution |

### Which files / functions own the failure

- Most owned by: `src/routes_v2.py:_BARRIER_NOTES` (line 61-68) — soft guidance.
- Second-most owned by: `src/data_loader.py:get_context_for_chat` (line 148-151) — retrieval that doesn't extract intent from conversational text, so the model answers ungrounded.
- Third: `templates/navigator_v2.html` (line 355) — `/` surface doesn't send session.
- Fourth: the entire chat reply path has no validator. The reply at `src/routes_v2.py:183-184` is returned without inspection.

---

## 5. Optimization Opportunities

### Constraint extraction

The Action Card has structured extraction via the intake form. The chat has none. Two paths to improve:

1. **Pre-parse free-text barriers.** When `/` users say "phone calls are hard," extract `'phone'` and add it to a synthesized session for that turn. Cheapest: a small keyword lexicon (`phone|call|talking|talk on the phone|hearing`). Slightly fancier: an LLM-extract pass against Haiku 4.5 or `gpt-4o-mini` with a tiny schema. Either way, the session becomes barrier-aware even without intake.
2. **Echo barriers back to the user.** When `barriers∋'phone'`, prepend or annotate the reply with "Because phone calls are hard for you, I'm focusing on online and written options." This both enforces (the model is more likely to follow once committed) and visibly acknowledges the constraint — closing the gap between "acknowledged" and "honored."

### Contact-method ranking

The single biggest missing primitive is an `access_modes` field on each resource: a set drawn from `phone | online | in_person | text | email | mail | sms_chat`. The pieces to build this:

- `src/fetch_211.py:normalize_detail` already exposes `phone`, `url`, `address`, `applicationProcess`. Deriving `access_modes` from these is straightforward (phone if `phone`, online if `url` and `applicationProcess` mentions online keywords, in_person if `address`, etc.). 211 also exposes `accessibility` flags — those should be promoted alongside.
- SAM.gov rows generally have a `URL` field already populated. Phone fields are not consistently present. An additive `access_modes: ['online']` default for SAM.gov programs that have a URL is a reasonable lower bound.
- Spokane provider JSON is phone-only — currently safe to keep unwired until tagging happens.

Once `access_modes` exists, ranking under `barriers∋'phone'` becomes: stable-sort retrieved resources by whether their modes intersect the user's accessible modes. Filtering (rather than ranking) is risky — a phone-only resource may still be the only option in some region.

### Recommendation validation

The highest-impact low-risk addition: a **reply-side validator**. Pseudocode for the shape only:

```
after Azure returns `reply`:
  if 'phone' in session.barriers:
    if reply_contains_phone_first_pattern(reply):
       append a brief follow-up: "If calling isn't an option, here's a non-phone alternative: …"
       OR (more aggressive) regenerate with a stricter system message
```

Patterns to detect: `r"\bcall\s+(?:\d|211|the|your)"`, `r"\bphone\s+number"`, leading imperative `r"^Call\b"`, mention of a literal phone number. Detect-and-augment is lower risk than detect-and-rewrite; detect-and-regenerate (one extra Azure call) is highest fidelity. Done well, this enforces the constraint regardless of which retrieval source or which model generation path produced the phone-first text.

### Fallback handling when only phone resources exist

This is the case where validation alone is wrong — sometimes phone is the only option. Recommended posture:

1. Explicitly name the constraint conflict: "The only option I can find requires a phone call. If that's not workable, here are nearby alternatives that might be online: …" — give the user agency rather than hiding the option.
2. Always pair a phone-only suggestion with a script and a non-phone alternative, even if that alternative is "ask a friend or family member to make the call for you" or a `relay.gov` 711 reference for deaf/hard-of-hearing users (not just Spanish/ASL).
3. Surface the `wheelchair` / `asl` / `spanish` / `phone_only` flags from 211 NDP into the chat context block once 211 is wired.

### User-facing explanation of why a recommendation fits

Today the chat reply is monolithic prose. A simple structural change: at the end of each reply where barriers are active, append one short line per active barrier explaining the fit. E.g., `[Why this fits: online application, no phone call required.]` That requires the model (or a post-processor) to know `access_modes` on the resources it cites — circling back to the access-mode tagging change.

### Tighten the system prompt

`_BARRIER_NOTES['phone']` is one line of advisory text. Cheap escalations:

- Change "when possible" → unconditional: `"phone calls are a barrier — DO NOT lead with a phone call. Offer online, in-person, written, or text alternatives. If only phone is available, say so explicitly and provide a short script."`
- Add a base-prompt line: `"Always state which contact method (online, in-person, phone, text, mail) a recommendation requires."` This habituates the model toward structured contact-method statements, which gives the validator a regex target.

---

## 6. Google Challenge Readiness

### Track 2 (Optimize Existing Agents) fit

Strong. Navigator is an existing agent (GPT-4o on Azure), in production, with a clearly definable optimization story: **accessibility constraints enforced, not advisory.** The submission narrative writes itself: "user-reported failure case → structured barrier capture → soft prompt guidance → reply-side enforcement → measurable failure-case test pass." Concrete failure cases (phone-hard, no-transport, low-energy, online-only) are tractable evals.

What is already in place that supports the Track 2 story:
- Structured intake with six barrier types.
- Session-aware system prompt builder.
- A working deterministic fix for one branch (the May 11 benefits Action Card).
- A passing unit test that locks in the prompt builder's behavior.

What needs to be added before submission:
- Reply-side validator with at least one regex-detected pattern + augment behavior.
- A small eval suite — even five hand-written cases scored manually — showing pre/post failure rates.
- Wiring barriers through to retrieval (even just a tag/filter pass).

### Gemini Challenge Edition branch

Operational context says billing/auth is resolved on OVH via Vertex (`/home/ubuntu/.secrets/vertex-sa.json`, model `gemini-2.5-flash`, project `navigator-gemini`, region `us-central1`). The proposed `gemini_search.py` at `/home/hyperion/gemini_search.py.from_ovh_20260515:17` is hardcoded to `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent` — the AI Studio direct endpoint that is broken (429s, prepayment wallet). It needs to switch to Vertex AI:

- `google-cloud-aiplatform` or `vertexai` SDK with `vertexai.init(project=..., location=..., credentials=SA-from-vertex-sa.json)`.
- `gemini-2.5-flash` per ops note.
- The `_save_discovered`/`_load_discovered` cache pattern is fine as-is and would carry over.

Once that swap happens, two near-immediate Gemini-anchored options for the submission:

1. **Gemini as the chat layer** (replacing or sitting alongside Azure GPT-4o on a `/gemini` branch). This is the highest-visibility Google-track demo but should not replace the production path.
2. **Gemini as the retrieval-augmentation layer** — i.e., `get_context_for_chat` uses Gemini to extract intent + access-method constraints from the user's message, then queries SAM.gov / BigQuery / 211 / discovered_resources. This is more architecturally interesting and harder to ablate against, which is good for an evaluation narrative.

### Google Cloud / BigQuery usage today

`check_bq.py` proves the dataset (`spheric-duality-466022-p6.navigator_benefits.programs`) exists and is queryable, but nothing in the live route path uses it. Submission-readiness requires wiring at least one chat-affecting query through BigQuery. Lowest-effort option: replace `data_loader.search_programs` with a BigQuery-backed equivalent for a `/gemini` branch only, keeping the CSV path stable on `/app`, `/pro`, `/copilot`.

### What NOT to change yet

- The Azure GPT-4o chat path on `/`, `/app`, `/pro`, `/copilot`. Production-live, working, validated by the May 11 transcript and the `test_chat_session.py` tests. Branch a Gemini variant instead.
- The intake schema (six barriers, five goals, three urgencies, four styles). Stable, tested, and already feeds three surfaces.
- The client store contract. The `intake` JSON shape is now persisted in SQLite via `clients_db.py`. Adding new barrier fields would break PUTs.

---

## 7. Testing / Evaluation Plan

### Persisted regression tests to add

1. **`tests/test_action_card.py`** — port the ephemeral May 11 21-case node harness. Three surfaces × seven cases. Should cover: phone branch fires only for `goal=benefits + urgency=today + barriers∋'phone'`; `Other` and `Prefer not to say` don't leak into state label; default goal returns the breath-three-times text. Cited by [[followup_phone_barrier_regression]].
2. **`tests/test_chat_reply.py`** — Azure response post-processing. With Azure mocked, assert: (a) when `'phone' ∈ barriers`, replies with `r"\bcall\b"` get an augmenting follow-up; (b) replies that already offer an online alternative pass through unmodified; (c) `barriers=[]` is unaffected.
3. **`tests/test_data_loader_query_extraction.py`** — if pre-parsing is added, lock in a small set of conversational → extracted-term mappings.

### Concrete eval cases (manual scoring sufficient for first pass)

| # | Message | Session | Pass criterion |
|---|---|---|---|
| 1 | "I need food help, but phone calls are really hard." | `barriers=['phone']` | No phone-first imperative. Mentions online (SNAP online app, mybenefits, 211.org) before any phone option. |
| 2 | "How do I apply for SSDI?" | `barriers=['phone']` | Mentions SSA online application (`ssa.gov/apply`) before 1-800. |
| 3 | "I can't drive and the nearest food bank is 20 miles away." | `barriers=['transport']` (not yet a captured barrier — needs schema add) | Mentions delivery, mail-order, online ordering. |
| 4 | "I'm exhausted, I can't deal with another form." | `barriers=['focus','overwhelm']` | Replies stay short (2-3 sentences). Suggests one next step, not a list. |
| 5 | "I only have access to a library computer for one hour a week." | inferred online-only constraint | Avoids any answer that requires a sustained phone session or repeated logins; prefers single-pass online intake. |
| 6 | "I just got an eviction notice and I'm scared." | `urgency='today'`, no other barriers | Leads with crisis-appropriate text; mentions both phone (988, 211) and online (legal aid websites). |
| 7 | "I need housing help. I can't make phone calls." | `barriers=['phone']` | Lists 211.org search, online HUD search, in-person CAA visit. Does not say "call your local housing authority." |

### Test infrastructure

Browser-level testing (Playwright/Selenium) is queued per ops context. As an interim, the existing pattern in `test_chat_session.py` (importing `_build_system_prompt` directly) + a Flask test client for `/api/chat` with a mocked `urllib.request.urlopen` is sufficient to cover reply-path behavior.

---

## 8. Priority Recommendations

### Top 5 highest-impact fixes

Ranked by **expected reduction in observed failure rate × independence from model behavior**.

1. **Reply-side validator on `/api/chat`.** Detect phone-first imperatives in the reply when `'phone' ∈ session.barriers`, augment with a non-phone alternative or regenerate. *Why highest-impact: enforces the constraint regardless of which model, which retrieval result, or which prompt phrasing produced the violation. Survives Azure ↔ Vertex switches.*
2. **Replace substring retrieval with extracted-intent retrieval.** `get_context_for_chat` currently substring-matches the user's raw sentence, which returns zero results for conversational input. *Why: this is broken independent of barriers. Fixing it gives the model real grounding to answer from, which both reduces hallucinated "call 211" defaults and improves all answers.*
3. **Strengthen `_BARRIER_NOTES['phone']` from advisory to blocking** + add base-prompt line requiring contact-method statement. *Why: ~10 LOC change, applied to every chat call on three of four surfaces, immediately reduces phone-first replies. Doesn't enforce but raises the model's prior dramatically.*
4. **Wire session into `/` (navigator_v2).** Currently the public homepage has no barrier awareness at all. Either pre-parse free-text barriers from the message or route `/` through the intake flow. *Why: the public surface is the highest-traffic entry and currently the least protected.*
5. **Generalize the phone-aware Action Card branch to all goals**, and remove "a phone call" from the `paperwork` default step subtitle. *Why: the May 11 fix was scoped to `benefits` because that's where the bug was reported, but the branching pattern needs to apply to every goal that could recommend a contact action — otherwise the next copy edit will silently regress.*

### Top 5 lowest-risk quick wins

Ranked by **lines changed × independence from any wiring not yet built**.

1. **Tighten `_BARRIER_NOTES['phone']` text** (one-line edit at `src/routes_v2.py:66`).
2. **Add a base-prompt line** at `src/routes_v2.py:36-43`: `"State which contact method (online, in-person, phone, text, mail) each recommendation requires."`
3. **Land `tests/test_action_card.py`** from the May 11 21-case harness — covered by [[followup_phone_barrier_regression]]. Existing as ephemeral node script.
4. **Delete or barrier-tag the `templates/resources.html` "Call 211" card** at line 182-188. Currently dormant via dead `routes.py` blueprint, but a landmine for any revival.
5. **Remove "a phone call" from the `paperwork` step subtitle** at `templates/navigator_web.html:857` (and mirrored sites in `_sw.html:929`, `_copilot.html:784`). The phrase is one example of three; replacing with "an answer" or "a form" doesn't lose meaning and removes a presumption-of-phone copy artifact.

### Risks and unknowns

- **Hardcoded data path in `data_loader.py:16`.** `data/raw/sam_assistance_listings_20260207.csv` is not in the repo. Unclear whether OVH has it. If not, retrieval silently returns nothing and the model is unanchored on all chat requests today. Worth verifying on OVH before any retrieval-layer change.
- **`run.py` is broken** (imports from empty `src/app.py`). Either it's never run in production (probably correct) or it's run and erroring silently somewhere. Worth confirming.
- **`navigator_client.html`** is 474 lines and contains an `/api/chat` fetch but no route maps to it. Either orphaned (delete) or about to be wired (clarify intent).
- **Caseworker auth is explicitly TODO** at `src/routes_v2.py:208-210`. `caseworker_id` is trusted from the client (a localStorage UUID). Pre-production this is fine; before any non-demo use it needs real auth. Out of scope for this audit but worth flagging.
- **No reply-path tests today.** The four tests in `test_chat_session.py` cover only `_build_system_prompt`. The Azure response, the retrieval block, the validator (if added), and the end-to-end behavior have zero coverage.
- **The "Write your one phone question on paper before you call" Steps insertion** at `templates/navigator_web.html:885-887` (and mirrors) is a subtle bug: it triggers when phone is a barrier, but the trigger result *assumes the call will happen*. Should either (a) only fire when the goal also implies a phone call is unavoidable, or (b) be replaced with "Look for an online or written alternative to this call." Low risk, ambiguous-impact — depends on how Robin reads "barrier-aware coping support."

### Suggested next pass

If the team decides to act on this audit, the order I'd recommend (each step gated by approval, not chained):

1. Land the May 11 Action Card regression test as a real file. Locks in the existing fix.
2. Tighten `_BARRIER_NOTES['phone']` text + add the base-prompt contact-method line. Ship with the existing test suite passing.
3. Add a single-pattern reply-side validator (regex for `^Call\b` / `\bcall (the|your|\d|211)\b`) that appends a non-phone alternative line. Cover with `tests/test_chat_reply.py`.
4. Wire `/` to either pre-parse or route through intake. Eliminates the bypass surface.
5. Verify OVH has the SAM.gov CSV at the expected path. If not, the retrieval layer needs a fix before anything else lands meaningfully.
6. Replace the substring retrieval with extracted-intent retrieval — Gemini-on-Vertex is a natural fit here and starts to build the Track 2 / Gemini Challenge Edition story in the same change.
7. Add `access_modes` tagging and reply-side filtering once at least two data sources are wired.

Each of these is independently shippable; step 1 is risk-free, step 6 is the most architecturally consequential.
