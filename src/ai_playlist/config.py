"""Configuration management for AI playlist generation.

This module handles environment variable validation and configuration loading.
All configuration is read from environment variables (NO .env files).
"""
import os
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


@dataclass
class AIPlaylistConfig:
    """Configuration for AI playlist generation (reads from environment)."""

    # Required: Subsonic/Emby
    subsonic_url: str
    subsonic_user: str
    subsonic_password: str

    # Required: OpenAI
    openai_api_key: str

    # Required: AzuraCast
    azuracast_host: str
    azuracast_api_key: str
    azuracast_station_id: str

    # Optional: Last.fm
    lastfm_api_key: Optional[str] = None

    # Optional: Cost control (FR-009, FR-030)
    cost_budget_mode: str = "suggested"  # "hard" or "suggested"
    cost_allocation_strategy: str = "dynamic"  # "dynamic" or "equal"
    total_cost_budget: Decimal = Decimal("10.00")

    @classmethod
    def from_environment(cls) -> 'AIPlaylistConfig':
        """Load configuration from environment variables (NO .env files).

        Returns:
            AIPlaylistConfig: Loaded configuration object

        Raises:
            EnvironmentError: If required environment variables are missing
        """
        missing = []

        # Required variables (using actual env var names: OPENAI_KEY, AZURACAST_STATIONID)
        required = {
            'SUBSONIC_URL': os.getenv('SUBSONIC_URL'),
            'SUBSONIC_USER': os.getenv('SUBSONIC_USER'),
            'SUBSONIC_PASSWORD': os.getenv('SUBSONIC_PASSWORD'),
            'OPENAI_API_KEY': os.getenv('OPENAI_KEY'),  # Actual var is OPENAI_KEY
            'AZURACAST_HOST': os.getenv('AZURACAST_HOST'),
            'AZURACAST_API_KEY': os.getenv('AZURACAST_API_KEY'),
            'AZURACAST_STATION_ID': os.getenv('AZURACAST_STATIONID'),  # Actual var is AZURACAST_STATIONID
        }

        for var, value in required.items():
            if not value:
                missing.append(var)

        if missing:
            raise EnvironmentError(
                f"Required environment variables missing: {', '.join(missing)}\n"
                f"These variables must be set in your shell environment (NOT in .env files).\n"
                f"Example: export SUBSONIC_URL='https://your-server.com'"
            )

        return cls(
            subsonic_url=required['SUBSONIC_URL'],
            subsonic_user=required['SUBSONIC_USER'],
            subsonic_password=required['SUBSONIC_PASSWORD'],
            openai_api_key=required['OPENAI_API_KEY'],
            azuracast_host=required['AZURACAST_HOST'],
            azuracast_api_key=required['AZURACAST_API_KEY'],
            azuracast_station_id=required['AZURACAST_STATION_ID'],
            lastfm_api_key=os.getenv('LASTFM_API_KEY'),
            cost_budget_mode=os.getenv('PLAYLIST_COST_BUDGET_MODE', 'suggested'),
            cost_allocation_strategy=os.getenv('PLAYLIST_COST_ALLOCATION_STRATEGY', 'dynamic'),
            total_cost_budget=Decimal(os.getenv('PLAYLIST_TOTAL_COST_BUDGET', '10.00')),
        )

    def validate_cost_config(self) -> None:
        """Validate cost control configuration.

        Raises:
            ValueError: If cost configuration values are invalid
        """
        if self.cost_budget_mode not in ('hard', 'suggested'):
            raise ValueError(
                f"Invalid cost_budget_mode: {self.cost_budget_mode}. "
                f"Must be 'hard' or 'suggested'"
            )
        if self.cost_allocation_strategy not in ('dynamic', 'equal'):
            raise ValueError(
                f"Invalid cost_allocation_strategy: {self.cost_allocation_strategy}. "
                f"Must be 'dynamic' or 'equal'"
            )
        if self.total_cost_budget <= 0:
            raise ValueError(
                f"Invalid total_cost_budget: {self.total_cost_budget}. "
                f"Must be > 0"
            )

    def to_subsonic_config(self):
        """Convert to SubsonicConfig for Subsonic client.

        Returns:
            SubsonicConfig: Configuration object for SubsonicClient
        """
        from src.subsonic.models import SubsonicConfig

        return SubsonicConfig(
            url=self.subsonic_url,
            username=self.subsonic_user,
            password=self.subsonic_password
        )

    def __repr__(self) -> str:
        """Return string representation with sensitive data masked."""
        return (
            f"AIPlaylistConfig("
            f"subsonic_url='{self.subsonic_url}', "
            f"subsonic_user='{self.subsonic_user}', "
            f"subsonic_password='***', "
            f"openai_api_key='***', "
            f"azuracast_host='{self.azuracast_host}', "
            f"azuracast_api_key='***', "
            f"azuracast_station_id='{self.azuracast_station_id}', "
            f"lastfm_api_key={'***' if self.lastfm_api_key else None}, "
            f"cost_budget_mode='{self.cost_budget_mode}', "
            f"cost_allocation_strategy='{self.cost_allocation_strategy}', "
            f"total_cost_budget={self.total_cost_budget}"
            f")"
        )
