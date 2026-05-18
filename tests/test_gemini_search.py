import json
import os
import sys
from urllib.error import HTTPError
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.constraints import ResourceResult
from src import gemini_search


VALID_RESPONSE = json.dumps(
    [
        {
            "title": "Community Rent Help",
            "source_url": "https://example.org/rent-help",
            "snippet": "Online rental assistance intake for local residents.",
            "contact_methods": ["online", "email"],
            "recommended_access_mode": "online",
            "barriers_active": [],
            "source": "gemini",
        }
    ]
)


def _mock_vertex_response(text: str) -> tuple[Mock, Mock]:
    model = Mock()
    model.generate_content.return_value = Mock(text=text)
    tool = Mock()
    return model, tool


def test_search_gemini_happy_path_returns_resource_result_shape(tmp_path):
    model, tool = _mock_vertex_response(VALID_RESPONSE)

    with (
        patch.object(gemini_search, "DISCOVERED_PATH", tmp_path / "discovered.json"),
        patch.object(gemini_search, "_build_vertex_model", return_value=(model, tool)),
    ):
        results = gemini_search.search_gemini("rental assistance")

    assert len(results) == 1
    result: ResourceResult = results[0]
    assert result == {
        "title": "Community Rent Help",
        "source_url": "https://example.org/rent-help",
        "snippet": "Online rental assistance intake for local residents.",
        "contact_methods": ["online", "email"],
        "recommended_access_mode": "online",
        "barriers_active": [],
        "source": "gemini",
    }


def test_search_gemini_passes_barriers_through_prompt(tmp_path):
    model, tool = _mock_vertex_response(VALID_RESPONSE)

    with (
        patch.object(gemini_search, "DISCOVERED_PATH", tmp_path / "discovered.json"),
        patch.object(gemini_search, "_build_vertex_model", return_value=(model, tool)),
    ):
        gemini_search.search_gemini("food help", barriers=["phone", "transport"])

    prompt = model.generate_content.call_args.args[0]
    assert "The user cannot use: phone, transport" in prompt


def test_search_gemini_non_english_language_prompt(tmp_path):
    model, tool = _mock_vertex_response(VALID_RESPONSE)

    with (
        patch.object(gemini_search, "DISCOVERED_PATH", tmp_path / "discovered.json"),
        patch.object(gemini_search, "_build_vertex_model", return_value=(model, tool)),
    ):
        gemini_search.search_gemini("ayuda alimentaria", language="es")

    prompt = model.generate_content.call_args.args[0]
    assert 'Return the title, snippet, contact_methods, barriers_active, and recommended_access_mode values in language code "es".' in prompt


def test_search_gemini_parse_failure_returns_empty_list(tmp_path, caplog):
    model, tool = _mock_vertex_response("not json")

    with (
        patch.object(gemini_search, "DISCOVERED_PATH", tmp_path / "discovered.json"),
        patch.object(gemini_search, "_build_vertex_model", return_value=(model, tool)),
        caplog.at_level("ERROR", logger="src.gemini_search"),
    ):
        results = gemini_search.search_gemini("rental assistance")

    assert results == []
    assert "Gemini JSON parse failed" in caplog.text


def test_search_gemini_auth_failure_returns_empty_list_and_logs_error(tmp_path, caplog):
    http_error = HTTPError(
        url="https://vertex.example",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=None,
    )
    model = Mock()
    model.generate_content.side_effect = http_error
    tool = Mock()

    with (
        patch.object(gemini_search, "DISCOVERED_PATH", tmp_path / "discovered.json"),
        patch.object(gemini_search, "_build_vertex_model", return_value=(model, tool)),
        caplog.at_level("ERROR", logger="src.gemini_search"),
    ):
        results = gemini_search.search_gemini("rental assistance")

    assert results == []
    assert "Gemini search failed" in caplog.text
    assert "403" in caplog.text


def test_ingest_discovered_deduplicates_by_source_url(tmp_path):
    discovered_path = tmp_path / "discovered.json"
    resource: ResourceResult = {
        "title": "Community Rent Help",
        "source_url": "https://example.org/rent-help",
        "snippet": "Online rental assistance intake for local residents.",
        "contact_methods": ["online"],
        "recommended_access_mode": "online",
        "barriers_active": [],
        "source": "gemini",
    }

    with patch.object(gemini_search, "DISCOVERED_PATH", discovered_path):
        first_added = gemini_search.ingest_discovered(resource, "rental assistance")
        second_added = gemini_search.ingest_discovered(resource, "rental assistance")

    entries = json.loads(discovered_path.read_text(encoding="utf-8"))
    assert first_added is True
    assert second_added is False
    assert len(entries) == 1
    assert entries[0]["source_url"] == "https://example.org/rent-help"
    assert entries[0]["discovered_from_query_hash"] != "rental assistance"
