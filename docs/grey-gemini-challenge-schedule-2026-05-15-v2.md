# Navigator — Gemini Challenge Schedule v2 (Grey-revised)

**From:** Stark
**To:** Robin, Grey (record)
**Date:** May 15, 2026
**Re:** Schedule v2 incorporating Grey's revisions
**Supersedes:** `grey-gemini-challenge-schedule-2026-05-15.md` (v1)
**Amended:** Grey reviewed v2 and approved with three modifications (see Roles + Operational Rules section below)

---

## What changed from v1

Grey's pushback landed clean. The blade is the constraint loop; everything else is scaffolding. v1 was too heavy in Weekend 3, didn't surface evaluation artifacts as deliverables, and let "use the credits" become "build everything." This version fixes those.

**Five revisions:**

1. **Weekend 3 lightened.** Cloud Run only on Saturday. Document AI demoted to Sunday-conditional. Hard gate: if Cloud Run isn't serving chat + BigQuery + Gemini by Saturday night, **do not add Document AI**.
2. **Reframed as a reliability loop, not an agent list.** *Intake → Structure → Retrieve → Validate → Repair → Summarize* is the story.
3. **`docs/evals/` added as a Weekend 1 deliverable.** Eval cases + before/after evidence. Judge-legible.
4. **Weekend 2 BigQuery retrieval phased.** Structured filters first (low risk, high signal); embeddings if needed; Vertex AI Search only if scope demands. Don't let semantic retrieval become the dragon guarding the demo.
5. **`discovered_resources` schema hardened with privacy guardrails** and explicit `recommended_access_mode` field.

---

## Roles + Operational Rules (Grey's three modifications)

### The five-role model

```
Codex      builds the precise parts
CC         weaves the multi-file behavior
Stark      integrates and keeps the board alive
Robin      holds authority and tests the human truth
Grey       reviews the seams
```

Per-weekend:

- **Integration owner:** Stark — when Codex and CC make plausible but incompatible choices, Stark picks the merge path
- **Final product owner:** Robin — authority + smoke-test + signoff
- **Reviewer:** Grey — diff review, spec review, narrative review, hard-gate sanity checks
- **Executors:** Codex (repo-shaped tight work) + CC (multi-file flow-shaped work)

### Robin does product, not diffs

Robin's job is: *does the thing work for a real user?* Not: *did the validator function parse the barrier correctly.* Implementation diff review goes to Grey. Robin smoke-tests behavior and gives final human-read signoff.

Saturday required list for Robin (cap at 5):
1. ADC refresh
2. IAM grant
3. SAM.gov CSV check
4. Smoke test
5. Final signoff

Saturday optional list for Robin (do not let become a shame trap):
- Partner-track list pull
- API enablement audit
- Read both audit reports
- Devpost IP terms skim

*"We are not feeding HearthMind with Robin's spinal fluid."* — Grey

### Hard rule: serialized agent passes

No second-agent pass until first diff is committed or stashed. Otherwise diffs tangle and nobody knows which agent broke what. Goblins, not fools.

```
git status
git diff
run tests
commit Codex pass OR stash it with a clear name
THEN CC starts
```

Checkpoint names for Weekend 1:
- `checkpoint: codex constraints + gemini search`
- `checkpoint: cc validator + route integration`
- `checkpoint: weekend1 smoke stable`

### Interface contract for `search_gemini()` — lock this before Codex writes it

```python
search_gemini(query, barriers=None, location=None, language="en") -> list[ResourceResult]
```

Where `ResourceResult` is the canonical resource shape used elsewhere in the app (title, source_url, snippet, contact_methods, recommended_access_mode, barriers_active). Codex spec must reference this signature; CC handoff must reference this signature. No reinventing on either side.

### Eval cases are a Weekend 1 gate (not Sunday optional polish)

Minimum eval cases — six, not five (Grey added #6 to prevent lying):

1. Phone barrier + food help
2. Phone barrier + benefits help
3. No transportation + appointment-based resource
4. Low energy + paperwork-heavy task
5. Spanish + phone barrier
6. **Only phone option available** — Navigator says so cleanly and offers mitigations, does not hallucinate a website

Files in `docs/evals/`:
- `eval_cases.md` — the six cases with inputs, sessions, expected behaviors, pass criteria
- `before_after_phone_barrier.md` — transcript evidence
- `constraint_matrix.md` — which barriers gate which output behaviors
- `demo_transcript.md` — the 90-second video script's underlying chat content

### What goes to whom (calibrated)

| Workstream | Codex | CC | Stark | Grey | Robin |
|---|---|---|---|---|---|
| Spec writing | — | — | **draft** | **review** | sign-off |
| Tight modules + tests (constraints.py, gemini_search.py rewrite) | **execute** | — | spec | mechanical review | spot-check |
| Multi-file refactors (validator + Gemini wire-in + `/` route + Spanish + phone-card) | — | **execute** | spec | **diff review** | spot-check |
| Eval case content | — | — | **draft** | **review framing** | final voice |
| Cloud Run + Document AI strategic decisions | — | — | analyze | **cross-arch sanity check** | **call** |
| Weekend hard-gates | — | — | analyze | **third perspective** | **call** |
| Submission write-up | — | — | **draft** | **review narrative** | final voice |
| Demo video script | — | — | **draft** | **review beat structure** | record |
| Live execution + judgment in session | — | — | **here** | — | drive |
| Board / journal / Tower | — | — | **mine to keep** | — | — |

### Substrate note (for the record, lands in stark-anchor)

- **CC** runs on Anthropic Opus 4.7 (1M context, coding-agent deployment with hands)
- **Codex** runs on OpenAI GPT-5.5 (coding-agent deployment with hands)
- **Grey** runs on OpenAI GPT-5.5 Thinking (conversational deployment, no hands — review and analysis)
- **Stark (me)** runs on Anthropic Sonnet/Opus on Hyperion with HCMD hands

Hands matter for execution. Reasoning depth matters for review. Use each for what its deployment is shaped to do.

---

## Submission framing (Grey's language, kept verbatim)

> Track 2: Optimizing an existing agent team so accessibility constraints become enforceable system behavior, not just sympathetic language.

> Navigator optimizes an existing social-support agent by converting user-stated barriers from passive prompt context into enforceable system constraints. The agent team uses Gemini and BigQuery to retrieve, validate, repair, and explain recommendations so users receive actions they can actually take.

**The reliability loop:**

```
Intake  →  Structure  →  Retrieve  →  Validate against barriers  →  Repair recommendation  →  Summarize
```

Six agents organized around one loop. The agent count supports the story; it isn't the story.

---

## Demo arc (90 seconds, five beats)

1. **Show the failure.** "I need food help, but phone calls are hard." Current production behavior recommends calling 211.
2. **Show the optimization.** Same input on the challenge branch.
3. **Show the agent team running the loop.** Intake identifies barrier → BigQuery retrieves resources → Constraint Agent flags phone-first mismatch → Repair Agent rewrites recommendation → Final response states contact method.
4. **Show institutional memory.** Gemini-discovered resources written to BigQuery with `verified=false`, `barriers_active`, hashed query.
5. **Show the handoff.** User gets a short action plan + caseworker summary.

This is what the video has to communicate. Everything else is supporting evidence.

---

## Priority order (Grey's, kept)

**Must-have:**
1. Gemini challenge branch
2. Constraint enforcement (the loop)
3. BigQuery read/write centrality
4. Demoable failure-case fix
5. Submission URL that works

**Strong-have:**
6. Cloud Run deployment
7. Cloud Logging / dashboard screenshot

**Roadmap or demo-only:**
8. Document AI
9. TTS
10. Partner MCP (if awkward fit, roadmap it)

---

## Weekend 1 — May 17-18 — Foundation + Evals

**Pre-flight (Sat AM, ~30 min):**
- Refresh Hyperion ADC: `gcloud auth application-default login`
- Verify `programs` table healthy in `spheric-duality-466022-p6.navigator_benefits`
- Grant cross-project IAM: `vertex-sa@navigator-gemini` → BigQuery Data Editor on `spheric-duality-466022-p6.navigator_benefits`
- Verify SAM.gov CSV exists on OVH at `/home/ubuntu/hearthmind-navigator/data/raw/sam_assistance_listings_20260207.csv`

**Saturday (~5-6 hr active, 7-8 wall):**
- Branch `navigator-gemini-challenge` off origin/main
- Build `src/constraints.py` — `normalize_barriers`, `has_barrier`, `validate_recommendation_text` + unit tests
- Tighten `_BARRIER_NOTES['phone']` advisory → blocking
- Add base-prompt line requiring contact-method statement
- Reply-side validator wired into `api_chat()` — detect phone-first patterns, augment with non-phone alternative
- Rewrite `gemini_search.py` to Vertex SDK + service account auth
- Wire `search_gemini()` into `api_chat()` — merge with SAM.gov, `[web]` tag for Gemini results
- Smoke test end-to-end demo path

**Sunday (~3-4 hr):**
- `/` route gets barrier awareness (pre-parse free-text, or route through intake)
- Generalize phone-Action-Card to all goals
- Spanish via system prompt + intake language selector
- **NEW: `docs/evals/` folder created with first 5 cases:**
  - `docs/evals/eval_cases.md`
  - `docs/evals/before_after_phone_barrier.md`
  - `docs/evals/constraint_matrix.md`
  - `docs/evals/demo_transcript.md`
- End-of-session protocol

**Gates:**
- ✅ Demo path returns non-phone advice when phone is barrier
- ✅ Gemini is the chat brain on challenge branch
- ✅ Spanish toggle works end-to-end
- ✅ All four surfaces barrier-aware
- ✅ `docs/evals/` exists with 5 cases (Grey's required set below)

**Eval cases (minimum required — six, per Grey's revision):**

| Case | Input | Session | Pass criterion |
|---|---|---|---|
| 1 | "I need food help, but phone calls are hard." | `barriers=['phone']` | No phone-first imperative. Online (SNAP, 211.org) before any phone option. Contact method explicitly stated. |
| 2 | "How do I apply for SSDI?" | `barriers=['phone']` | Mentions SSA online application before any 1-800 number. Contact method stated. |
| 3 | "No transportation, need an appointment for [X]." | `barriers=['transport']` (schema add) | Prefer remote, mail, online, local delivery, transit-accessible, or advocate-assisted. |
| 4 | "I'm exhausted, can't deal with more paperwork." | `barriers=['focus','overwhelm']` | Replies 2-3 sentences. One next step, not a list. |
| 5 | "Necesito ayuda con comida, pero no puedo hacer llamadas telefónicas." | `barriers=['phone'], language='es'` | Spanish response. Non-phone-first. Contact method stated. |
| 6 | Query where only phone resource exists for [X]. | `barriers=['phone']` | Says so clearly. Does not hallucinate a website. Offers scripts, advocate-assisted calling, "ask someone to call on your behalf" option. |

---

## Mid-week 1 — May 19-22 — Optional prep

If energy: CC handoff specs for BigQuery structured retrieval + STT. If not: Weekend 2 absorbs.

---

## Weekend 2 — May 23-24 — BigQuery centrality + voice (Stark's birthday weekend)

**Retrieval improvements phased (Grey's order):**

**Phase 1 (Saturday, ~3 hr):** BigQuery structured filters
- category / benefit type
- geography
- contact method
- eligibility keywords
- barrier compatibility

**Phase 2 (Saturday afternoon if Phase 1 stable, ~2 hr):** Embeddings + BigQuery vector search
- Embed program name + description + eligibility + contact fields
- Vector search via BigQuery ML (cleaner than Vertex AI Search for ~2K rows)

**Phase 3 (skip unless time and scope demand):** Vertex AI Search
- Don't let "semantic retrieval" become the dragon guarding the demo
- Retrieval quality only needs to be "good enough to prove the constraint loop"

**Living database (Saturday, ~1.5 hr):**
- BigQuery `discovered_resources` schema (hardened with privacy):
  - `resource_id`
  - `source_url`
  - `source_title`
  - `source_snippet`
  - `need_category`
  - `location_scope`
  - `contact_methods`
  - `barriers_active`
  - `barrier_compatibility`
  - `recommended_access_mode` *(central field — what the architecture *does*)*
  - `discovered_from_query_hash` *(never raw query)*
  - `discovered_at`
  - `verified` (default false)
  - `verification_status`
  - `review_notes`
  - `source_agent`
- Write path in `gemini_search.py`

**Sunday (~4 hr):**
- Speech-to-Text input — mic button, browser audio capture, `/api/transcribe`, Cloud STT, Spanish locale
- TTS only if retrieval is stable (Grey: "voice only if retrieval is stable")
- End-of-session

**Gates:**
- ✅ Retrieval quality: "food help" returns food programs
- ✅ BigQuery is genuinely central — every chat reads, every Gemini discovery writes
- ✅ `discovered_resources` schema includes privacy guardrails
- ✅ Voice input works in English and Spanish (if not eaten by retrieval debugging)

---

## Mid-week 2 — May 26-29 — Cloud Run scouting

- Dockerfile shape for Flask + Vertex + Cloud Storage
- Cloud Run service config: env vars, secrets injection, region, scaling
- Partner-track decision (which MCP server to integrate)
- Document AI prep: read docs, pick processor (Form Parser or OCR), enable API — *but do not commit to it in submission scope yet*

---

## Weekend 3 — May 30-31 — Cloud Run (Document AI conditional)

**Saturday (~5 hr) — Cloud Run only:**
- Dockerfile build + Artifact Registry push
- Deploy to Cloud Run, region selection
- Env vars + Secret Manager (move `vertex-sa.json` from flat file → Secret Manager, wire Cloud Run to pull at runtime)
- Cloud Storage bucket creation (optional bucket prep; required only if Document AI runs Sunday)
- Cloud Logging + basic dashboard screenshot for demo video
- Smoke test on Cloud Run URL: every route, auth, Vertex calls, BigQuery reads/writes

**HARD GATE (end of Saturday):**
> If Cloud Run is not serving chat + BigQuery + Gemini by Saturday night, do not add Document AI. Document AI moves to roadmap or local-only demo.

**Sunday — TWO PATHS:**

**Path A (Cloud Run stable Saturday night):**
- Document AI integration: upload widget → Cloud Storage → trigger processor → field extraction → chat explains
- Test with Robin's actual SSI denial letter samples
- End-of-session

**Path B (Cloud Run unstable Saturday night):**
- Cloud Run debugging
- Document AI → roadmap section, not submission
- End-of-session

**Gates:**
- ✅ Submission URL is `navigator-XXX.run.app` or custom subdomain (or graceful fallback to OVH if Cloud Run fails)
- ✅ Cloud Logging dashboard exists
- ✅ Secret Manager replaces flat-file SA credentials *if and only if* Cloud Run ships

**Why Secret Manager is required if Cloud Run ships:**
Public deploy with flat-file SA credentials is bad form. Either Secret Manager goes with Cloud Run, or the demo stays private/limited.

---

## Mid-week 3 — June 2-5 — Buffer / polish

- Partner MCP integration (one partner, scope-locked; if awkward, roadmap it per Grey's "MCP if easy")
- Demo video script following the five-beat arc
- Submission write-up draft including roadmap section
- Grey reviews everything

---

## Weekend 4 — June 6-7 — Polish + submit

**Saturday (~5 hr):**
- Partner MCP integration if not done mid-week
- Demo video recording (script + retakes, target 90 seconds)
- README + project description + technical details
- **Roadmap section drafted** (Grey's reordered version below)

**Roadmap (Grey-reordered):**

*Submitted now:*
- Gemini challenge branch
- Constraint-aware recommendation repair
- BigQuery resource read/write loop
- Accessibility-tagged discovery provenance
- Bilingual English/Spanish support
- Evaluation cases showing before/after reliability

*Next sprint:*
- STT/TTS
- More languages through Translation API
- Better eval harness
- Human review queue for discovered resources

*Next quarter:*
- Document AI for denial letters
- Looker Studio for analytics/reporting
- Formal agent orchestration with ADK or Vertex AI Agent Builder

*Next half-year:*
- Marketplace/Gemini Enterprise hardening
- Pub/Sub event bus
- Larger partner MCP integrations

**Sunday (~3 hr):**
- Submit by 5 PM PT
- Full project journal entry

**Gates:**
- ✅ Submission in by Sunday June 7
- ✅ Demo video shows the five-beat arc
- ✅ Eval cases reference visible in submission

---

## Mon-Tue June 8-9 — Emergency buffer
## Wed June 11 @ 2:00 PM PT — Hard cutoff

---

## What I most needed Grey to push on (and did)

1. **Weekend 3 scope.** Was overloaded. Now Cloud Run only on Saturday, Document AI conditional. The hard gate is now actually hard.
2. **Eval cases as deliverable.** I had smoke tests; Grey added judge-legible artifacts. Bigger reframe than it sounds — turns "we fixed a bug" into "AI quality as engineering discipline."
3. **BigQuery semantic retrieval phasing.** Vertex AI Search was the dragon guarding the demo. Structured filters + embeddings hit the actual demo requirement at a fraction of the risk.
4. **Privacy guardrails on `discovered_resources`.** Should have led with this. Hashed query, never raw narrative.
5. **Demo arc.** I had pieces; didn't have sequence. Now I have both.

---

## The blade and the hilt

> Build the blade first. Then decorate the hilt. — Grey

Blade: the constraint loop, demonstrably enforced, with evidence.

Hilt: Cloud Run polish, Document AI, partner MCP, voice, dashboards.

Don't bury the blade.

---

## Grey's closer (kept verbatim)

> Codex builds the precise parts.
> CC weaves the multi-file behavior.
> Stark integrates and keeps the board alive.
> Robin holds authority and tests the human truth.
> Grey reviews the seams.
>
> That's an AI team building an AI team.
>
> Clean. Strange. Extremely us.

🖤

— Stark
