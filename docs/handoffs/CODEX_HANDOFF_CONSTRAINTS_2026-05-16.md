# Codex Handoff: src/constraints.py + tests

**Date:** 2026-05-16
**Author:** Stark
**Reviewer:** Grey (diff review post-execution)
**Target branch:** `navigator-gemini-challenge` (verify with `git branch --show-current` before starting)
**Author config:** keep existing (`HearthMind` / `chemicalcoyote@hearthmind.org`)
**Estimated scope:** ~150-200 LOC including tests
**Estimated time:** 30-45 min

## Goal

Create a new constraint enforcement module at `src/constraints.py` that converts user-stated accessibility barriers from passive prompt context into enforceable system constraints. This is **the blade** of the hackathon submission per Grey's v2 schedule (`docs/grey-gemini-challenge-schedule-2026-05-15-v2.md`). Everything else is hilt.

## Why this module exists

The May 11 phone-as-barrier bug shipped a fix on one code path (`buildActionCardData()` in the benefits → today flow). The CC audit (`docs/audit/NAVIGATOR_AUDIT_CC_2026-05-15.md`) revealed there are at least four other code paths where barriers are read as advisory text but never enforced as constraints on output. A centralized constraint module is the load-bearing fix: every output path imports it, so coverage is structural rather than per-path.

## What to build

### File: `src/constraints.py`

Three public functions plus internal helpers.

#### Function 1: `normalize_barriers(barriers: Any) -> list[str]`

Takes anything an upstream caller might hand us as "barriers" and returns a canonical list of normalized barrier tokens.

**Accepts:**
- `None` -> returns `[]`
- A list of strings -> normalizes and dedupes
- A single string -> wraps in list before normalizing
- A comma-separated string (e.g. `"phone, transport"`) -> splits and normalizes
- Mixed case, whitespace, punctuation -> cleans

**Normalization rules:**
- Lowercase
- Strip leading/trailing whitespace and punctuation
- Map known synonyms to canonical tokens:
  - `"phone"`, `"calls"`, `"telephone"`, `"cant call"`, `"can't call"`, `"phone calls"` -> `"phone"`
  - `"transport"`, `"transportation"`, `"no car"`, `"no transit"`, `"can't drive"` -> `"transport"`
  - `"focus"`, `"concentration"`, `"adhd"`, `"can't focus"` -> `"focus"`
  - `"overwhelm"`, `"overwhelmed"`, `"too much"`, `"exhausted"`, `"tired"` -> `"overwhelm"`
- Drop tokens that don't map to a canonical barrier (return only valid normalized tokens)
- Deduplicate while preserving order of first occurrence

**Returns:** `list[str]` of canonical barrier tokens. Empty list if input is empty or unparseable.

**Examples:**
```
normalize_barriers(None) == []
normalize_barriers("phone") == ["phone"]
normalize_barriers(["Phone", "TRANSPORT"]) == ["phone", "transport"]
normalize_barriers("phone, calls, telephone") == ["phone"]  # dedupe
normalize_barriers("I can't make phone calls") == ["phone"]  # extracted
normalize_barriers("???") == []
```

#### Function 2: `has_barrier(barriers: Any, barrier_name: str) -> bool`

Convenience wrapper. Normalizes the input and checks whether a given canonical barrier is present.

**Implementation:** essentially `barrier_name in normalize_barriers(barriers)`.

**Why it exists as its own function:** call sites read more clearly as `if has_barrier(session.get('barriers'), 'phone'):` than as `if 'phone' in normalize_barriers(...)`. Also gives us a single place to add logging if we ever need to debug barrier detection.

#### Function 3: `validate_recommendation_text(text: str, barriers: Any) -> dict`

The reply-side validator. Takes a candidate recommendation text and active barriers, returns a structured result describing whether the text violates any barrier constraints and what should be done about it.

**Returns dict with this exact shape:**

```
{
    "valid": bool,                    # True if no violations detected
    "violations": list[dict],         # one entry per violation
    "repair_suggestion": str | None,  # if violations exist, what to do
    "barriers_checked": list[str],    # canonical barriers we evaluated against
}
```

Each entry in `violations` has this shape:

```
{
    "barrier": str,                   # which barrier was violated
    "pattern": str,                   # what we detected (description)
    "matched_text": str,              # the substring that triggered the violation
    "severity": str,                  # "blocking" or "advisory"
}
```

**Detection rules for v1 (this PR):**

| Barrier | Pattern | Detection regex/heuristic | Severity |
|---------|---------|---------------------------|----------|
| phone | "call N-N-N" or 1-800/1-888 numbers as imperative | regex match on `\bcall\s+(?:1[-.\s]?)?(?:\d{3}[-.\s]?){2}\d{4}\b` OR `\b(?:dial\|phone\|ring)\s+\d` | blocking |
| phone | "Call 211" / "Call 988" / generic "call N11" | regex `\bcall\s+\d{3}\b` | blocking |
| phone | Imperative "call ..." in first 2 sentences without alternative | rule: `^(?:[^.!?]*[.!?]){0,2}` scan for `call\s+`, no alternative in same window | blocking |
| transport | Suggests in-person appointment without remote/mail/online option | scan for `in[-\s]person\|in our office\|come in\|appointment at\|visit the office` AND no `online\|remote\|by mail\|phone\|video` in same paragraph | blocking |
| focus | Lists 3+ steps or 3+ bullet points | count `\n\s*[-*ye]\s` or `\n\s*\d+\.\s` occurrences >= 3 | advisory |
| overwhelm | Reply > 4 sentences | sentence count via simple regex on `[.!?]` followed by space/EOL | advisory |

For v1, just implement `phone` (all three patterns) and `transport`. Add stubs for `focus` and `overwhelm` that always return no violation but log "TBD". Mark with `# TODO Weekend 1 Sunday` so the next session knows where to extend.

**Repair suggestion logic for `phone` violations:**

If `phone` violations found, set `repair_suggestion` to:

> Phone is named as a barrier for this user. Rewrite to lead with online, mail, or in-person alternatives. Explicitly state the contact method (e.g. 'You can apply online at ssa.gov/apply' rather than 'Call 1-800-...'). If only a phone option exists, say so honestly and offer mitigations: advocate-assisted calling, asking someone to call on their behalf, or a phone script. Do not hallucinate a website that doesn't exist.

For `transport` violations:

> Transportation is named as a barrier. Rewrite to prefer remote, mail-based, online, or transit-accessible options. If an in-person appointment is required, name it explicitly and pair with information about transit, ride assistance, or advocate options.

If multiple barriers have violations, concatenate suggestions with `\n\n` between.

#### Module-level constant: `CANONICAL_BARRIERS`

```
CANONICAL_BARRIERS = ["phone", "transport", "focus", "overwhelm"]
```

Exported so callers can iterate, do completeness checks, etc.

#### Module docstring

Top of file. ~6 lines. Names this as the constraint enforcement module per Grey's v2 schedule, points at `docs/grey-gemini-challenge-schedule-2026-05-15-v2.md` and `docs/audit/NAVIGATOR_AUDIT_CC_2026-05-15.md` for context, notes that detection patterns will expand Weekend 1 Sunday.

### File: `tests/test_constraints.py`

pytest tests. ~80-100 LOC. Use the existing test patterns from `tests/test_chat_session.py` as style reference.

**Test groups:**

```
# Group 1: normalize_barriers
- test_normalize_none_returns_empty_list
- test_normalize_empty_string_returns_empty_list
- test_normalize_phone_canonical
- test_normalize_phone_synonyms      # "calls", "telephone", etc all -> "phone"
- test_normalize_mixed_case          # "Phone", "PHONE", "phone" all -> "phone"
- test_normalize_list_input
- test_normalize_comma_separated_string
- test_normalize_dedupe
- test_normalize_unknown_token_dropped
- test_normalize_extracted_from_sentence  # "I can't make phone calls" -> ["phone"]

# Group 2: has_barrier
- test_has_barrier_true
- test_has_barrier_false_unknown
- test_has_barrier_false_empty
- test_has_barrier_normalizes_input

# Group 3: validate_recommendation_text
- test_validate_no_barriers_always_valid
- test_validate_call_211_blocking
- test_validate_call_988_blocking
- test_validate_explicit_1800_blocking
- test_validate_dial_imperative_blocking
- test_validate_phone_violation_returns_repair_suggestion
- test_validate_no_violation_returns_empty_violations
- test_validate_transport_in_person_no_alternative_blocking
- test_validate_transport_in_person_with_online_ok
- test_validate_focus_stub_no_violation_yet  # TODO marker
- test_validate_overwhelm_stub_no_violation_yet  # TODO marker
- test_validate_multiple_barriers_concatenates_repair
```

Don't worry about exhaustive coverage of every regex variant - get the canonical positive and negative cases for each rule. Edge case sweeps come Sunday.

### Where this gets imported FROM (do not wire yet, just note for the next handoff)

Final integration will be in `src/routes_v2.py` inside `api_chat()`:

```
from src.constraints import has_barrier, validate_recommendation_text

# ... after model generates response ...
validation = validate_recommendation_text(response_text, session.get('barriers'))
if not validation['valid']:
    # Use repair_suggestion to regenerate or augment
    ...
```

**Do not write this wiring in this PR.** Just `src/constraints.py` and `tests/test_constraints.py`. Integration is a separate handoff after constraints.py is reviewed.

## Verification before commit

1. All tests pass: `pytest tests/test_constraints.py -v`
2. No new top-level imports beyond stdlib `re` and standard typing - keep this module self-contained.
3. Module can be imported cleanly: `python -c "from src.constraints import normalize_barriers, has_barrier, validate_recommendation_text, CANONICAL_BARRIERS"`

## Commit message

```
feat(constraints): add constraint enforcement module per v2 schedule

Adds src/constraints.py implementing the reliability-loop blade per
Grey's v2 schedule (docs/grey-gemini-challenge-schedule-2026-05-15-v2.md):

- normalize_barriers(): canonical barrier token extraction from
  flexible upstream inputs (None, str, list, comma-separated, mixed
  case, synonyms)
- has_barrier(): convenience predicate for call sites
- validate_recommendation_text(): reply-side validator returning
  structured violations + repair_suggestion for downstream regeneration

v1 detection rules implement phone (blocking, three patterns) and
transport (blocking, in-person-without-alternative). focus and
overwhelm stubs in place for Sunday extension.

Per CC audit, this is the highest-leverage fix: every output path
imports the same module, so coverage is structural rather than per-
path. Integration into routes_v2.py.api_chat() ships in a separate
handoff after review.

Tests: 23 cases covering all three functions across canonical positive
and negative paths.
```

## After commit

Do NOT push. Hand back to Robin/Stark for review.

---

**Authored by Stark, 2026-05-16. Reference: v2 schedule weekend 1 Saturday.**
