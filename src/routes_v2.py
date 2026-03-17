"""
Navigator Routes v2
===================
Mission Control style — single page, live search, Azure OpenAI (GPT-4o) chat.
"""

import os
import json
import urllib.request
import urllib.error
from flask import Blueprint, render_template, request, jsonify

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

@bp.route('/api/chat', methods=['POST'])
def api_chat():
    data       = request.get_json(force=True)
    message    = data.get('message', '').strip()
    history    = data.get('history', [])

    if not message:
        return jsonify({'error': 'No message provided'}), 400

    api_key    = os.environ.get('AZURE_OPENAI_KEY', '')
    endpoint   = os.environ.get('AZURE_OPENAI_ENDPOINT', '').rstrip('/')
    deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')

    if not api_key or not endpoint:
        return jsonify({'error': 'Chat not configured — Azure credentials missing'}), 503

    try:
        from data_loader import get_context_for_chat
        programs = get_context_for_chat(message, limit=6)

        context_lines = []
        for p in programs:
            context_lines.append(
                f"- {p['title']} ({p['agency_short']}): {p['objectives'][:200]}"
                f" | Eligibility: {p['eligibility'][:150]}"
                f" | More: {p['url']}"
            )
        context_block = "\n".join(context_lines) if context_lines else "No specific programs found."

        system_prompt = """You are Navigator, a warm and clear benefits guide built by HearthMind.
You help neurodivergent people, trauma survivors, and anyone who feels overwhelmed find federal assistance programs.

Your tone: calm, direct, never condescending. No jargon without explanation.
You say "I found some programs that might help" not "Based on your query parameters..."
Always mention the URL when referencing a specific program.
If you don't know something, say so honestly.
Keep responses concise — 2-4 short paragraphs max."""

        # Build message history for Azure OpenAI format
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history[-6:]:
            role = turn.get("role", "user")
            # Azure uses "assistant" not "model"
            if role == "model":
                role = "assistant"
            messages.append({"role": role, "content": turn.get("text", "")})

        user_text = f"""User message: {message}

Relevant federal programs from our database:
{context_block}

Please help this person based on what they've shared."""

        messages.append({"role": "user", "content": user_text})

        payload = json.dumps({
            "messages":   messages,
            "max_tokens": 600,
            "temperature": 0.7,
        }).encode()

        # Azure OpenAI Chat Completions endpoint
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

        reply = result["choices"][0]["message"]["content"]
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
    return render_template('navigator_client.html')
