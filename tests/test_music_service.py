"""Unit tests for MusicService."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from services.music_service import MusicService, SongInfo, RepeatMode, PlaybackState
from tests.conftest import TestConfig


@pytest.mark.unit
class TestMusicService:
    """Unit tests for MusicService class."""

    def test_initialization(self, music_service, mock_shared_managers):
        """Test MusicService initialization."""
        assert music_service.shared_managers == mock_shared_managers
        assert music_service.config_manager == mock_shared_managers.config_manager
        assert music_service._playback_states == {}
        assert music_service._original_queues == {}

    def test_get_playback_state_new_guild(self, music_service, guild_id):
        """Test getting playback state for a new guild."""
        # Mock config manager to return default config
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        
        state = music_service.get_playback_state(guild_id)
        
        assert isinstance(state, PlaybackState)
        assert state.queue == []
        assert state.repeat_mode == RepeatMode.OFF
        assert state.volume == 75
        assert not state.is_playing
        assert not state.is_paused

    def test_get_playback_state_existing_guild(self, music_service, guild_id, sample_playlist_songs):
        """Test getting playback state for existing guild with saved state."""
        config = TestConfig.config_with_queue(sample_playlist_songs)
        config["repeat_mode"] = "song"
        config["volume"] = 90
        
        music_service.config_manager.get_config = Mock(return_value=config)
        
        state = music_service.get_playback_state(guild_id)
        
        assert len(state.queue) == 3
        assert state.queue[0].title == "Song 1"
        assert state.repeat_mode == RepeatMode.SONG
        assert state.volume == 90

    def test_save_playback_state(self, music_service, guild_id, sample_song_info):
        """Test saving playback state to config."""
        # Setup initial state
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        music_service.config_manager.save_config = Mock()
        
        state = music_service.get_playback_state(guild_id)
        state.queue.append(sample_song_info)
        state.volume = 80
        state.repeat_mode = RepeatMode.QUEUE
        
        music_service.save_playback_state(guild_id)
        
        # Verify save_config was called
        music_service.config_manager.save_config.assert_called_once()
        call_args = music_service.config_manager.save_config.call_args
        guild_id_arg, config_arg = call_args[0]
        
        assert guild_id_arg == guild_id
        assert config_arg["volume"] == 80
        assert config_arg["repeat_mode"] == "queue"
        assert len(config_arg["queue"]) == 1
        assert config_arg["queue"][0]["title"] == "Test Song"

    @pytest.mark.asyncio
    async def test_search_music_success(self, music_service, mock_yt_dlp):
        """Test successful music search."""
        query = "test song"
        
        result = await music_service.search_music(query)
        
        assert result is not None
        assert isinstance(result, SongInfo)
        assert result.title == "Test Song"
        assert result.url == "https://example.com/test.mp3"
        assert result.duration == 180
        
        # Verify yt-dlp was called with correct query
        mock_yt_dlp.extract_info.assert_called_once_with("ytsearch:test song", download=False)

    @pytest.mark.asyncio
    async def test_search_music_with_url(self, music_service, mock_yt_dlp):
        """Test music search with direct URL."""
        url = "https://youtube.com/watch?v=test"
        
        result = await music_service.search_music(url)
        
        assert result is not None
        # Verify yt-dlp was called with direct URL (no ytsearch prefix)
        mock_yt_dlp.extract_info.assert_called_once_with(url, download=False)

    @pytest.mark.asyncio
    async def test_search_music_with_entries(self, music_service, mock_yt_dlp):
        """Test music search that returns entries list."""
        mock_yt_dlp.extract_info.return_value = {
            'entries': [{
                'title': 'Test Song from Entries',
                'url': 'https://example.com/entry.mp3',
                'duration': 200,
                'thumbnail': 'https://example.com/entry_thumb.jpg',
                'uploader': 'Entry Artist',
                'webpage_url': 'https://example.com/entry_video'
            }]
        }
        
        result = await music_service.search_music("test query")
        
        assert result is not None
        assert result.title == "Test Song from Entries"
        assert result.duration == 200

    @pytest.mark.asyncio
    async def test_search_music_failure(self, music_service, mock_yt_dlp):
        """Test music search failure."""
        mock_yt_dlp.extract_info.side_effect = Exception("Network error")
        
        result = await music_service.search_music("test query")
        
        assert result is None

    def test_add_to_queue_success(self, music_service, guild_id, sample_song_info):
        """Test successfully adding song to queue."""
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        music_service.save_playback_state = Mock()
        
        result = music_service.add_to_queue(guild_id, sample_song_info)
        
        assert result is True
        state = music_service.get_playback_state(guild_id)
        assert len(state.queue) == 1
        assert state.queue[0] == sample_song_info
        music_service.save_playback_state.assert_called_once_with(guild_id)

    def test_add_to_queue_multiple_songs(self, music_service, guild_id, sample_playlist_songs):
        """Test adding multiple songs to queue."""
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        music_service.save_playback_state = Mock()
        
        for song in sample_playlist_songs:
            result = music_service.add_to_queue(guild_id, song)
            assert result is True
        
        state = music_service.get_playback_state(guild_id)
        assert len(state.queue) == 3
        assert state.queue[0].title == "Song 1"
        assert state.queue[2].title == "Song 3"

    def test_get_next_song_normal_queue(self, music_service, guild_id, sample_playlist_songs):
        """Test getting next song from normal queue."""
        config = TestConfig.config_with_queue(sample_playlist_songs)
        music_service.config_manager.get_config = Mock(return_value=config)
        music_service.save_playback_state = Mock()
        
        # Get first song
        song = music_service.get_next_song(guild_id)
        
        assert song is not None
        assert song.title == "Song 1"
        
        # Verify queue was updated
        state = music_service.get_playback_state(guild_id)
        assert len(state.queue) == 2  # One song removed
        assert state.queue[0].title == "Song 2"

    def test_get_next_song_repeat_song(self, music_service, guild_id, sample_song_info):
        """Test getting next song with song repeat mode."""
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        
        # Set up repeat song mode
        state = music_service.get_playback_state(guild_id)
        state.repeat_mode = RepeatMode.SONG
        state.current_song = sample_song_info
        
        song = music_service.get_next_song(guild_id)
        
        assert song == sample_song_info
        # Queue should remain unchanged in song repeat mode
        assert len(state.queue) == 0

    def test_get_next_song_repeat_queue(self, music_service, guild_id, sample_playlist_songs):
        """Test getting next song with queue repeat mode."""
        config = TestConfig.config_with_queue(sample_playlist_songs)
        music_service.config_manager.get_config = Mock(return_value=config)
        music_service.save_playback_state = Mock()
        
        state = music_service.get_playback_state(guild_id)
        state.repeat_mode = RepeatMode.QUEUE
        state.current_song = sample_playlist_songs[0]  # Set current song
        
        # Initial queue should have 3 songs
        assert len(state.queue) == 3
        
        # Get first song - should store original queue
        song1 = music_service.get_next_song(guild_id)
        assert song1.title == "Song 1"
        assert guild_id in music_service._original_queues
        assert len(state.queue) == 2  # One song removed
        
        # Get second song
        song2 = music_service.get_next_song(guild_id)
        assert song2.title == "Song 2"
        assert len(state.queue) == 1  # Another song removed
        
        # Get third song - this should empty the queue and then restore it
        song3 = music_service.get_next_song(guild_id)
        assert song3.title == "Song 3"
        # After popping Song 3, queue becomes empty, then gets restored with [Song2, Song3]
        # (original queue [Song1, Song2, Song3] minus current Song1 = [Song2, Song3])
        assert len(state.queue) == 2  # Queue restored
        
        # Get next song - should get Song 2 from the restored queue
        song4 = music_service.get_next_song(guild_id)
        assert song4.title == "Song 2"  # First song from restored queue
        # After popping Song 2, queue should have Song 3 remaining
        assert len(state.queue) == 1

    def test_get_next_song_empty_queue(self, music_service, guild_id):
        """Test getting next song from empty queue."""
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        
        song = music_service.get_next_song(guild_id)
        
        assert song is None

    def test_set_current_song(self, music_service, guild_id, sample_song_info):
        """Test setting current song."""
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        
        music_service.set_current_song(guild_id, sample_song_info)
        
        state = music_service.get_playback_state(guild_id)
        assert state.current_song == sample_song_info
        assert state.is_playing is True
        assert state.is_paused is False

    def test_set_playback_state(self, music_service, guild_id):
        """Test setting playback state."""
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        
        music_service.set_playback_state(guild_id, is_playing=False, is_paused=True)
        
        state = music_service.get_playback_state(guild_id)
        assert state.is_playing is False
        assert state.is_paused is True

    def test_clear_current_song(self, music_service, guild_id, sample_song_info):
        """Test clearing current song."""
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        
        # Set a current song first
        state = music_service.get_playback_state(guild_id)
        state.current_song = sample_song_info
        state.is_playing = True
        
        music_service.clear_current_song(guild_id)
        
        assert state.current_song is None
        assert state.is_playing is False
        assert state.is_paused is False

    def test_clear_queue(self, music_service, guild_id, sample_playlist_songs):
        """Test clearing the queue."""
        config = TestConfig.config_with_queue(sample_playlist_songs)
        music_service.config_manager.get_config = Mock(return_value=config)
        music_service.save_playback_state = Mock()
        
        # Setup queue and original queue
        state = music_service.get_playback_state(guild_id)
        music_service._original_queues[guild_id] = sample_playlist_songs.copy()
        
        music_service.clear_queue(guild_id)
        
        assert len(state.queue) == 0
        assert guild_id not in music_service._original_queues
        music_service.save_playback_state.assert_called_once_with(guild_id)

    def test_set_repeat_mode(self, music_service, guild_id):
        """Test setting repeat mode."""
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        music_service.save_playback_state = Mock()
        
        music_service.set_repeat_mode(guild_id, RepeatMode.QUEUE)
        
        state = music_service.get_playback_state(guild_id)
        assert state.repeat_mode == RepeatMode.QUEUE
        music_service.save_playback_state.assert_called_once_with(guild_id)

    def test_set_volume_valid(self, music_service, guild_id):
        """Test setting valid volume."""
        music_service.config_manager.get_config = Mock(return_value=TestConfig.default_config())
        music_service.save_playback_state = Mock()
        
        result = music_service.set_volume(guild_id, 100)
        
        assert result is True
        state = music_service.get_playback_state(guild_id)
        assert state.volume == 100
        music_service.save_playback_state.assert_called_once_with(guild_id)

    def test_set_volume_invalid_low(self, music_service, guild_id):
        """Test setting volume below valid range."""
        result = music_service.set_volume(guild_id, -10)
        assert result is False

    def test_set_volume_invalid_high(self, music_service, guild_id):
        """Test setting volume above valid range."""
        result = music_service.set_volume(guild_id, 200)
        assert result is False

    def test_get_queue_info(self, music_service, guild_id, sample_song_info, sample_playlist_songs):
        """Test getting comprehensive queue information."""
        config = TestConfig.config_with_queue(sample_playlist_songs)
        config["volume"] = 90
        config["repeat_mode"] = "song"
        music_service.config_manager.get_config = Mock(return_value=config)
        
        # Set current song and playback state
        state = music_service.get_playback_state(guild_id)
        state.current_song = sample_song_info
        state.is_playing = True
        state.is_paused = False
        
        queue_info = music_service.get_queue_info(guild_id)
        
        assert queue_info["current_song"] == sample_song_info
        assert len(queue_info["queue"]) == 3
        assert queue_info["queue_length"] == 3
        assert queue_info["repeat_mode"] == RepeatMode.SONG
        assert queue_info["volume"] == 90
        assert queue_info["is_playing"] is True
        assert queue_info["is_paused"] is False

    def test_playback_state_post_init(self):
        """Test PlaybackState post_init method."""
        # Test with None queue
        state1 = PlaybackState()
        assert state1.queue == []
        
        # Test with existing queue
        test_queue = [SongInfo(title="Test", url="test.mp3")]
        state2 = PlaybackState(queue=test_queue)
        assert state2.queue == test_queue

    def test_repeat_mode_enum_values(self):
        """Test RepeatMode enum values."""
        assert RepeatMode.OFF.value == "off"
        assert RepeatMode.SONG.value == "song"
        assert RepeatMode.QUEUE.value == "queue" 