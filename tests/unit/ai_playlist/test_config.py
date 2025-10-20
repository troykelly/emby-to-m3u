"""
Comprehensive tests for config module.

Tests all configuration management including:
- AIPlaylistConfig.from_environment()
- validate_cost_config()
- to_subsonic_config()
- __repr__()
"""
import pytest
import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from src.ai_playlist.config import AIPlaylistConfig


class TestAIPlaylistConfigFromEnvironment:
    """Tests for AIPlaylistConfig.from_environment()."""

    @pytest.fixture
    def valid_env_vars(self):
        """Return dict of valid environment variables."""
        return {
            'SUBSONIC_URL': 'https://music.example.com',
            'SUBSONIC_USER': 'testuser',
            'SUBSONIC_PASSWORD': 'testpass',
            'OPENAI_KEY': 'sk-test123456',
            'AZURACAST_HOST': 'https://radio.example.com',
            'AZURACAST_API_KEY': 'azura-key-123',
            'AZURACAST_STATIONID': '1',
            'LASTFM_API_KEY': 'lastfm-key-123',
            'PLAYLIST_COST_BUDGET_MODE': 'hard',
            'PLAYLIST_COST_ALLOCATION_STRATEGY': 'equal',
            'PLAYLIST_TOTAL_COST_BUDGET': '25.00',
        }

    def test_from_environment_with_all_vars(self, valid_env_vars):
        """Test loading config with all environment variables set."""
        # Arrange & Act
        with patch.dict(os.environ, valid_env_vars, clear=True):
            config = AIPlaylistConfig.from_environment()

        # Assert
        assert config.subsonic_url == 'https://music.example.com'
        assert config.subsonic_user == 'testuser'
        assert config.subsonic_password == 'testpass'
        assert config.openai_api_key == 'sk-test123456'
        assert config.azuracast_host == 'https://radio.example.com'
        assert config.azuracast_api_key == 'azura-key-123'
        assert config.azuracast_station_id == '1'
        assert config.lastfm_api_key == 'lastfm-key-123'
        assert config.cost_budget_mode == 'hard'
        assert config.cost_allocation_strategy == 'equal'
        assert config.total_cost_budget == Decimal('25.00')

    def test_from_environment_with_defaults(self, valid_env_vars):
        """Test loading config with optional vars using defaults."""
        # Arrange - Remove optional vars
        env_vars = {k: v for k, v in valid_env_vars.items()
                    if k not in ('LASTFM_API_KEY', 'PLAYLIST_COST_BUDGET_MODE',
                                 'PLAYLIST_COST_ALLOCATION_STRATEGY', 'PLAYLIST_TOTAL_COST_BUDGET')}

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            config = AIPlaylistConfig.from_environment()

        # Assert defaults
        assert config.lastfm_api_key is None
        assert config.cost_budget_mode == 'suggested'
        assert config.cost_allocation_strategy == 'dynamic'
        assert config.total_cost_budget == Decimal('10.00')

    def test_from_environment_missing_subsonic_url(self, valid_env_vars):
        """Test that missing SUBSONIC_URL raises EnvironmentError."""
        # Arrange
        env_vars = {k: v for k, v in valid_env_vars.items() if k != 'SUBSONIC_URL'}

        # Act & Assert
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(EnvironmentError, match="SUBSONIC_URL"):
                AIPlaylistConfig.from_environment()

    def test_from_environment_missing_subsonic_user(self, valid_env_vars):
        """Test that missing SUBSONIC_USER raises EnvironmentError."""
        # Arrange
        env_vars = {k: v for k, v in valid_env_vars.items() if k != 'SUBSONIC_USER'}

        # Act & Assert
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(EnvironmentError, match="SUBSONIC_USER"):
                AIPlaylistConfig.from_environment()

    def test_from_environment_missing_openai_key(self, valid_env_vars):
        """Test that missing OPENAI_KEY raises EnvironmentError."""
        # Arrange
        env_vars = {k: v for k, v in valid_env_vars.items() if k != 'OPENAI_KEY'}

        # Act & Assert
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
                AIPlaylistConfig.from_environment()

    def test_from_environment_missing_azuracast_host(self, valid_env_vars):
        """Test that missing AZURACAST_HOST raises EnvironmentError."""
        # Arrange
        env_vars = {k: v for k, v in valid_env_vars.items() if k != 'AZURACAST_HOST'}

        # Act & Assert
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(EnvironmentError, match="AZURACAST_HOST"):
                AIPlaylistConfig.from_environment()

    def test_from_environment_missing_multiple_vars(self):
        """Test that missing multiple vars shows all in error message."""
        # Arrange - Empty environment
        # Act & Assert
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError) as exc_info:
                AIPlaylistConfig.from_environment()

            # Should mention all required vars
            assert "SUBSONIC_URL" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)
            assert "AZURACAST_HOST" in str(exc_info.value)


class TestValidateCostConfig:
    """Tests for validate_cost_config()."""

    def test_validate_cost_config_valid_hard_dynamic(self):
        """Test validation with valid 'hard' and 'dynamic' config."""
        # Arrange
        config = AIPlaylistConfig(
            subsonic_url='https://music.example.com',
            subsonic_user='user',
            subsonic_password='pass',
            openai_api_key='key',
            azuracast_host='https://radio.example.com',
            azuracast_api_key='key',
            azuracast_station_id='1',
            cost_budget_mode='hard',
            cost_allocation_strategy='dynamic',
            total_cost_budget=Decimal('10.00'),
        )

        # Act & Assert - Should not raise
        config.validate_cost_config()

    def test_validate_cost_config_valid_suggested_equal(self):
        """Test validation with valid 'suggested' and 'equal' config."""
        # Arrange
        config = AIPlaylistConfig(
            subsonic_url='https://music.example.com',
            subsonic_user='user',
            subsonic_password='pass',
            openai_api_key='key',
            azuracast_host='https://radio.example.com',
            azuracast_api_key='key',
            azuracast_station_id='1',
            cost_budget_mode='suggested',
            cost_allocation_strategy='equal',
            total_cost_budget=Decimal('5.00'),
        )

        # Act & Assert - Should not raise
        config.validate_cost_config()

    def test_validate_cost_config_invalid_budget_mode(self):
        """Test validation fails with invalid budget mode."""
        # Arrange
        config = AIPlaylistConfig(
            subsonic_url='https://music.example.com',
            subsonic_user='user',
            subsonic_password='pass',
            openai_api_key='key',
            azuracast_host='https://radio.example.com',
            azuracast_api_key='key',
            azuracast_station_id='1',
            cost_budget_mode='invalid',
            cost_allocation_strategy='dynamic',
            total_cost_budget=Decimal('10.00'),
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid cost_budget_mode"):
            config.validate_cost_config()

    def test_validate_cost_config_invalid_allocation_strategy(self):
        """Test validation fails with invalid allocation strategy."""
        # Arrange
        config = AIPlaylistConfig(
            subsonic_url='https://music.example.com',
            subsonic_user='user',
            subsonic_password='pass',
            openai_api_key='key',
            azuracast_host='https://radio.example.com',
            azuracast_api_key='key',
            azuracast_station_id='1',
            cost_budget_mode='hard',
            cost_allocation_strategy='invalid',
            total_cost_budget=Decimal('10.00'),
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid cost_allocation_strategy"):
            config.validate_cost_config()

    def test_validate_cost_config_zero_budget(self):
        """Test validation fails with zero budget."""
        # Arrange
        config = AIPlaylistConfig(
            subsonic_url='https://music.example.com',
            subsonic_user='user',
            subsonic_password='pass',
            openai_api_key='key',
            azuracast_host='https://radio.example.com',
            azuracast_api_key='key',
            azuracast_station_id='1',
            cost_budget_mode='hard',
            cost_allocation_strategy='dynamic',
            total_cost_budget=Decimal('0.00'),
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid total_cost_budget"):
            config.validate_cost_config()

    def test_validate_cost_config_negative_budget(self):
        """Test validation fails with negative budget."""
        # Arrange
        config = AIPlaylistConfig(
            subsonic_url='https://music.example.com',
            subsonic_user='user',
            subsonic_password='pass',
            openai_api_key='key',
            azuracast_host='https://radio.example.com',
            azuracast_api_key='key',
            azuracast_station_id='1',
            cost_budget_mode='hard',
            cost_allocation_strategy='dynamic',
            total_cost_budget=Decimal('-5.00'),
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid total_cost_budget"):
            config.validate_cost_config()


class TestToSubsonicConfig:
    """Tests for to_subsonic_config()."""

    def test_to_subsonic_config_conversion(self):
        """Test conversion to SubsonicConfig."""
        # Arrange
        config = AIPlaylistConfig(
            subsonic_url='https://music.example.com',
            subsonic_user='testuser',
            subsonic_password='testpass',
            openai_api_key='key',
            azuracast_host='https://radio.example.com',
            azuracast_api_key='key',
            azuracast_station_id='1',
        )

        # Act
        subsonic_config = config.to_subsonic_config()

        # Assert
        assert subsonic_config.url == 'https://music.example.com'
        assert subsonic_config.username == 'testuser'
        assert subsonic_config.password == 'testpass'


class TestRepr:
    """Tests for __repr__()."""

    def test_repr_masks_sensitive_data(self):
        """Test that __repr__ masks sensitive information."""
        # Arrange
        config = AIPlaylistConfig(
            subsonic_url='https://music.example.com',
            subsonic_user='testuser',
            subsonic_password='secretpass',
            openai_api_key='sk-secret123',
            azuracast_host='https://radio.example.com',
            azuracast_api_key='secret-key',
            azuracast_station_id='1',
            lastfm_api_key='lastfm-secret',
            cost_budget_mode='hard',
            cost_allocation_strategy='dynamic',
            total_cost_budget=Decimal('15.00'),
        )

        # Act
        repr_str = repr(config)

        # Assert - Should NOT contain sensitive data
        assert 'secretpass' not in repr_str
        assert 'sk-secret123' not in repr_str
        assert 'secret-key' not in repr_str
        assert 'lastfm-secret' not in repr_str

        # Assert - Should contain masked versions
        assert '***' in repr_str

        # Assert - Should contain non-sensitive data
        assert 'https://music.example.com' in repr_str
        assert 'testuser' in repr_str
        assert 'https://radio.example.com' in repr_str
        assert '1' in repr_str
        assert 'hard' in repr_str
        assert 'dynamic' in repr_str
        assert '15.00' in repr_str

    def test_repr_without_lastfm(self):
        """Test __repr__ when lastfm_api_key is None."""
        # Arrange
        config = AIPlaylistConfig(
            subsonic_url='https://music.example.com',
            subsonic_user='testuser',
            subsonic_password='secretpass',
            openai_api_key='sk-secret123',
            azuracast_host='https://radio.example.com',
            azuracast_api_key='secret-key',
            azuracast_station_id='1',
            lastfm_api_key=None,
        )

        # Act
        repr_str = repr(config)

        # Assert
        assert 'lastfm_api_key=None' in repr_str

class TestGetStationIdentityPath:
    """Test get_station_identity_path() precedence and defaults."""

    def test_explicit_path_takes_precedence_over_env_var(self, tmp_path, monkeypatch):
        """Explicit path parameter should override STATION_IDENTITY_PATH env var."""
        # Create two test files
        explicit_file = tmp_path / "explicit.md"
        explicit_file.write_text("explicit content")

        env_file = tmp_path / "env.md"
        env_file.write_text("env content")

        # Set env var
        monkeypatch.setenv("STATION_IDENTITY_PATH", str(env_file))

        # Explicit path should win
        from src.ai_playlist.config import get_station_identity_path
        result = get_station_identity_path(explicit_path=str(explicit_file))
        assert result == explicit_file

    def test_env_var_used_when_no_explicit_path(self, tmp_path, monkeypatch):
        """STATION_IDENTITY_PATH env var should be used when no explicit path."""
        env_file = tmp_path / "from-env.md"
        env_file.write_text("env content")

        monkeypatch.setenv("STATION_IDENTITY_PATH", str(env_file))

        from src.ai_playlist.config import get_station_identity_path
        result = get_station_identity_path()
        assert result == env_file

    def test_default_path_docker_environment(self, tmp_path, monkeypatch):
        """Should use /app/station-identity.md in Docker environment."""
        # Clear env var
        monkeypatch.delenv("STATION_IDENTITY_PATH", raising=False)

        # Mock Docker environment (check for /app directory)
        default_file = Path("/app/station-identity.md")

        # We'll mock Path.exists() for this test
        # For now, just verify the logic exists
        # Full test requires mocking filesystem
        pass  # Placeholder - will implement in refinement

    def test_default_path_local_environment(self, tmp_path, monkeypatch):
        """Should use ./station-identity.md in local environment."""
        monkeypatch.delenv("STATION_IDENTITY_PATH", raising=False)

        # Create file in current directory
        local_file = tmp_path / "station-identity.md"
        local_file.write_text("local content")

        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        from src.ai_playlist.config import get_station_identity_path
        result = get_station_identity_path()
        assert result == Path("station-identity.md").resolve()

    def test_file_not_found_raises_clear_error(self, tmp_path, monkeypatch):
        """Should raise FileNotFoundError with clear message if file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.md"

        from src.ai_playlist.config import get_station_identity_path
        with pytest.raises(FileNotFoundError) as exc_info:
            get_station_identity_path(explicit_path=str(nonexistent))

        assert "station identity" in str(exc_info.value).lower()
        assert str(nonexistent) in str(exc_info.value)

    def test_relative_path_resolved_to_absolute(self, tmp_path, monkeypatch):
        """Relative paths should be resolved to absolute paths."""
        monkeypatch.chdir(tmp_path)

        rel_file = Path("relative.md")
        (tmp_path / "relative.md").write_text("content")

        from src.ai_playlist.config import get_station_identity_path
        result = get_station_identity_path(explicit_path="relative.md")
        assert result.is_absolute()
        assert result == (tmp_path / "relative.md")
