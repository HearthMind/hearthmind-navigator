"""Regression tests for deterministic Action Card payloads.

The Action Card logic is client-side in the intake templates, not in a Python
route. This pytest harness executes the actual template JavaScript with Node so
the May 11 phone-barrier fix is covered without moving behavior server-side.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


SURFACES = {
    "app": {
        "template": ROOT / "templates" / "navigator_web.html",
        "runner": "renderActionCard",
        "copy": "user",
    },
    "copilot": {
        "template": ROOT / "templates" / "navigator_copilot.html",
        "runner": "buildActionCardData",
        "copy": "user",
    },
    "social_worker": {
        "template": ROOT / "templates" / "navigator_sw.html",
        "runner": "buildActionCardData",
        "copy": "client",
    },
}


USER_EXPECTED = {
    # May 11 incident baseline: benefits/today without the phone barrier keeps
    # the original phone CTA.
    ("benefits", ()): ("Call 211", "One call counts"),
    # May 11 incident baseline: benefits/today with phone as a barrier must
    # switch to the non-phone 211.org CTA.
    ("benefits", ("phone",)): ("Visit 211.org", "no phone call needed"),
    ("paperwork", ()): ("Open the most recent notice", "know what it says"),
    ("paperwork", ("phone",)): ("Open the most recent notice", "know what it says"),
    ("nextsteps", ()): ("Write down the one thing", "Naming it is the step"),
    ("nextsteps", ("phone",)): ("Write down the one thing", "Naming it is the step"),
    ("overwhelm", ()): ("Pick one task", "organizing"),
    ("overwhelm", ("phone",)): ("Pick one task", "organizing"),
    ("exploring", ()): ("Pick one program below", "Looking is doing"),
    ("exploring", ("phone",)): ("Pick one program below", "Looking is doing"),
    ("", ()): ("Take three slow breaths", "just to start"),
    ("", ("phone",)): ("Take three slow breaths", "just to start"),
}


CLIENT_EXPECTED = {
    # May 11 incident baseline: benefits/today without the phone barrier keeps
    # the original phone CTA.
    ("benefits", ()): ("Call 211", "One call counts"),
    # May 11 incident baseline: benefits/today with phone as a barrier must
    # switch to the non-phone 211.org CTA.
    ("benefits", ("phone",)): ("Visit 211.org", "no phone call needed"),
    ("paperwork", ()): ("Open the most recent notice", "Names the ask"),
    ("paperwork", ("phone",)): ("Open the most recent notice", "Names the ask"),
    ("nextsteps", ()): ("Write down the one thing", "Naming it is the step"),
    ("nextsteps", ("phone",)): ("Write down the one thing", "Naming it is the step"),
    ("overwhelm", ()): ("Pick one task", "Organizing"),
    ("overwhelm", ("phone",)): ("Pick one task", "Organizing"),
    ("exploring", ()): ("Pick one program below", "Scouting"),
    ("exploring", ("phone",)): ("Pick one program below", "Scouting"),
    ("", ()): ("Three slow breaths", "orient"),
    ("", ("phone",)): ("Three slow breaths", "orient"),
}


def _extract_function(source, name):
    marker = f"function {name}("
    start = source.find(marker)
    assert start != -1, f"{name}() not found"

    brace_start = source.find("{", start)
    assert brace_start != -1, f"{name}() opening brace not found"

    depth = 0
    for pos in range(brace_start, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]
    raise AssertionError(f"{name}() closing brace not found")


def _run_node(script):
    if shutil.which("node") is None:
        pytest.skip("Node is required to execute client-side Action Card logic")

    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def _build_action_card(surface, goal, barriers):
    config = SURFACES[surface]
    source = config["template"].read_text(encoding="utf-8")
    intake = {
        "goal": goal,
        "barriers": list(barriers),
        "urgency": "today",
        "state": "",
    }

    if config["runner"] == "buildActionCardData":
        fn = _extract_function(source, "buildActionCardData")
        script = f"""
let intake = {json.dumps(intake)};
{fn}
console.log(JSON.stringify(buildActionCardData()));
"""
    else:
        fn = _extract_function(source, "renderActionCard")
        script = f"""
let intake = {json.dumps(intake)};
const elements = {{}};
const document = {{
  getElementById(id) {{
    if (!elements[id]) elements[id] = {{ style: {{}}, textContent: "" }};
    return elements[id];
  }}
}};
{fn}
renderActionCard();
console.log(JSON.stringify({{
  text: elements["action-text"].textContent,
  sub: elements["action-sub"].textContent,
  stop: elements["action-stop"].textContent,
  display: elements["action-card"].style.display || "block"
}}));
"""

    return _run_node(script)


@pytest.mark.parametrize("surface", sorted(SURFACES))
@pytest.mark.parametrize("goal,barriers", USER_EXPECTED)
def test_action_card_goal_and_phone_barrier_matrix(surface, goal, barriers):
    expected_by_copy = CLIENT_EXPECTED if SURFACES[surface]["copy"] == "client" else USER_EXPECTED
    expected_text, expected_sub = expected_by_copy[(goal, barriers)]

    card = _build_action_card(surface, goal, barriers)

    assert card is not None
    assert expected_text in card["text"]
    assert expected_sub in card["sub"]


@pytest.mark.parametrize("surface", sorted(SURFACES))
def test_phone_barrier_benefits_card_does_not_call_211(surface):
    card = _build_action_card(surface, "benefits", ("phone",))

    assert "Visit 211.org" in card["text"]
    assert "Call 211" not in card["text"]


@pytest.mark.parametrize("surface", sorted(SURFACES))
def test_non_today_urgency_suppresses_action_card(surface):
    config = SURFACES[surface]
    source = config["template"].read_text(encoding="utf-8")
    intake = {
        "goal": "benefits",
        "barriers": ["phone"],
        "urgency": "week",
        "state": "",
    }

    if config["runner"] == "buildActionCardData":
        fn = _extract_function(source, "buildActionCardData")
        script = f"""
let intake = {json.dumps(intake)};
{fn}
console.log(JSON.stringify(buildActionCardData()));
"""
        assert _run_node(script) is None
    else:
        fn = _extract_function(source, "renderActionCard")
        script = f"""
let intake = {json.dumps(intake)};
const elements = {{}};
const document = {{
  getElementById(id) {{
    if (!elements[id]) elements[id] = {{ style: {{}}, textContent: "" }};
    return elements[id];
  }}
}};
{fn}
renderActionCard();
console.log(JSON.stringify(elements["action-card"].style.display));
"""
        assert _run_node(script) == "none"


@pytest.mark.parametrize("surface", sorted(SURFACES))
@pytest.mark.parametrize("state", ["Other", "Prefer not to say"])
def test_action_card_state_label_does_not_leak_non_state_choices(surface, state):
    config = SURFACES[surface]
    source = config["template"].read_text(encoding="utf-8")
    intake = {
        "goal": "benefits",
        "barriers": [],
        "urgency": "today",
        "state": state,
    }

    if config["runner"] == "buildActionCardData":
        fn = _extract_function(source, "buildActionCardData")
        script = f"""
let intake = {json.dumps(intake)};
{fn}
console.log(JSON.stringify(buildActionCardData()));
"""
    else:
        fn = _extract_function(source, "renderActionCard")
        script = f"""
let intake = {json.dumps(intake)};
const elements = {{}};
const document = {{
  getElementById(id) {{
    if (!elements[id]) elements[id] = {{ style: {{}}, textContent: "" }};
    return elements[id];
  }}
}};
{fn}
renderActionCard();
console.log(JSON.stringify({{
  text: elements["action-text"].textContent,
  sub: elements["action-sub"].textContent,
  stop: elements["action-stop"].textContent
}}));
"""

    card = _run_node(script)
    assert state not in card["text"]
