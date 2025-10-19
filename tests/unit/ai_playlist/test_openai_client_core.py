"""Core tests for openai_client.py - Part 1: Initialization and Basic Methods.

Targets the OpenAIClient class initialization, prompt building, and token estimation.
"""
import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal
import uuid
from datetime import datetime, date, time

from src.ai_playlist.openai_client import OpenAIClient, DEFAULT_PER_TOOL_TIMEOUT_SECONDS, MAX_TOOL_TIMEOUT_SECONDS
from src.ai_playlist.models import (
    PlaylistSpec,
    PlaylistSpecification,
    LLMTrackSelectionRequest,
    TrackSelectionCriteria,
    BPMRange,
    GenreCriteria,
    EraCriteria
)


class TestOpenAIClientInitialization:
    """Test OpenAIClient.__init__ method."""

    def test_init_with_api_key_parameter(self):
        """Test initialization with API key provided as parameter."""
        # Act
        client = OpenAIClient(api_key="test-api-key-123")

        # Assert
        assert client.api_key == "test-api-key-123"
        assert client.model == "gpt-5"  # Default
        assert client.per_tool_timeout_seconds == DEFAULT_PER_TOOL_TIMEOUT_SECONDS
        assert client.client is not None
        assert client.encoding is not None

    def test_init_reads_from_openai_api_key_env(self):
        """Test initialization reads from OPENAI_API_KEY environment variable."""
        # Arrange
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-api-key"}):
            # Act
            client = OpenAIClient()

            # Assert
            assert client.api_key == "env-api-key"

    def test_init_reads_from_openai_key_env_as_fallback(self):
        """Test initialization reads from OPENAI_KEY as fallback."""
        # Arrange
        with patch.dict(os.environ, {"OPENAI_KEY": "fallback-key"}, clear=True):
            # Act
            client = OpenAIClient()

            # Assert
            assert client.api_key == "fallback-key"

    def test_init_raises_error_when_no_api_key(self):
        """Test initialization raises ValueError when no API key provided."""
        # Arrange - clear environment
        with patch.dict(os.environ, {}, clear=True):
            # Act & Assert
            with pytest.raises(ValueError, match="OPENAI_API_KEY or OPENAI_KEY must be provided"):
                OpenAIClient()

    def test_init_with_custom_model(self):
        """Test initialization with custom model parameter."""
        # Act
        client = OpenAIClient(api_key="test-key", model="gpt-4-turbo")

        # Assert
        assert client.model == "gpt-4-turbo"

    def test_init_reads_model_from_env(self):
        """Test initialization reads model from OPENAI_MODEL environment variable."""
        # Arrange
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "gpt-4"}):
            # Act
            client = OpenAIClient()

            # Assert
            assert client.model == "gpt-4"

    def test_init_validates_timeout_positive(self):
        """Test initialization raises error for non-positive timeout."""
        # Act & Assert
        with pytest.raises(ValueError, match="per_tool_timeout_seconds must be positive"):
            OpenAIClient(api_key="test-key", per_tool_timeout_seconds=0)

        with pytest.raises(ValueError, match="per_tool_timeout_seconds must be positive"):
            OpenAIClient(api_key="test-key", per_tool_timeout_seconds=-5)

    def test_init_validates_timeout_max(self):
        """Test initialization raises error for timeout exceeding max."""
        # Act & Assert
        with pytest.raises(ValueError, match=f"per_tool_timeout_seconds cannot exceed {MAX_TOOL_TIMEOUT_SECONDS}"):
            OpenAIClient(api_key="test-key", per_tool_timeout_seconds=MAX_TOOL_TIMEOUT_SECONDS + 1)

    def test_init_sets_cost_per_token(self):
        """Test initialization sets correct cost per token values."""
        # Act
        client = OpenAIClient(api_key="test-key")

        # Assert
        assert client.cost_per_input_token == 0.00000125
        assert client.cost_per_output_token == 0.00001000

    @patch('tiktoken.encoding_for_model')
    def test_init_handles_unknown_model_encoding(self, mock_encoding_for_model):
        """Test initialization falls back to o200k_base for unknown models."""
        # Arrange
        mock_encoding_for_model.side_effect = KeyError("Model not found")

        with patch('tiktoken.get_encoding') as mock_get_encoding:
            mock_get_encoding.return_value = Mock()

            # Act
            client = OpenAIClient(api_key="test-key", model="unknown-model")

            # Assert
            mock_get_encoding.assert_called_once_with("o200k_base")
            assert client.encoding is not None


class TestBuildSystemPrompt:
    """Test OpenAIClient._build_system_prompt method."""

    def test_build_system_prompt_includes_tool_descriptions(self):
        """Test system prompt includes all tool descriptions."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        mock_tools = Mock()
        mock_tools.get_tool_definitions.return_value = [
            {
                "function": {
                    "name": "search_tracks",
                    "description": "Search for tracks by query"
                }
            },
            {
                "function": {
                    "name": "get_genres",
                    "description": "Get available genres"
                }
            }
        ]

        # Act
        prompt = client._build_system_prompt(mock_tools)

        # Assert
        assert "search_tracks" in prompt
        assert "Search for tracks by query" in prompt
        assert "get_genres" in prompt
        assert "Get available genres" in prompt
        assert "You are an expert radio playlist curator" in prompt


class TestCreateSelectionRequest:
    """Test OpenAIClient.create_selection_request method."""

    @pytest.fixture
    def sample_spec(self):
        """Create sample PlaylistSpec."""
        bpm_range = BPMRange(
            time_start=time(6, 0),
            time_end=time(10, 0),
            bpm_min=90,
            bpm_max=130
        )

        criteria = TrackSelectionCriteria(
            bpm_ranges=[bpm_range],
            genre_mix={"Rock": GenreCriteria(target_percentage=0.5)},
            era_distribution={"Current": EraCriteria(
                era_name="Current",
                min_year=2020,
                max_year=2025,
                target_percentage=0.6
            )},
            australian_content_min=0.30,
            energy_flow_requirements=["Energetic"],
            rotation_distribution={"Power": 0.6},
            no_repeat_window_hours=24.0
        )

        spec_id = str(uuid.uuid4())
        specification = PlaylistSpecification(
            id=spec_id,
            name="Monday_MorningDrive_0600_1000",
            source_daypart_id=str(uuid.uuid4()),
            generation_date=date.today(),
            target_track_count_min=10,
            target_track_count_max=15,
            target_duration_minutes=240,
            track_selection_criteria=criteria,
            created_at=datetime.now()
        )

        return specification  # Return the PlaylistSpecification directly

    def test_create_selection_request_basic(self, sample_spec):
        """Test creating basic LLM track selection request."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Act
        request = client.create_selection_request(sample_spec)

        # Assert
        assert isinstance(request, LLMTrackSelectionRequest)
        assert request.playlist_id == sample_spec.id
        assert request.criteria == sample_spec.track_selection_criteria
        assert request.target_track_count >= 10
        assert request.target_track_count <= 15

    def test_create_selection_request_with_used_tracks(self, sample_spec):
        """Test creating request with used track IDs filter."""
        # Arrange
        client = OpenAIClient(api_key="test-key")
        used_tracks = {"track-1", "track-2", "track-3"}

        # Act
        request = client.create_selection_request(sample_spec, used_track_ids=used_tracks)

        # Assert
        assert isinstance(request, LLMTrackSelectionRequest)
        # The prompt template should reference excluded tracks
        assert request.prompt_template is not None


class TestEstimateTokens:
    """Test OpenAIClient.estimate_tokens method."""

    @pytest.fixture
    def sample_request(self):
        """Create sample LLM request."""
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=24.0
        )

        return LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=criteria,
            target_track_count=10,
            prompt_template="Test prompt template with some content",
            max_cost_usd=0.10,
            timeout_seconds=30
        )

    def test_estimate_tokens_returns_positive_integer(self, sample_request):
        """Test token estimation returns positive integer."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Act
        tokens = client.estimate_tokens(sample_request)

        # Assert
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_tokens_increases_with_prompt_length(self):
        """Test token estimate increases with longer prompts."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=24.0
        )

        short_request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=criteria,
            target_track_count=10,
            prompt_template="Short",
            max_cost_usd=0.10,
            timeout_seconds=30
        )

        long_request = LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=criteria,
            target_track_count=10,
            prompt_template="A much longer prompt template with many more words to increase the token count significantly",
            max_cost_usd=0.10,
            timeout_seconds=30
        )

        # Act
        short_tokens = client.estimate_tokens(short_request)
        long_tokens = client.estimate_tokens(long_request)

        # Assert
        assert long_tokens > short_tokens


class TestEstimateCost:
    """Test OpenAIClient.estimate_cost method."""

    @pytest.fixture
    def sample_request(self):
        """Create sample LLM request."""
        criteria = TrackSelectionCriteria(
            bpm_ranges=[],
            genre_mix={},
            era_distribution={},
            australian_content_min=0.30,
            energy_flow_requirements=[],
            rotation_distribution={},
            no_repeat_window_hours=24.0
        )

        return LLMTrackSelectionRequest(
            playlist_id=str(uuid.uuid4()),
            criteria=criteria,
            target_track_count=10,
            prompt_template="Test prompt",
            max_cost_usd=0.10,
            timeout_seconds=30
        )

    def test_estimate_cost_returns_positive_float(self, sample_request):
        """Test cost estimation returns positive float."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Act
        cost = client.estimate_cost(sample_request)

        # Assert
        assert isinstance(cost, float)
        assert cost > 0.0

    def test_estimate_cost_uses_input_token_pricing(self, sample_request):
        """Test cost estimation uses proper token pricing for input and output."""
        # Arrange
        client = OpenAIClient(api_key="test-key")

        # Act
        cost = client.estimate_cost(sample_request)

        # estimate_cost internally calculates:
        # input_tokens = len(encode(prompt))
        # output_tokens = target_track_count * 200
        # cost = (input_tokens * input_price) + (output_tokens * output_price)

        # We can verify by encoding the prompt directly
        input_tokens = len(client.encoding.encode(sample_request.prompt_template))
        estimated_output_tokens = sample_request.target_track_count * 200

        # Calculate expected cost
        expected_cost = (input_tokens * client.cost_per_input_token +
                        estimated_output_tokens * client.cost_per_output_token)

        # Assert - should match exactly (within floating point precision)
        assert abs(cost - expected_cost) < 0.000001
