"""
Navigator Routes v2
===================
Mission Control style — single page, live search, Azure OpenAI (GPT-4o) chat.
"""

import os
import json
import urllib.request
import urllib.error
from flask import Blueprint, render_template, request, jsonify, current_app

from constraints import validate_recommendation_text

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('navigator_v2.html')

@bp.route('/api/programs')
def api_programs():
    from data_loader import search_programs
    query    = request.args.get('q', '')
    category = request.args.get('category', '')
    agency   = request.args.get('agency', '')
    limit    = int(request.args.get('limit', 50))
    offset   = int(request.args.get('offset', 0))
    result   = search_programs(query=query, category=category,
                               agency=agency, limit=limit, offset=offset)
    return jsonify(result)

@bp.route('/api/categories')
def api_categories():
    from data_loader import get_categories
    return jsonify(get_categories())

_BASE_SYSTEM_PROMPT = """You are Navigator, a warm and clear benefits guide built by HearthMind.
You help neurodivergent people, trauma survivors, and anyone who feels overwhelmed find federal assistance programs.

Your tone: calm, direct, never condescending. No jargon without explanation.
You say "I found some programs that might help" not "Based on your query parameters..."
Always mention the URL when referencing a specific program.
If you don't know something, say so honestly.
Keep responses concise — 2-4 short paragraphs max.
When you recommend any program or resource, always state HOW to contact or access it (online URL, mail-in address, walk-in location, or phone number) and prefer methods accessible to the user given their stated barriers."""


_STYLE_GUIDANCE = {
    'direct':  "The user wants direct, step-by-step guidance. Skip preamble. Number steps when possible.",
    'gentle':  "The user wants gentle, supportive language. Acknowledge effort. Avoid pressure or urgency words.",
    'fast':    "The user wants fast summaries. Lead with the answer in one sentence, then optional detail.",
    'minimal': "The user prefers minimal chat. Point them to resources rather than long explanations.",
}

_GOAL_FRAMING = {
    'benefits':  "They are trying to find benefits or assistance.",
    'paperwork': "They are dealing with a notice or paperwork and need help interpreting it.",
    'nextsteps': "They are trying to figure out what to do next and need help orienting.",
    'overwhelm': "They feel overwhelmed and need help breaking things down.",
    'exploring': "They are exploring and don't know yet what they need.",
}

_BARRIER_NOTES = {
    'focus':           "brain fog / focus is a barrier — keep responses short and concrete",
    'overwhelm':       "they feel overwhelmed — one thing at a time, no long lists",
    'losing_benefits': "they're afraid of losing existing benefits — be cautious before suggesting changes",
    'paperwork':       "paperwork is hard for them — explain forms in plain language",
    'phone':           "phone calls are not available to this user. Do NOT recommend calling a number as the primary action. Lead with online application, mail-in forms, or in-person options. If the only path is phone, name that honestly and offer a script or advocate-assisted-calling — but never present 'call N-N-N' as the first recommendation.",
    'deadlines':       "they worry about missing deadlines — surface dates and timing clearly",
}


def _build_system_prompt(session: dict) -> str:
    if not session:
        return _BASE_SYSTEM_PROMPT

    parts = [_BASE_SYSTEM_PROMPT, "", "--- Session context ---"]
    name = (session.get('name') or '').strip()
    if name:
        parts.append(f"The user goes by: {name}. Use their name occasionally, naturally — not every message.")

    goal = session.get('goal')
    if goal and goal in _GOAL_FRAMING:
        parts.append(_GOAL_FRAMING[goal])

    barriers = session.get('barriers') or []
    if isinstance(barriers, list) and barriers:
        notes = [_BARRIER_NOTES[b] for b in barriers if b in _BARRIER_NOTES]
        if notes:
            parts.append("Known barriers: " + "; ".join(notes) + ".")

    urgency = session.get('urgency')
    if urgency == 'today':
        parts.append("They need to act today. Lead with the single most useful next step.")
    elif urgency == 'week':
        parts.append("They have about a week. You can suggest a small sequence.")
    elif urgency == 'planning':
        parts.append("No hard deadline — they're planning ahead. Background and tradeoffs are welcome.")

    style = session.get('style')
    if style and style in _STYLE_GUIDANCE:
        parts.append(_STYLE_GUIDANCE[style])

    state = (session.get('state') or '').strip()
    if state and state not in ('Other', 'Prefer not to say'):
        parts.append(f"They are in {state}. Prefer state-specific resources where you know them.")

    language = (session.get('language') or '').strip()
    if language and language != 'en':
        parts.append(
            f"Respond entirely in {language}. All resource names, instructions, "
            f"and explanations must be in {language}."
        )

    return "\n".join(parts)


def _call_model_with_system_prompt(system_prompt: str, user_message: str,
                                   conversation_history: list) -> str:
    """Call Azure OpenAI with a given system prompt + user message + prior turns.

    Extracted from api_chat() so the reply-side validator can re-invoke the
    model with a repair-augmented system prompt while keeping call shape
    identical to the first pass.
    """
    api_key    = os.environ.get('AZURE_OPENAI_KEY', '')
    endpoint   = os.environ.get('AZURE_OPENAI_ENDPOINT', '').rstrip('/')
    deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')

    messages = [{"role": "system", "content": system_prompt}]
    for turn in (conversation_history or [])[-6:]:
        role = turn.get("role", "user")
        # Azure uses "assistant" not "model"
        if role == "model":
            role = "assistant"
        messages.append({"role": role, "content": turn.get("text", "")})
    messages.append({"role": "user", "content": user_message})

    payload = json.dumps({
        "messages":   messages,
        "max_tokens": 600,
        "temperature": 0.7,
    }).encode()

    url = (
        f"{endpoint}/openai/deployments/{deployment}"
        f"/chat/completions?api-version=2024-08-01-preview"
    )

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "api-key":       api_key,
        }
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    return result["choices"][0]["message"]["content"]


@bp.route('/api/chat', methods=['POST'])
def api_chat():
    data       = request.get_json(force=True)
    message    = data.get('message', '').strip()
    history    = data.get('history', [])
    session    = data.get('session') or {}

    if not message:
        return jsonify({'error': 'No message provided'}), 400

    api_key    = os.environ.get('AZURE_OPENAI_KEY', '')
    endpoint   = os.environ.get('AZURE_OPENAI_ENDPOINT', '').rstrip('/')

    if not api_key or not endpoint:
        return jsonify({'error': 'Chat not configured — Azure credentials missing'}), 503

    try:
        from data_loader import get_context_for_chat
        from gemini_search import search_gemini
        programs = get_context_for_chat(message, limit=6)

        context_lines = []
        for p in programs:
            context_lines.append(
                f"- {p['title']} ({p['agency_short']}): {p['objectives'][:200]}"
                f" | Eligibility: {p['eligibility'][:150]}"
                f" | More: {p['url']}"
            )

        gemini_barriers = session.get('barriers') if session else None
        if not isinstance(gemini_barriers, list):
            gemini_barriers = None
        gemini_location = (session.get('state') or '').strip() or None
        gemini_language = (session.get('language') or 'en').strip() or 'en'

        web_results = search_gemini(
            message,
            barriers=gemini_barriers,
            location=gemini_location,
            language=gemini_language,
        )
        for r in web_results:
            access = r.get('recommended_access_mode') or 'unspecified'
            context_lines.append(
                f"- [{r.get('source', 'gemini')}] {r['title']}: {r['snippet'][:200]}"
                f" | How to access: {access}"
                f" | More: {r['source_url']}"
            )

        context_block = "\n".join(context_lines) if context_lines else "No specific programs found."

        system_prompt = _build_system_prompt(session)

        user_text = f"""User message: {message}

Relevant federal programs from our database:
{context_block}

Please help this person based on what they've shared."""

        reply = _call_model_with_system_prompt(system_prompt, user_text, history)

        # Reply-side validator: enforce barrier constraints per
        # docs/handoffs/CODEX_HANDOFF_CONSTRAINTS_2026-05-16.md
        session_barriers = session.get('barriers') if session else None
        validation = validate_recommendation_text(reply, session_barriers)

        if not validation['valid']:
            # First-pass violation. Regenerate once with repair guidance
            # appended to the system prompt.
            repair_system_prompt = (
                system_prompt
                + "\n\n--- ENFORCEMENT NOTE ---\n"
                + validation['repair_suggestion']
                + "\n\nRewrite your previous response following this guidance. "
                  "Do not apologize or mention this note."
            )
            reply = _call_model_with_system_prompt(
                repair_system_prompt, user_text, history
            )

            # Second-pass validation. If still violating, ship the response
            # with a fallback notice rather than infinite-loop.
            second_validation = validate_recommendation_text(reply, session_barriers)
            if not second_validation['valid']:
                violated_barriers = sorted(
                    {v['barrier'] for v in second_validation['violations']}
                )
                reply = reply + (
                    "\n\n*Note: based on your stated barriers ("
                    + ", ".join(violated_barriers)
                    + "), the recommendation above may not fully match your "
                      "access needs. Reply with 'help me find another way' if "
                      "this approach won't work for you.*"
                )

        return jsonify({"reply": reply, "programs": programs[:3]})

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return jsonify({'error': f'Azure OpenAI error {e.code}', 'detail': body}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/pro')
def professional():
    return render_template('navigator_sw.html')

@bp.route('/app')
def client_app():
    return render_template('navigator_web.html')

@bp.route('/copilot')
def copilot():
    return render_template('navigator_copilot.html')


# ---------------------------------------------------------------------------
# Client store API
# TODO: real auth. caseworker_id is trusted from the client (localStorage UUID)
# this pass. Replace with an authenticated session before any non-demo use.
# ---------------------------------------------------------------------------

def _client_db_path():
    return current_app.config.get('CLIENTS_DB_PATH') if current_app else None


def _bad(msg, code=400):
    return jsonify({'error': msg}), code


def _coerce_json_field(payload, key):
    """Return (value, error). value is None if absent. Accepts dict only."""
    if key not in payload:
        return None, None
    val = payload[key]
    if val is None:
        return None, None
    if isinstance(val, dict):
        return val, None
    return None, f"'{key}' must be a JSON object"


@bp.route('/api/clients', methods=['POST'])
def api_clients_create():
    from clients_db import create_client
    data = request.get_json(silent=True) or {}
    caseworker_id = (data.get('caseworker_id') or '').strip()
    name = (data.get('name') or '').strip()
    if not caseworker_id:
        return _bad("'caseworker_id' is required")
    if not name:
        return _bad("'name' is required")
    state = data.get('state')
    if state is not None and not isinstance(state, str):
        return _bad("'state' must be a string")
    intake, err = _coerce_json_field(data, 'intake')
    if err: return _bad(err)
    plan, err = _coerce_json_field(data, 'plan')
    if err: return _bad(err)
    rec = create_client(caseworker_id, name, state=state, intake=intake, plan=plan,
                        db_path=_client_db_path())
    return jsonify(rec), 201


@bp.route('/api/clients', methods=['GET'])
def api_clients_list():
    from clients_db import list_clients
    caseworker_id = (request.args.get('caseworker_id') or '').strip()
    if not caseworker_id:
        return _bad("'caseworker_id' query param is required")
    raw = (request.args.get('include_archived') or '').lower()
    include_archived = raw in ('1', 'true', 'yes', 'on')
    clients = list_clients(caseworker_id, include_archived=include_archived,
                           db_path=_client_db_path())
    return jsonify({'clients': clients})


@bp.route('/api/clients/<client_id>', methods=['GET'])
def api_clients_get(client_id):
    from clients_db import get_client
    rec = get_client(client_id, db_path=_client_db_path())
    if not rec:
        return _bad('Client not found', 404)
    return jsonify(rec)


@bp.route('/api/clients/<client_id>', methods=['PUT'])
def api_clients_update(client_id):
    from clients_db import update_client
    data = request.get_json(silent=True) or {}
    kwargs = {}
    if 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return _bad("'name' cannot be empty")
        kwargs['name'] = name
    if 'state' in data:
        state = data.get('state')
        if state is not None and not isinstance(state, str):
            return _bad("'state' must be a string or null")
        kwargs['state'] = state
    if 'intake' in data:
        intake, err = _coerce_json_field(data, 'intake')
        if err: return _bad(err)
        kwargs['intake'] = intake
    if 'plan' in data:
        plan, err = _coerce_json_field(data, 'plan')
        if err: return _bad(err)
        kwargs['plan'] = plan
    rec = update_client(client_id, db_path=_client_db_path(), **kwargs)
    if not rec:
        return _bad('Client not found', 404)
    return jsonify(rec)


@bp.route('/api/clients/<client_id>/archive', methods=['POST'])
def api_clients_archive(client_id):
    from clients_db import archive_client
    rec = archive_client(client_id, db_path=_client_db_path())
    if not rec:
        return _bad('Client not found', 404)
    return jsonify(rec)


@bp.route('/api/clients/<client_id>/unarchive', methods=['POST'])
def api_clients_unarchive(client_id):
    from clients_db import unarchive_client
    rec = unarchive_client(client_id, db_path=_client_db_path())
    if not rec:
        return _bad('Client not found', 404)
    return jsonify(rec)
