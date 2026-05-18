# CC Handoff: Sunday Items — Spanish + `/` route + Phone-card generalization
**Date:** 2026-05-17
**From:** Stark
**To:** CC
**Branch:** navigator-gemini-challenge
**Prereq:** CC_HANDOFF_GEMINI_SEARCH_REWRITE_2026-05-17.md committed (Gemini wire-in pass)

---

## Context

Three Sunday items from the v2 schedule. All touch templates and routes — CC's domain.
Do not touch `src/constraints.py`, `src/gemini_search.py`, or `tests/`.

Serialized with the Gemini wire-in pass. Confirm that pass is committed before starting.

---

## Item 1: Spanish via system prompt + intake language selector

### What to do

In `src/routes_v2.py`, the system prompt builder (wherever `_BARRIER_NOTES` and goal
framing are assembled into the prompt sent to the model) — add a language instruction:

```python
if language and language != "en":
    system_parts.append(
        f"Respond entirely in {language}. All resource names, instructions, "
        f"and explanations must be in {language}."
    )
```

`language` comes from the session (already stored from intake). If not set, default "en",
no instruction added.

In the intake template(s) — add a language selector. Simple: a two-option toggle or
dropdown, English / Español. Store selection as `language` in session alongside barriers.

Which templates get the selector:
- `navigator_v2.html` (the `/` public route — if it has intake)
- The intake surface on `/copilot` if it has a language field slot

Do not add to `/pro` caseworker surface — caseworkers set language on behalf of client,
that's a separate UX decision, out of scope for Weekend 1.

### Pass criteria
- Session with `language='es'` produces Spanish response
- English sessions unaffected
- Language selector visible in intake UI on at least one surface

---

## Item 2: `/` route barrier awareness

### What to do

The `/` route (`navigator_v2.html`) currently does not send session data with chat
requests — CC audit caught this (navigator_v2.html:355, no session attached to fetch).

Fix: when the public homepage chat submits a message, include whatever barrier/language
state exists in the page (from intake if completed, or empty if not) in the request body.

This does not require a full intake flow on `/` — just don't drop the session on the floor.
If the user has gone through intake on `/`, their barriers travel with the chat request.
If they haven't, barriers = [] and language = "en" — same as current behavior, just explicit.

Check `routes_v2.py` to see how `/api/chat` receives session data and make sure the
`navigator_v2.html` fetch call sends it in the same shape.

### Pass criteria
- A user on `/` who has completed intake sees barrier-aware responses
- A user on `/` who skipped intake gets the same behavior as today (no regression)

---

## Item 3: Generalize phone-Action-Card to all goals

### What to do

The phone-as-barrier Action Card branch currently fires only on the `benefits/today` path
(from the May 11 fix). Generalize it so any goal path that produces an Action Card checks
barriers before rendering.

Specifically: wherever an Action Card is rendered in the templates, check if
`barriers` includes `'phone'` and if the Action Card's primary CTA is a phone number.
If both true — suppress the phone CTA, show the non-phone alternative branch instead.

Read `tests/test_chat_session.py` and the existing Action Card logic to understand the
current branch structure before editing. The 21-test harness from May 11 is the regression
baseline — all 21 must still pass.

### Pass criteria
- Phone barrier suppresses phone-CTA Action Cards on ALL goal paths, not just benefits/today
- All 21 existing Action Card tests pass
- No new test failures

---

## Commit shape — three commits, one per item

1. `feat(i18n): Spanish via system prompt + intake language selector`
2. `fix(routes): wire session barriers into / route chat requests`  
3. `feat(ui): generalize phone-barrier Action Card to all goal paths`

Do not push — commit locally only.

## Verification before each commit
```bash
pytest -v    # full suite passes after each commit
git diff --stat    # only expected files touched
```

