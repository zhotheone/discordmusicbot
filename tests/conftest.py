"""Pytest configuration and shared fixtures for Discord Music Bot tests."""

import pytest
import os
import json
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any

# Import services for testing
from services.music_service import MusicService, SongInfo, RepeatMode, PlaybackState
from services.filter_service import FilterService, FilterToggleResult
from services.playback_service import PlaybackService
from utils.config_manager import ConfigManager
from utils.advanced_filters import AdvancedFilterManager


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary directory for config files during tests."""
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    return str(config_dir)


@pytest.fixture
def mock_config_manager(temp_config_dir):
    """Create a mock ConfigManager that uses temporary directory."""
    config_manager = ConfigManager()
    config_manager.config_dir = temp_config_dir
    return config_manager


@pytest.fixture
def mock_shared_managers(mock_config_manager):
    """Create a mock SharedManagers instance for testing."""
    shared_managers = Mock()
    shared_managers.config_manager = mock_config_manager
    shared_managers.guild_filter_managers = {}
    
    # Mock get_filter_manager method
    def mock_get_filter_manager(guild_id):
        if guild_id not in shared_managers.guild_filter_managers:
            shared_managers.guild_filter_managers[guild_id] = AdvancedFilterManager()
        return shared_managers.guild_filter_managers[guild_id]
    
    shared_managers.get_filter_manager = mock_get_filter_manager
    shared_managers.save_filter_state = Mock()
    
    return shared_managers


@pytest.fixture
def music_service(mock_shared_managers):
    """Create a MusicService instance for testing."""
    return MusicService(mock_shared_managers)


@pytest.fixture
def filter_service(mock_shared_managers):
    """Create a FilterService instance for testing."""
    return FilterService(mock_shared_managers)


@pytest.fixture
def playback_service(mock_shared_managers):
    """Create a PlaybackService instance for testing."""
    service = PlaybackService(mock_shared_managers)
    
    # Mock the service getter methods to avoid circular references
    service._get_music_service = Mock(return_value=MusicService(mock_shared_managers))
    service._get_filter_service = Mock(return_value=FilterService(mock_shared_managers))
    
    return service


@pytest.fixture
def sample_song_info():
    """Create sample SongInfo for testing."""
    return SongInfo(
        title="Test Song",
        url="https://example.com/test.mp3",
        duration=180,
        thumbnail="https://example.com/thumb.jpg",
        uploader="Test Artist",
        webpage_url="https://example.com/video"
    )


@pytest.fixture
def sample_playlist_songs():
    """Create multiple sample songs for playlist testing."""
    return [
        SongInfo(title="Song 1", url="https://example.com/song1.mp3", duration=120),
        SongInfo(title="Song 2", url="https://example.com/song2.mp3", duration=150),
        SongInfo(title="Song 3", url="https://example.com/song3.mp3", duration=200),
    ]


@pytest.fixture
def guild_id():
    """Standard guild ID for testing."""
    return 12345


@pytest.fixture
def mock_yt_dlp():
    """Mock yt-dlp for testing music searches."""
    with patch('services.music_service.yt_dlp.YoutubeDL') as mock_ytdl:
        mock_instance = MagicMock()
        mock_ytdl.return_value.__enter__.return_value = mock_instance
        
        # Default successful response
        mock_instance.extract_info.return_value = {
            'title': 'Test Song',
            'url': 'https://example.com/test.mp3',
            'duration': 180,
            'thumbnail': 'https://example.com/thumb.jpg',
            'uploader': 'Test Artist',
            'webpage_url': 'https://example.com/video'
        }
        
        yield mock_instance


@pytest.fixture
def mock_discord_voice_client():
    """Mock Discord VoiceClient for testing playback."""
    voice_client = Mock()
    voice_client.is_connected.return_value = True
    voice_client.is_playing.return_value = False
    voice_client.is_paused.return_value = False
    voice_client.play = Mock()
    voice_client.stop = Mock()
    voice_client.pause = Mock()
    voice_client.resume = Mock()
    
    return voice_client


@pytest.fixture
def mock_discord_audio_source():
    """Mock Discord audio source for testing."""
    with patch('services.playback_service.discord.FFmpegPCMAudio') as mock_audio:
        with patch('services.playback_service.discord.PCMVolumeTransformer') as mock_transformer:
            mock_source = Mock()
            mock_transformer.return_value = mock_source
            yield mock_source


@pytest.fixture(autouse=True)
def suppress_yt_dlp_warnings():
    """Suppress yt-dlp bug report messages during testing."""
    with patch('yt_dlp.utils.bug_reports_message'):
        yield


class TestConfig:
    """Helper class for test configuration data."""
    
    @staticmethod
    def default_config() -> Dict[str, Any]:
        """Return default configuration for testing."""
        return {
            "volume": 75,
            "active_filter": "none",
            "queue": [],
            "repeat_mode": "off",
            "advanced_filters": {}
        }
    
    @staticmethod
    def config_with_queue(songs: list) -> Dict[str, Any]:
        """Return configuration with a queue of songs."""
        config = TestConfig.default_config()
        config["queue"] = [
            {
                "title": song.title,
                "url": song.url,
                "duration": song.duration,
                "thumbnail": song.thumbnail,
                "uploader": song.uploader,
                "webpage_url": song.webpage_url
            }
            for song in songs
        ]
        return config 