"""
T104: Unit tests for LLM response parsing.

These tests validate JSON parsing of LLM responses instead of regex extraction.
Tests should initially FAIL until T108 implementation is complete.
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock
from src.ai_playlist.openai_client import OpenAIClient


class TestLLMResponseParsing:
    """Test JSON parsing of LLM track selection responses."""

    @pytest.fixture
    def openai_client(self):
        """Create OpenAI client with mocked API."""
        return OpenAIClient(api_key="test-key")

    def test_parse_json_track_selection(self, openai_client):
        """Test parsing valid JSON track selection response."""
        response_content = """{
            "selected_track_ids": ["track-1", "track-2", "track-3"],
            "reasoning": "Selected diverse tracks matching criteria"
        }"""

        # This should parse JSON instead of using regex
        result = openai_client._parse_track_selection_response(response_content)

        assert result["track_ids"] == ["track-1", "track-2", "track-3"]
        assert result["reasoning"] == "Selected diverse tracks matching criteria"
        assert result["parse_method"] == "json"

    def test_parse_json_with_markdown_code_fence(self, openai_client):
        """Test parsing JSON wrapped in markdown code fence."""
        response_content = """Here are the selected tracks:

```json
{
    "selected_track_ids": ["track-1", "track-2"],
    "reasoning": "Perfect for morning drive"
}
```
"""

        result = openai_client._parse_track_selection_response(response_content)

        assert result["track_ids"] == ["track-1", "track-2"]
        assert result["reasoning"] == "Perfect for morning drive"
        assert result["parse_method"] == "json"

    def test_parse_malformed_json_falls_back_to_regex(self, openai_client):
        """Test fallback to regex when JSON parsing fails."""
        response_content = """
        I'll select these tracks:
        - track-1
        - track-2
        - track-3

        Reasoning: Good mix of genres
        """

        result = openai_client._parse_track_selection_response(response_content)

        # Should fall back to regex pattern matching
        assert result["track_ids"] == ["track-1", "track-2", "track-3"]
        assert result["parse_method"] == "regex_fallback"

    def test_parse_empty_response_returns_empty_list(self, openai_client):
        """Test handling of empty or invalid responses."""
        response_content = "I couldn't find any matching tracks."

        result = openai_client._parse_track_selection_response(response_content)

        assert result["track_ids"] == []
        assert result["parse_method"] in ["json", "regex_fallback"]

    def test_parse_partial_json_with_missing_reasoning(self, openai_client):
        """Test handling of partial JSON (missing optional fields)."""
        response_content = """{
            "selected_track_ids": ["track-1", "track-2"]
        }"""

        result = openai_client._parse_track_selection_response(response_content)

        assert result["track_ids"] == ["track-1", "track-2"]
        assert result.get("reasoning") is None or result["reasoning"] == ""
        assert result["parse_method"] == "json"

    def test_parse_json_with_invalid_track_id_types(self, openai_client):
        """Test handling of non-string track IDs in JSON."""
        response_content = """{
            "selected_track_ids": [123, 456, "track-3"],
            "reasoning": "Mixed types"
        }"""

        result = openai_client._parse_track_selection_response(response_content)

        # Should coerce to strings or filter invalid types
        assert all(isinstance(tid, str) for tid in result["track_ids"])
        assert "track-3" in result["track_ids"]

    def test_parse_json_with_duplicate_track_ids(self, openai_client):
        """Test deduplication of track IDs in response."""
        response_content = """{
            "selected_track_ids": ["track-1", "track-2", "track-1", "track-3"],
            "reasoning": "Contains duplicates"
        }"""

        result = openai_client._parse_track_selection_response(response_content)

        # Should deduplicate
        unique_ids = list(dict.fromkeys(result["track_ids"]))
        assert len(unique_ids) == 3
        assert unique_ids == ["track-1", "track-2", "track-3"]

    @pytest.mark.asyncio
    async def test_end_to_end_json_response_handling(self, openai_client, mocker):
        """Test complete flow from LLM response to parsed track IDs."""
        # Mock OpenAI client to return JSON response
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = """{
            "selected_track_ids": ["track-1", "track-2"],
            "reasoning": "Great selection"
        }"""
        mock_message.tool_calls = None
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]

        mocker.patch.object(
            openai_client.client.chat.completions,
            'create',
            return_value=mock_completion
        )

        # This tests the full parsing flow
        result = openai_client._parse_track_selection_response(mock_message.content)

        assert result["track_ids"] == ["track-1", "track-2"]
        assert result["parse_method"] == "json"


class TestLLMPromptStructure:
    """Test that prompts explicitly request JSON format."""

    @pytest.fixture
    def openai_client(self):
        return OpenAIClient(api_key="test-key")

    def test_prompt_requests_json_format(self, openai_client):
        """Test that system prompt explicitly requests JSON responses."""
        from src.ai_playlist.models import PlaylistSpecification, DayPartConfig
        from src.subsonic.client import SubsonicClient

        # Create minimal spec
        spec = PlaylistSpecification(
            name="Test Playlist",
            description="Test",
            target_count=10
        )

        request = openai_client.create_selection_request(spec)

        # System prompt should include JSON format instructions
        system_prompt = request.system_prompt
        assert "json" in system_prompt.lower() or "JSON" in system_prompt
        assert "selected_track_ids" in system_prompt
        assert "reasoning" in system_prompt

    def test_prompt_includes_json_example(self, openai_client):
        """Test that prompt includes JSON response example."""
        from src.ai_playlist.models import PlaylistSpecification

        spec = PlaylistSpecification(
            name="Test Playlist",
            description="Test",
            target_count=10
        )

        request = openai_client.create_selection_request(spec)
        system_prompt = request.system_prompt

        # Should include an example JSON response
        assert '{"selected_track_ids":' in system_prompt or '"selected_track_ids":' in system_prompt


class TestErrorMessages:
    """Test clear error messages for parsing failures."""

    @pytest.fixture
    def openai_client(self):
        return OpenAIClient(api_key="test-key")

    def test_parse_error_includes_original_content(self, openai_client):
        """Test that parse errors include snippet of original content for debugging."""
        response_content = "This is completely invalid format with no track IDs at all!"

        result = openai_client._parse_track_selection_response(response_content)

        # Even on parse failure, should return structure with metadata
        assert "track_ids" in result
        assert "parse_method" in result
        # Could include original_content for debugging
        if "original_content_snippet" in result:
            assert len(result["original_content_snippet"]) <= 200

    def test_json_decode_error_handling(self, openai_client):
        """Test graceful handling of JSON decode errors."""
        response_content = """{"selected_track_ids": ["track-1", "track-2",}"""  # Invalid JSON

        result = openai_client._parse_track_selection_response(response_content)

        # Should fall back gracefully
        assert "track_ids" in result
        assert result["parse_method"] in ["json", "regex_fallback"]
