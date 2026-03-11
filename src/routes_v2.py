"""
Navigator Routes v2
===================
Mission Control style — single page, live search, Gemini chat.
"""

import os
import json
from flask import Blueprint, render_template, request, jsonify, current_app

bp = Blueprint('main', __name__)

# ── Pages ─────────────────────────────────────────────────────────────────────

@bp.route('/')
def index():
    return render_template('navigator_v2.html')


# ── API: Programs ──────────────────────────────────────────────────────────────

@bp.route('/api/programs')
def api_programs():
    from data_loader import search_programs, get_categories
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


# ── API: Gemini Chat ───────────────────────────────────────────────────────────

@bp.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json(force=True)
    message = data.get('message', '').strip()
    history = data.get('history', [])

    if not message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        import boto3
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

        messages = []
        for turn in history[-6:]:
            role = "user" if turn.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": turn.get("text", "")})

        user_text = f"""User message: {message}

Relevant federal programs from our database:
{context_block}

Please help this person based on what they've shared."""

        messages.append({"role": "user", "content": user_text})

        client = boto3.client('bedrock-runtime', region_name='us-east-1')
        response = client.invoke_model(
            modelId='us.anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 600,
                "system": system_prompt,
                "messages": messages,
            })
        )
        result = json.loads(response['body'].read())
        reply = result['content'][0]['text']

        return jsonify({
            "reply": reply,
            "programs": programs[:3],
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
