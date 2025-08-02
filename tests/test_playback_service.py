"""Unit tests for PlaybackService."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from services.playback_service import PlaybackService
from services.music_service import SongInfo
from tests.conftest import TestConfig


@pytest.mark.unit
class TestPlaybackService:
    """Unit tests for PlaybackService class."""

    def test_initialization(self, playback_service, mock_shared_managers):
        """Test PlaybackService initialization."""
        assert playback_service.shared_managers == mock_shared_managers
        assert playback_service._current_songs == {}

    @pytest.mark.asyncio
    async def test_create_audio_source_success(self, playback_service, guild_id, sample_song_info, mock_discord_audio_source):
        """Test successful audio source creation."""
        # Mock filter service
        mock_filter_service = Mock()
        mock_filter_service.get_combined_ffmpeg_filter.return_value = "atempo=1.25"
        mock_filter_service.get_volume.return_value = 80
        playback_service._get_filter_service = Mock(return_value=mock_filter_service)
        
        with patch('services.playback_service.discord.FFmpegPCMAudio') as mock_audio:
            with patch('services.playback_service.discord.PCMVolumeTransformer') as mock_transformer:
                mock_player = Mock()
                mock_audio.return_value = mock_player
                mock_source = Mock()
                mock_transformer.return_value = mock_source
                
                result = await playback_service._create_audio_source(guild_id, sample_song_info)
                
                assert result == mock_source
                
                # Verify FFmpeg was called with filters
                mock_audio.assert_called_once()
                call_args = mock_audio.call_args
                assert sample_song_info.url in call_args[0]
                ffmpeg_options = call_args[1]
                assert '-af "atempo=1.25"' in ffmpeg_options['options']
                
                # Verify volume transformer was called
                mock_transformer.assert_called_once_with(mock_player, volume=0.8)

    @pytest.mark.asyncio
    async def test_create_audio_source_no_filters(self, playback_service, guild_id, sample_song_info):
        """Test audio source creation without filters."""
        # Mock filter service with no active filters
        mock_filter_service = Mock()
        mock_filter_service.get_combined_ffmpeg_filter.return_value = None
        mock_filter_service.get_volume.return_value = 75
        playback_service._get_filter_service = Mock(return_value=mock_filter_service)
        
        with patch('services.playback_service.discord.FFmpegPCMAudio') as mock_audio:
            with patch('services.playback_service.discord.PCMVolumeTransformer') as mock_transformer:
                mock_player = Mock()
                mock_audio.return_value = mock_player
                mock_source = Mock()
                mock_transformer.return_value = mock_source
                
                result = await playback_service._create_audio_source(guild_id, sample_song_info)
                
                assert result == mock_source
                
                # Verify no filters were applied
                call_args = mock_audio.call_args
                ffmpeg_options = call_args[1]
                assert '-af' not in ffmpeg_options['options']

    @pytest.mark.asyncio
    async def test_create_audio_source_error(self, playback_service, guild_id, sample_song_info):
        """Test audio source creation error handling."""
        mock_filter_service = Mock()
        mock_filter_service.get_combined_ffmpeg_filter.return_value = None
        mock_filter_service.get_volume.return_value = 75
        playback_service._get_filter_service = Mock(return_value=mock_filter_service)
        
        with patch('services.playback_service.discord.FFmpegPCMAudio', side_effect=Exception("Audio error")):
            result = await playback_service._create_audio_source(guild_id, sample_song_info)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_play_song_success(self, playback_service, guild_id, sample_song_info, mock_discord_voice_client):
        """Test successful song playback."""
        # Mock music service
        mock_music_service = Mock()
        mock_music_service.get_next_song.return_value = sample_song_info
        mock_music_service.set_current_song = Mock()
        playback_service._get_music_service = Mock(return_value=mock_music_service)
        
        # Mock audio source creation
        mock_source = Mock()
        playback_service._create_audio_source = AsyncMock(return_value=mock_source)
        
        # Mock callback
        after_callback = Mock()
        
        result = await playback_service.play_song(guild_id, mock_discord_voice_client, after_callback)
        
        assert result is True
        
        # Verify music service interactions
        mock_music_service.get_next_song.assert_called_once_with(guild_id)
        mock_music_service.set_current_song.assert_called_once_with(guild_id, sample_song_info)
        
        # Verify voice client play was called
        mock_discord_voice_client.play.assert_called_once_with(mock_source, after=after_callback)
        
        # Verify current song was stored
        assert playback_service._current_songs[guild_id] == sample_song_info

    @pytest.mark.asyncio
    async def test_play_song_no_songs_in_queue(self, playback_service, guild_id, mock_discord_voice_client):
        """Test play_song when queue is empty."""
        # Mock music service returning no song
        mock_music_service = Mock()
        mock_music_service.get_next_song.return_value = None
        mock_music_service.clear_current_song = Mock()
        playback_service._get_music_service = Mock(return_value=mock_music_service)
        
        result = await playback_service.play_song(guild_id, mock_discord_voice_client)
        
        assert result is False
        mock_music_service.clear_current_song.assert_called_once_with(guild_id)
        mock_discord_voice_client.play.assert_not_called()

    @pytest.mark.asyncio
    async def test_play_song_audio_source_creation_fails(self, playback_service, guild_id, sample_song_info, mock_discord_voice_client):
        """Test play_song when audio source creation fails."""
        # Mock music service
        mock_music_service = Mock()
        mock_music_service.get_next_song.return_value = sample_song_info
        mock_music_service.set_current_song = Mock()
        playback_service._get_music_service = Mock(return_value=mock_music_service)
        
        # Mock audio source creation failure
        playback_service._create_audio_source = AsyncMock(return_value=None)
        
        result = await playback_service.play_song(guild_id, mock_discord_voice_client)
        
        assert result is False
        mock_discord_voice_client.play.assert_not_called()

    @pytest.mark.asyncio
    async def test_play_song_exception_handling(self, playback_service, guild_id, mock_discord_voice_client):
        """Test play_song exception handling."""
        # Mock music service that raises exception
        mock_music_service = Mock()
        mock_music_service.get_next_song.side_effect = Exception("Service error")
        playback_service._get_music_service = Mock(return_value=mock_music_service)
        
        result = await playback_service.play_song(guild_id, mock_discord_voice_client)
        
        assert result is False

    def test_get_current_song(self, playback_service, guild_id, sample_song_info):
        """Test getting current song."""
        playback_service._current_songs[guild_id] = sample_song_info
        
        result = playback_service.get_current_song(guild_id)
        
        assert result == sample_song_info

    def test_get_current_song_not_exists(self, playback_service, guild_id):
        """Test getting current song when none exists."""
        result = playback_service.get_current_song(guild_id)
        
        assert result is None

    def test_set_playback_state(self, playback_service, guild_id):
        """Test setting playback state."""
        mock_music_service = Mock()
        playback_service._get_music_service = Mock(return_value=mock_music_service)
        
        playback_service.set_playback_state(guild_id, is_playing=True, is_paused=False)
        
        mock_music_service.set_playback_state.assert_called_once_with(guild_id, True, False)

    def test_clear_current_song(self, playback_service, guild_id, sample_song_info):
        """Test clearing current song."""
        # Set current song first
        playback_service._current_songs[guild_id] = sample_song_info
        
        mock_music_service = Mock()
        playback_service._get_music_service = Mock(return_value=mock_music_service)
        
        playback_service.clear_current_song(guild_id)
        
        assert guild_id not in playback_service._current_songs
        mock_music_service.clear_current_song.assert_called_once_with(guild_id)

    def test_clear_current_song_not_exists(self, playback_service, guild_id):
        """Test clearing current song when none exists."""
        mock_music_service = Mock()
        playback_service._get_music_service = Mock(return_value=mock_music_service)
        
        playback_service.clear_current_song(guild_id)
        
        # Should not raise error
        mock_music_service.clear_current_song.assert_called_once_with(guild_id)

    @pytest.mark.asyncio
    async def test_apply_filters_to_current_song_success(self, playback_service, guild_id, sample_song_info, mock_discord_voice_client):
        """Test successfully applying filters to current song."""
        # Setup current song
        playback_service._current_songs[guild_id] = sample_song_info
        
        # Mock voice client state
        mock_discord_voice_client.is_connected.return_value = True
        mock_discord_voice_client.is_playing.return_value = True
        mock_discord_voice_client.is_paused.return_value = False
        
        # Mock audio source creation
        mock_source = Mock()
        playback_service._create_audio_source = AsyncMock(return_value=mock_source)
        
        result = await playback_service.apply_filters_to_current_song(guild_id, mock_discord_voice_client)
        
        assert result is True
        
        # Verify voice client operations
        mock_discord_voice_client.stop.assert_called_once()
        mock_discord_voice_client.play.assert_called_once_with(mock_source)
        mock_discord_voice_client.pause.assert_not_called()  # Wasn't paused initially

    @pytest.mark.asyncio
    async def test_apply_filters_to_current_song_was_paused(self, playback_service, guild_id, sample_song_info, mock_discord_voice_client):
        """Test applying filters to current song that was paused."""
        playback_service._current_songs[guild_id] = sample_song_info
        
        # Mock voice client state (paused)
        mock_discord_voice_client.is_connected.return_value = True
        mock_discord_voice_client.is_playing.return_value = False
        mock_discord_voice_client.is_paused.return_value = True
        
        mock_source = Mock()
        playback_service._create_audio_source = AsyncMock(return_value=mock_source)
        
        result = await playback_service.apply_filters_to_current_song(guild_id, mock_discord_voice_client)
        
        assert result is True
        mock_discord_voice_client.pause.assert_called_once()  # Should restore paused state

    @pytest.mark.asyncio
    async def test_apply_filters_no_voice_client(self, playback_service, guild_id):
        """Test applying filters when voice client is not connected."""
        result = await playback_service.apply_filters_to_current_song(guild_id, None)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_apply_filters_not_playing(self, playback_service, guild_id, mock_discord_voice_client):
        """Test applying filters when nothing is playing."""
        mock_discord_voice_client.is_connected.return_value = True
        mock_discord_voice_client.is_playing.return_value = False
        mock_discord_voice_client.is_paused.return_value = False
        
        result = await playback_service.apply_filters_to_current_song(guild_id, mock_discord_voice_client)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_apply_filters_no_current_song(self, playback_service, guild_id, mock_discord_voice_client):
        """Test applying filters when no current song exists."""
        mock_discord_voice_client.is_connected.return_value = True
        mock_discord_voice_client.is_playing.return_value = True
        
        result = await playback_service.apply_filters_to_current_song(guild_id, mock_discord_voice_client)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_apply_filters_audio_source_creation_fails(self, playback_service, guild_id, sample_song_info, mock_discord_voice_client):
        """Test applying filters when audio source creation fails."""
        playback_service._current_songs[guild_id] = sample_song_info
        mock_discord_voice_client.is_connected.return_value = True
        mock_discord_voice_client.is_playing.return_value = True
        
        # Mock audio source creation failure
        playback_service._create_audio_source = AsyncMock(return_value=None)
        
        result = await playback_service.apply_filters_to_current_song(guild_id, mock_discord_voice_client)
        
        assert result is False

    def test_update_volume_success(self, playback_service, guild_id, mock_discord_voice_client):
        """Test successfully updating volume."""
        # Mock voice client with source
        mock_source = Mock()
        mock_discord_voice_client.source = mock_source
        
        # Mock filter service
        mock_filter_service = Mock()
        mock_filter_service.set_volume.return_value = (True, "Volume set to **90%**")
        playback_service._get_filter_service = Mock(return_value=mock_filter_service)
        
        result = playback_service.update_volume(guild_id, mock_discord_voice_client, 90)
        
        assert result is True
        mock_filter_service.set_volume.assert_called_once_with(guild_id, 90)
        assert mock_source.volume == 0.9  # 90/100

    def test_update_volume_filter_service_fails(self, playback_service, guild_id, mock_discord_voice_client):
        """Test volume update when filter service fails."""
        mock_filter_service = Mock()
        mock_filter_service.set_volume.return_value = (False, "Invalid volume")
        playback_service._get_filter_service = Mock(return_value=mock_filter_service)
        
        result = playback_service.update_volume(guild_id, mock_discord_voice_client, 200)
        
        assert result is False

    def test_update_volume_no_voice_client_source(self, playback_service, guild_id):
        """Test volume update when voice client has no source."""
        mock_filter_service = Mock()
        mock_filter_service.set_volume.return_value = (True, "Volume set")
        playback_service._get_filter_service = Mock(return_value=mock_filter_service)
        
        # Voice client without source
        mock_voice_client = Mock()
        mock_voice_client.source = None
        
        result = playback_service.update_volume(guild_id, mock_voice_client, 80)
        
        assert result is True  # Should still succeed even without voice client source

    def test_update_volume_exception(self, playback_service, guild_id, mock_discord_voice_client):
        """Test volume update exception handling."""
        mock_filter_service = Mock()
        mock_filter_service.set_volume.side_effect = Exception("Service error")
        playback_service._get_filter_service = Mock(return_value=mock_filter_service)
        
        result = playback_service.update_volume(guild_id, mock_discord_voice_client, 80)
        
        assert result is False

    def test_get_playback_info(self, playback_service, guild_id, sample_song_info):
        """Test getting comprehensive playback information."""
        # Setup current song
        playback_service._current_songs[guild_id] = sample_song_info
        
        # Mock services
        mock_music_service = Mock()
        mock_music_info = {
            "current_song": sample_song_info,
            "queue": [],
            "queue_length": 0,
            "repeat_mode": "off",
            "volume": 75,
            "is_playing": True,
            "is_paused": False
        }
        mock_music_service.get_queue_info.return_value = mock_music_info
        
        mock_filter_service = Mock()
        mock_filter_info = {
            "legacy_filter": "none",
            "volume": 75,
            "advanced_filters": [],
            "has_active_filters": False
        }
        mock_filter_service.get_filter_status.return_value = mock_filter_info
        
        playback_service._get_music_service = Mock(return_value=mock_music_service)
        playback_service._get_filter_service = Mock(return_value=mock_filter_service)
        
        result = playback_service.get_playback_info(guild_id)
        
        # Should combine both music and filter info
        expected_keys = set(mock_music_info.keys()) | set(mock_filter_info.keys()) | {"current_song_cached"}
        assert set(result.keys()) == expected_keys
        assert result["current_song_cached"] == sample_song_info

    def test_multiple_guilds_isolation(self, playback_service, sample_song_info):
        """Test that different guilds maintain separate state."""
        guild1_id = 12345
        guild2_id = 67890
        
        # Set different current songs for different guilds
        playback_service._current_songs[guild1_id] = sample_song_info
        
        guild2_song = SongInfo(title="Guild 2 Song", url="test2.mp3")
        playback_service._current_songs[guild2_id] = guild2_song
        
        assert playback_service.get_current_song(guild1_id) == sample_song_info
        assert playback_service.get_current_song(guild2_id) == guild2_song
        
        # Clear one guild shouldn't affect the other
        playback_service.clear_current_song(guild1_id)
        
        assert playback_service.get_current_song(guild1_id) is None
        assert playback_service.get_current_song(guild2_id) == guild2_song

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, playback_service, guild_id, sample_song_info, mock_discord_voice_client):
        """Test concurrent operations on the same guild."""
        playback_service._current_songs[guild_id] = sample_song_info
        
        # Mock audio source creation with delay
        async def delayed_audio_source(*args, **kwargs):
            await asyncio.sleep(0.01)  # Small delay
            return Mock()
        
        playback_service._create_audio_source = delayed_audio_source
        
        # Start multiple filter applications concurrently
        mock_discord_voice_client.is_connected.return_value = True
        mock_discord_voice_client.is_playing.return_value = True
        
        tasks = [
            playback_service.apply_filters_to_current_song(guild_id, mock_discord_voice_client)
            for _ in range(3)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed (though the actual behavior depends on implementation)
        assert all(isinstance(result, bool) for result in results) 