"""
Navigator Routes v2
===================
Mission Control style — single page, live search, Gemini chat.
"""

import os
import json
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
    data = request.get_json(force=True)
    message = data.get('message', '').strip()
    history = data.get('history', [])

    if not message:
        return jsonify({'error': 'No message provided'}), 400

    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'Chat not configured — API key missing'}), 503

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

        contents = []
        for turn in history[-6:]:
            contents.append({"role": turn["role"], "parts": [{"text": turn["text"]}]})

        user_text = f"""User message: {message}

Relevant federal programs from our database:
{context_block}

Please help this person based on what they've shared."""

        contents.append({"role": "user", "parts": [{"text": user_text}]})

        import urllib.request
        import urllib.error

        payload = json.dumps({
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 600,
            }
        }).encode()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        reply = result["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"reply": reply, "programs": programs[:3]})

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return jsonify({'error': f'Gemini error {e.code}', 'detail': body}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500
