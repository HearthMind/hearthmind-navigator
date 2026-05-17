# CC Handoff: Reply-Side Validator Wiring + Phone Barrier Tightening

**Date:** 2026-05-16
**Author:** Stark
**Reviewer:** Grey (diff review post-execution)
**Target branch:** `navigator-gemini-challenge`
**Author config:** keep existing (`HearthMind` / `chemicalcoyote@hearthmind.org`)
**Estimated scope:** ~80-120 LOC across 2 files
**Estimated time:** 30-45 min
**Depends on:** commit `218bbab` (constraints.py + tests) already shipped on this branch

## Goal

Wire the constraint enforcement module (`src/constraints.py`, just shipped by Codex) into Navigator's actual chat path so violations are *enforced*, not just *detected*. Plus tighten `_BARRIER_NOTES['phone']` from advisory language to blocking language so the LLM gets a clearer instruction at the system-prompt layer.

This is the **integration** half of the blade. Codex built the validator; this handoff makes it run in production.

## Why this module exists

Per `docs/audit/NAVIGATOR_AUDIT_CC_2026-05-15.md`, barriers in `routes_v2.py._build_system_prompt()` are read as advisory text appended to the LLM's system prompt, but never enforced post-generation. The model often produces "Call 211..." responses anyway, especially when retrieval returns thin context. The reply-side validator catches violations the model produces and triggers a regeneration with explicit repair guidance.

Per `docs/handoffs/GROUND_TRUTH_2026-05-16.md`, the current `_BARRIER_NOTES['phone']` line says *"suggest scripts or written alternatives when possible"* — the *"when possible"* makes the model treat this as soft. Tightening that to blocking language is the lower-hanging fix that should also land in this PR.

## What to build

Three concrete changes across two files.

### Change 1: `src/routes_v2.py` — tighten `_BARRIER_NOTES['phone']`

Locate the `_BARRIER_NOTES` dict (currently around line 60-67). Find the `phone` entry. Replace its current value with blocking language.

**Current:**

```python
'phone':           "phone calls are a barrier — suggest scripts or written alternatives when possible",
```

**Target:**

```python
'phone':           "phone calls are not available to this user. Do NOT recommend calling a number as the primary action. Lead with online application, mail-in forms, or in-person options. If the only path is phone, name that honestly and offer a script or advocate-assisted-calling — but never present 'call N-N-N' as the first recommendation.",
```

Leave the other five barrier entries (`focus`, `overwhelm`, `losing_benefits`, `paperwork`, `deadlines`) unchanged. This handoff is scoped to `phone` only; other barriers may need similar tightening in a future pass.

### Change 2: `src/routes_v2.py` — add contact-method line to `_BASE_SYSTEM_PROMPT`

Locate `_BASE_SYSTEM_PROMPT` (currently around line 36-43, the warm-clear-Navigator persona).

**Add this line** to the end of the existing prompt (before the closing `"""`):

```
When you recommend any program or resource, always state HOW to contact or access it (online URL, mail-in address, walk-in location, or phone number) and prefer methods accessible to the user given their stated barriers.
```

This is a *positive* instruction — "always state HOW" — that pairs with the barrier-specific *negative* instructions to give the model clear shape on both directions: what TO do, plus what NOT to do.

### Change 3: `src/routes_v2.py` — wire validator into `api_chat()`

Locate the `api_chat()` route handler. Find the point after the model generates its response, before the response is returned to the client.

**Import constraints at top of file:**

```python
from src.constraints import validate_recommendation_text
```

**After model generates `response_text`** (the assistant's reply, before it's returned to the client):

```python
# Reply-side validator: enforce barrier constraints per docs/handoffs/CODEX_HANDOFF_CONSTRAINTS_2026-05-16.md
session_barriers = session.get('barriers') if session else None
validation = validate_recommendation_text(response_text, session_barriers)

if not validation['valid']:
    # First-pass violation. Regenerate once with repair guidance appended to system prompt.
    repair_system_prompt = system_prompt + "\n\n--- ENFORCEMENT NOTE ---\n" + validation['repair_suggestion'] + "\n\nRewrite your previous response following this guidance. Do not apologize or mention this note."

    # Re-call the model with the repair-augmented system prompt.
    # Use the same model client + same user message; only the system prompt changes.
    response_text = _call_model_with_system_prompt(repair_system_prompt, user_message, conversation_history)

    # Second-pass validation. If still violating, ship the response with a fallback notice rather than infinite-loop.
    second_validation = validate_recommendation_text(response_text, session_barriers)
    if not second_validation['valid']:
        # Fallback: keep the response but append a brief disclaimer naming the constraint we couldn't fully satisfy.
        violated_barriers = sorted({v['barrier'] for v in second_validation['violations']})
        response_text = response_text + (
            "\n\n*Note: based on your stated barriers (" + ", ".join(violated_barriers) +
            "), the recommendation above may not fully match your access needs. "
            "Reply with 'help me find another way' if this approach won't work for you.*"
        )
```

**Three notes on this code:**

1. **`_call_model_with_system_prompt(...)` is a notional helper.** If `api_chat()` already has a model-call pattern (e.g. direct OpenAI/Vertex SDK call inline), extract that into a helper named `_call_model_with_system_prompt(system_prompt, user_message, conversation_history)` that returns the response text. The validator wiring should call the same helper twice — once with original system prompt, once with repair-augmented. If extracting feels invasive, inline the second call and replicate the same model-call shape.

2. **`conversation_history`** should be whatever variable currently holds the prior turns being sent to the model. Don't change history-handling shape — just pass what's already there.

3. **`session_barriers`** is the input to the validator. Use `session.get('barriers')` defensively — `session` may itself be `None` for the legacy `/` route per the CC audit. If `session is None`, pass `None` to the validator and it'll return `valid=True` with `barriers_checked=[]`, no-op.

### What NOT to do in this PR

- **Do not** touch any other route handler (`api_chat()` only).
- **Do not** alter the model call shape itself (still Azure GPT-4o on `main`; Gemini wire-in is a future handoff).
- **Do not** modify or extend `src/constraints.py` (Codex's PR is reviewed and shipped; this is integration only).
- **Do not** add `transport` to `_BARRIER_NOTES` — per ground truth, `_BARRIER_NOTES` is the tone-coloring vocabulary, `CANONICAL_BARRIERS` is the enforcement vocabulary; intentional split, don't merge them.
- **Do not** push. Commit locally; hand back for review.

## Verification before commit

1. Existing tests still pass: `pytest tests/ -v` — no regression in `test_chat_session.py` or `test_constraints.py`.
2. Add at least one new test: `tests/test_chat_session.py` (or a new `tests/test_validator_wiring.py`) covering the case where `session={'barriers': ['phone']}` and the model is mocked to return `"Call 1-800-..."`. Assert that the second call to the model receives the repair-augmented system prompt. Mock the model client to verify the call shape — don't make real API calls in tests.
3. Manual smoke test (if practical): start the Flask app, hit `/api/chat` with a session payload `{"barriers": ["phone"], "goal": "benefits"}` and message `"I need food help"`, confirm the response does not lead with a phone number.
4. Lint passes if there's a linter config; if not, eyeball check that imports are at top, no trailing whitespace, no debug prints.

## Commit message

```
feat(constraints): wire reply-side validator into api_chat + tighten phone barrier

Three changes that together turn the constraint loop from detection-
only into demonstrably enforced behavior in production:

1. routes_v2._BARRIER_NOTES['phone'] tightened from advisory
   ("when possible") to blocking ("not available, never the first
   recommendation, lead with online/mail/in-person"). Other five
   barrier entries unchanged.

2. _BASE_SYSTEM_PROMPT gains a positive instruction: always state
   HOW to contact/access any recommended program (online URL, mail
   address, walk-in location, or phone) and prefer methods accessible
   given stated barriers.

3. api_chat() wires src.constraints.validate_recommendation_text()
   after model generation. On first-pass violation, regenerates once
   with repair_suggestion appended to system prompt. On second-pass
   violation, appends a brief access-mismatch disclaimer rather than
   infinite-looping.

Pairs with constraints.py (commit 218bbab) shipped earlier today.
The advisory-via-prompt layer and the enforcement-via-validator
layer are intentionally complementary, not redundant: prompt is the
first-best-effort; validator is the safety net.

Tests: new mock-based test verifying repair_suggestion reaches the
second model call. Existing test_chat_session and test_constraints
pass unchanged.
```

## After commit

Do NOT push. Hand back to Robin/Stark for review.

---

**Authored by Stark, 2026-05-16. References:**
- v2 schedule weekend 1 Saturday: `docs/grey-gemini-challenge-schedule-2026-05-15-v2.md`
- constraints.py spec: `docs/handoffs/CODEX_HANDOFF_CONSTRAINTS_2026-05-16.md`
- Current state ground truth: `docs/handoffs/GROUND_TRUTH_2026-05-16.md`
- CC audit (originator of "reply-side validator is highest-leverage"): `docs/audit/NAVIGATOR_AUDIT_CC_2026-05-15.md`
