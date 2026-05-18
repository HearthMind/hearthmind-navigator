"""Constraint enforcement for accessibility barriers.

This module turns user-stated barriers into enforceable checks per Grey's v2
schedule in docs/grey-gemini-challenge-schedule-2026-05-15-v2.md. It addresses
the structural enforcement gap described in
docs/audit/NAVIGATOR_AUDIT_CC_2026-05-15.md. Detection patterns are intentionally
small for v1 and will expand Weekend 1 Sunday.
"""

import re
from typing import Any, TypedDict


class ResourceResult(TypedDict):
    title: str
    source_url: str
    snippet: str
    contact_methods: list[str]
    recommended_access_mode: str
    barriers_active: list[str]
    source: str


CANONICAL_BARRIERS = ["phone", "transport", "focus", "overwhelm"]

_BARRIER_ALIASES = {
    "phone": [
        "phone calls",
        "can't call",
        "cant call",
        "telephone",
        "calls",
        "phone",
    ],
    "transport": [
        "transportation",
        "transport",
        "no transit",
        "can't drive",
        "cant drive",
        "no car",
    ],
    "focus": [
        "can't focus",
        "cant focus",
        "concentration",
        "focus",
        "adhd",
    ],
    "overwhelm": [
        "overwhelmed",
        "overwhelm",
        "too much",
        "exhausted",
        "tired",
    ],
}

_PHONE_REPAIR = (
    "Phone is named as a barrier for this user. Rewrite to lead with online, "
    "mail, or in-person alternatives. Explicitly state the contact method "
    "(e.g. 'You can apply online at ssa.gov/apply' rather than "
    "'Call 1-800-...'). If only a phone option exists, say so honestly and "
    "offer mitigations: advocate-assisted calling, asking someone to call on "
    "their behalf, or a phone script. Do not hallucinate a website that "
    "doesn't exist."
)

_TRANSPORT_REPAIR = (
    "Transportation is named as a barrier. Rewrite to prefer remote, "
    "mail-based, online, or transit-accessible options. If an in-person "
    "appointment is required, name it explicitly and pair with information "
    "about transit, ride assistance, or advocate options."
)


def normalize_barriers(barriers: Any) -> list[str]:
    """Return canonical barrier tokens extracted from flexible upstream input."""
    if barriers is None:
        return []

    values = barriers if isinstance(barriers, list) else [barriers]
    normalized = []

    for value in values:
        if not isinstance(value, str):
            continue
        for barrier in _extract_barriers(value):
            if barrier not in normalized:
                normalized.append(barrier)

    return normalized


def has_barrier(barriers: Any, barrier_name: str) -> bool:
    """Return whether a canonical barrier exists in the normalized input."""
    return barrier_name in normalize_barriers(barriers)


def validate_recommendation_text(text: str, barriers: Any) -> dict:
    """Validate recommendation text against active accessibility constraints."""
    barriers_checked = normalize_barriers(barriers)
    violations = []

    if "phone" in barriers_checked:
        violations.extend(_phone_violations(text))
    if "transport" in barriers_checked:
        violations.extend(_transport_violations(text))
    if "focus" in barriers_checked:
        violations.extend(_focus_violations(text))
    if "overwhelm" in barriers_checked:
        violations.extend(_overwhelm_violations(text))

    repair_suggestions = []
    violated_barriers = {violation["barrier"] for violation in violations}
    if "phone" in violated_barriers:
        repair_suggestions.append(_PHONE_REPAIR)
    if "transport" in violated_barriers:
        repair_suggestions.append(_TRANSPORT_REPAIR)

    return {
        "valid": not violations,
        "violations": violations,
        "repair_suggestion": "\n\n".join(repair_suggestions)
        if repair_suggestions
        else None,
        "barriers_checked": barriers_checked,
    }


def _extract_barriers(value: str) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []

    matches = []
    for barrier in CANONICAL_BARRIERS:
        for alias in _BARRIER_ALIASES[barrier]:
            pattern = r"\b" + re.escape(alias).replace(r"\ ", r"\s+") + r"\b"
            for match in re.finditer(pattern, text):
                matches.append((match.start(), barrier))

    matches.sort(key=lambda item: item[0])
    extracted = []
    for _, barrier in matches:
        if barrier not in extracted:
            extracted.append(barrier)
    return extracted


def _clean_text(value: str) -> str:
    text = value.lower().strip()
    text = text.replace("\u2019", "'")
    text = re.sub(r"[/_,;:]+", " ", text)
    text = re.sub(r"[^\w\s'-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n-_'")


def _phone_violations(text: str) -> list[dict]:
    violations = []

    patterns = [
        (
            re.compile(
                r"\bcall\s+(?:1[-.\s]?)?(?:\d{3}[-.\s]?){2}\d{4}\b",
                re.IGNORECASE,
            ),
            '"call N-N-N" or 1-800/1-888 numbers as imperative',
        ),
        (
            re.compile(r"\b(?:dial|phone|ring)\s+\d", re.IGNORECASE),
            '"dial", "phone", or "ring" followed by a number',
        ),
        (
            re.compile(r"\bcall\s+\d{3}\b", re.IGNORECASE),
            '"Call 211" / "Call 988" / generic "call N11"',
        ),
    ]

    spans = []
    for pattern, description in patterns:
        for match in pattern.finditer(text):
            violations.append(
                _violation("phone", description, match.group(0), "blocking")
            )
            spans.append(match.span())

    first_two_sentences = _first_sentences(text, 2)
    alternative_pattern = re.compile(
        r"\b(?:online|website|web|mail|email|in[-\s]person|office|chat|form)\b",
        re.IGNORECASE,
    )
    if not alternative_pattern.search(first_two_sentences):
        for match in re.finditer(r"\bcall\s+", first_two_sentences, re.IGNORECASE):
            if not _overlaps_existing_span(match.span(), spans):
                violations.append(
                    _violation(
                        "phone",
                        'imperative "call ..." in first 2 sentences without alternative',
                        match.group(0).strip(),
                        "blocking",
                    )
                )

    return violations


def _transport_violations(text: str) -> list[dict]:
    trigger_pattern = re.compile(
        r"\b(?:in[-\s]person|in our office|come in|appointment at|visit the office)\b",
        re.IGNORECASE,
    )
    alternative_pattern = re.compile(
        r"\b(?:online|remote|by mail|phone|video)\b",
        re.IGNORECASE,
    )
    violations = []

    for paragraph in re.split(r"\n\s*\n", text):
        if alternative_pattern.search(paragraph):
            continue
        for match in trigger_pattern.finditer(paragraph):
            violations.append(
                _violation(
                    "transport",
                    "suggests in-person appointment without remote/mail/online option",
                    match.group(0),
                    "blocking",
                )
            )

    return violations


def _focus_violations(text: str) -> list[dict]:
    # TODO Weekend 1 Sunday: implement focus burden checks.
    return []


def _overwhelm_violations(text: str) -> list[dict]:
    # TODO Weekend 1 Sunday: implement sentence-count burden checks.
    return []


def _first_sentences(text: str, count: int) -> str:
    matches = list(re.finditer(r"[.!?](?:\s|$)", text))
    if len(matches) < count:
        return text
    return text[: matches[count - 1].end()]


def _overlaps_existing_span(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(span[0] < existing[1] and existing[0] < span[1] for existing in spans)


def _violation(
    barrier: str, pattern: str, matched_text: str, severity: str
) -> dict[str, str]:
    return {
        "barrier": barrier,
        "pattern": pattern,
        "matched_text": matched_text,
        "severity": severity,
    }
