"""Vertex AI Gemini web search for discovered Navigator resources."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.constraints import ResourceResult


DISCOVERED_PATH = Path(__file__).parent.parent / "data" / "discovered_resources.json"
PROJECT_ID = "navigator-gemini"
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.5-flash"

logger = logging.getLogger(__name__)


def _load_discovered() -> list[dict[str, Any]]:
    if DISCOVERED_PATH.exists():
        with DISCOVERED_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_discovered(resources: list[dict[str, Any]]) -> None:
    DISCOVERED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DISCOVERED_PATH.open("w", encoding="utf-8") as f:
        json.dump(resources, f, indent=2)


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def _already_known(url: str, existing: list[dict[str, Any]]) -> bool:
    normalized = _normalize_url(url)
    return any(
        _normalize_url(item.get("source_url") or item.get("url", "")) == normalized
        for item in existing
    )


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def ingest_discovered(
    resource: ResourceResult,
    query: str,
    need_category: str = "other",
    location_scope: str | None = None,
    barrier_compatibility: list[str] | None = None,
) -> bool:
    """Add a discovered Gemini resource to the flat review file."""
    existing = _load_discovered()
    source_url = resource.get("source_url", "")
    if source_url and _already_known(source_url, existing):
        return False

    entry = {
        "resource_id": str(uuid4()),
        "source_url": source_url,
        "source_title": resource.get("title", ""),
        "source_snippet": resource.get("snippet", ""),
        "need_category": need_category,
        "location_scope": location_scope,
        "contact_methods": list(resource.get("contact_methods", [])),
        "barriers_active": list(resource.get("barriers_active", [])),
        "barrier_compatibility": list(barrier_compatibility or []),
        "recommended_access_mode": resource.get("recommended_access_mode", ""),
        "discovered_from_query_hash": _query_hash(query),
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "verified": False,
        "verification_status": "pending",
        "review_notes": "",
        "source_agent": "gemini_search",
    }
    existing.append(entry)
    _save_discovered(existing)
    return True


def load_discovered() -> list[dict[str, Any]]:
    """Return all discovered resources from the flat review file."""
    return _load_discovered()


def search_gemini(
    query: str,
    barriers: list[str] | None = None,
    location: str | None = None,
    language: str = "en",
) -> list[ResourceResult]:
    """Search grounded Gemini results and return normalized resource records."""
    try:
        model, tool = _build_vertex_model()
        response = model.generate_content(
            _build_prompt(query, barriers, location, language),
            tools=[tool],
            generation_config={"temperature": 0.2, "max_output_tokens": 2000},
        )
        resources = _parse_response_text(_response_text(response))
    except Exception as exc:
        logger.error("Gemini search failed: %s", exc)
        return []

    for resource in resources:
        try:
            ingest_discovered(resource, query, location_scope=location)
        except Exception as exc:
            logger.error("Gemini discovered-resource ingest failed: %s", exc)
    return resources


def _build_vertex_model() -> tuple[Any, Any]:
    import vertexai
    from google.oauth2 import service_account
    from vertexai.generative_models import GenerativeModel, Tool, grounding

    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path
        )
        vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
    else:
        vertexai.init(project=PROJECT_ID, location=LOCATION)

    try:
        search_tool = Tool.from_google_search_retrieval()
    except TypeError:
        search_tool = Tool.from_google_search_retrieval(
            grounding.GoogleSearchRetrieval()
        )
    return GenerativeModel(MODEL_NAME), search_tool


def _build_prompt(
    query: str,
    barriers: list[str] | None,
    location: str | None,
    language: str,
) -> str:
    barrier_context = ", ".join(barriers or []) if barriers else "none"
    location_context = f'\nLocation context: "{location}"' if location else ""
    language_context = ""
    if language != "en":
        language_context = (
            f'\nReturn the title, snippet, contact_methods, barriers_active, and '
            f'recommended_access_mode values in language code "{language}".'
        )

    return f"""You are a benefits research assistant using grounded web search.
Search for federal, state, local, or nonprofit assistance programs related to: "{query}"
The user cannot use: {barrier_context}{location_context}
Language: {language}.{language_context}

Return ONLY a JSON array, with no markdown fences and no explanation.
Return up to 5 resources. Each item must have exactly these keys:
- title: program or resource name
- source_url: direct URL for the program or resource
- snippet: concise description of what help is offered
- contact_methods: array of available access methods, such as ["online", "in-person", "phone", "email", "mail", "chat"]
- recommended_access_mode: how should someone without phone access reach this program?
- barriers_active: array of user barriers this resource may trigger, such as ["phone"] or ["transport"]
- source: always "gemini"

Prefer resources that can be accessed without phone calls when phone is listed as a barrier.
Focus on resources not commonly found in SAM.gov: local organizations, state programs, nonprofits, and 211-style resources."""


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text

    candidates = getattr(response, "candidates", None) or []
    return candidates[0].content.parts[0].text


def _parse_response_text(text: str) -> list[ResourceResult]:
    try:
        parsed = json.loads(_strip_json_fences(text))
    except json.JSONDecodeError as exc:
        logger.error("Gemini JSON parse failed: %s", exc)
        return []

    if not isinstance(parsed, list):
        logger.error("Gemini JSON parse failed: expected list, got %s", type(parsed))
        return []

    resources: list[ResourceResult] = []
    for item in parsed:
        resource = _normalize_resource(item)
        if resource is not None:
            resources.append(resource)
    return resources


def _strip_json_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```json"):
        stripped = stripped[len("```json") :]
    elif stripped.startswith("```"):
        stripped = stripped[len("```") :]
    if stripped.endswith("```"):
        stripped = stripped[: -len("```")]
    return stripped.strip()


def _normalize_resource(item: Any) -> ResourceResult | None:
    if not isinstance(item, dict):
        return None

    title = str(item.get("title", "")).strip()
    source_url = str(item.get("source_url", "")).strip()
    if not title or not source_url:
        return None

    return {
        "title": title,
        "source_url": source_url,
        "snippet": str(item.get("snippet", "")).strip(),
        "contact_methods": _string_list(item.get("contact_methods")),
        "recommended_access_mode": str(
            item.get("recommended_access_mode", "")
        ).strip(),
        "barriers_active": _string_list(item.get("barriers_active")),
        "source": "gemini",
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
