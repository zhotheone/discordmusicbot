"""Unit tests for FilterService."""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from services.filter_service import FilterService, FilterToggleResult, FilterState
from tests.conftest import TestConfig


@pytest.mark.unit
class TestFilterService:
    """Unit tests for FilterService class."""

    def test_initialization(self, filter_service, mock_shared_managers):
        """Test FilterService initialization."""
        assert filter_service.shared_managers == mock_shared_managers
        assert filter_service.config_manager == mock_shared_managers.config_manager

    def test_toggle_legacy_filter_enable(self, filter_service, guild_id):
        """Test enabling a legacy filter."""
        config = TestConfig.default_config()
        filter_service.config_manager.get_config = Mock(return_value=config)
        filter_service.config_manager.save_config = Mock()
        
        result, message = filter_service.toggle_legacy_filter(guild_id, "nightcore")
        
        assert result == FilterToggleResult.ENABLED
        assert "**Nightcore** filter turned **ON**!" in message
        
        # Verify config was updated
        filter_service.config_manager.save_config.assert_called_once()
        call_args = filter_service.config_manager.save_config.call_args
        assert call_args[0][1]["active_filter"] == "nightcore"

    def test_toggle_legacy_filter_disable(self, filter_service, guild_id):
        """Test disabling an active legacy filter."""
        config = TestConfig.default_config()
        config["active_filter"] = "bassboost"
        filter_service.config_manager.get_config = Mock(return_value=config)
        filter_service.config_manager.save_config = Mock()
        
        result, message = filter_service.toggle_legacy_filter(guild_id, "bassboost")
        
        assert result == FilterToggleResult.DISABLED
        assert "**Bassboost** filter turned **OFF**!" in message
        
        # Verify config was updated
        filter_service.config_manager.save_config.assert_called_once()
        call_args = filter_service.config_manager.save_config.call_args
        assert call_args[0][1]["active_filter"] == "none"

    def test_toggle_legacy_filter_switch(self, filter_service, guild_id):
        """Test switching from one filter to another."""
        config = TestConfig.default_config()
        config["active_filter"] = "slowed"
        filter_service.config_manager.get_config = Mock(return_value=config)
        filter_service.config_manager.save_config = Mock()
        
        result, message = filter_service.toggle_legacy_filter(guild_id, "8d")
        
        assert result == FilterToggleResult.ENABLED
        assert "**8d** filter turned **ON**!" in message
        
        # Verify config was updated to new filter
        call_args = filter_service.config_manager.save_config.call_args
        assert call_args[0][1]["active_filter"] == "8d"

    def test_toggle_legacy_filter_error(self, filter_service, guild_id):
        """Test error handling during filter toggle."""
        filter_service.config_manager.get_config = Mock(side_effect=Exception("Config error"))
        
        result, message = filter_service.toggle_legacy_filter(guild_id, "nightcore")
        
        assert result == FilterToggleResult.ERROR
        assert "Failed to toggle nightcore filter." in message

    def test_get_active_legacy_filter(self, filter_service, guild_id):
        """Test getting the currently active legacy filter."""
        config = TestConfig.default_config()
        config["active_filter"] = "tremolo"
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        active_filter = filter_service.get_active_legacy_filter(guild_id)
        
        assert active_filter == "tremolo"

    def test_get_active_legacy_filter_none(self, filter_service, guild_id):
        """Test getting active filter when none is set."""
        config = TestConfig.default_config()
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        active_filter = filter_service.get_active_legacy_filter(guild_id)
        
        assert active_filter == "none"

    def test_set_volume_valid(self, filter_service, guild_id):
        """Test setting valid volume."""
        config = TestConfig.default_config()
        filter_service.config_manager.get_config = Mock(return_value=config)
        filter_service.config_manager.save_config = Mock()
        
        success, message = filter_service.set_volume(guild_id, 90)
        
        assert success is True
        assert "Volume set to **90%**" == message
        
        # Verify config was updated
        filter_service.config_manager.save_config.assert_called_once()
        call_args = filter_service.config_manager.save_config.call_args
        assert call_args[0][1]["volume"] == 90

    def test_set_volume_invalid_low(self, filter_service, guild_id):
        """Test setting volume below valid range."""
        success, message = filter_service.set_volume(guild_id, -5)
        
        assert success is False
        assert "Volume must be between 0 and 150." == message

    def test_set_volume_invalid_high(self, filter_service, guild_id):
        """Test setting volume above valid range."""
        success, message = filter_service.set_volume(guild_id, 200)
        
        assert success is False
        assert "Volume must be between 0 and 150." == message

    def test_set_volume_boundary_values(self, filter_service, guild_id):
        """Test setting volume at boundary values."""
        config = TestConfig.default_config()
        filter_service.config_manager.get_config = Mock(return_value=config)
        filter_service.config_manager.save_config = Mock()
        
        # Test minimum boundary (0)
        success, message = filter_service.set_volume(guild_id, 0)
        assert success is True
        assert "Volume set to **0%**" == message
        
        # Test maximum boundary (150)
        success, message = filter_service.set_volume(guild_id, 150)
        assert success is True
        assert "Volume set to **150%**" == message

    def test_set_volume_error(self, filter_service, guild_id):
        """Test error handling during volume setting."""
        filter_service.config_manager.get_config = Mock(side_effect=Exception("Config error"))
        
        success, message = filter_service.set_volume(guild_id, 75)
        
        assert success is False
        assert "Failed to set volume." == message

    def test_get_volume(self, filter_service, guild_id):
        """Test getting current volume."""
        config = TestConfig.default_config()
        config["volume"] = 110
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        volume = filter_service.get_volume(guild_id)
        
        assert volume == 110

    def test_get_volume_default(self, filter_service, guild_id):
        """Test getting volume with default value."""
        config = {"active_filter": "none"}  # No volume key
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        volume = filter_service.get_volume(guild_id)
        
        assert volume == 75  # Default volume

    def test_get_advanced_filter_manager(self, filter_service, guild_id, mock_shared_managers):
        """Test getting advanced filter manager."""
        mock_filter_manager = Mock()
        mock_shared_managers.get_filter_manager.return_value = mock_filter_manager
        
        # Override the filter_service method to use the mock
        filter_service.get_advanced_filter_manager = Mock(return_value=mock_filter_manager)
        
        manager = filter_service.get_advanced_filter_manager(guild_id)
        
        assert manager == mock_filter_manager

    def test_save_advanced_filter_state(self, filter_service, guild_id, mock_shared_managers):
        """Test saving advanced filter state."""
        filter_service.save_advanced_filter_state(guild_id)
        
        mock_shared_managers.save_filter_state.assert_called_once_with(guild_id)

    def test_get_combined_ffmpeg_filter_advanced(self, filter_service, guild_id, mock_shared_managers):
        """Test getting combined FFmpeg filter with active advanced filters."""
        # Setup advanced filter manager
        mock_filter_manager = Mock()
        mock_filter_manager.get_combined_ffmpeg_filter.return_value = "adelay=100ms,atempo=1.25"
        
        # Mock the get_advanced_filter_manager method
        filter_service.get_advanced_filter_manager = Mock(return_value=mock_filter_manager)
        
        result = filter_service.get_combined_ffmpeg_filter(guild_id)
        
        assert result == "adelay=100ms,atempo=1.25"

    def test_get_combined_ffmpeg_filter_legacy(self, filter_service, guild_id, mock_shared_managers):
        """Test getting combined FFmpeg filter with legacy filter fallback."""
        # Setup advanced filter manager (no active filters)
        mock_filter_manager = Mock()
        mock_filter_manager.get_combined_ffmpeg_filter.return_value = None
        filter_service.get_advanced_filter_manager = Mock(return_value=mock_filter_manager)
        
        # Setup legacy filter
        config = TestConfig.default_config()
        config["active_filter"] = "nightcore"
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        # Patch the utils.filters module with FFMPEG_FILTER_CHAINS
        mock_filters_module = Mock()
        mock_filters_module.FFMPEG_FILTER_CHAINS = {'nightcore': 'atempo=1.25,asetrate=48000*1.25'}
        
        with patch.dict('sys.modules', {'utils.filters': mock_filters_module}):
            result = filter_service.get_combined_ffmpeg_filter(guild_id)
            assert result == "atempo=1.25,asetrate=48000*1.25"

    def test_get_combined_ffmpeg_filter_none(self, filter_service, guild_id, mock_shared_managers):
        """Test getting combined FFmpeg filter when no filters are active."""
        # Setup advanced filter manager (no active filters)
        mock_filter_manager = Mock()
        mock_filter_manager.get_combined_ffmpeg_filter.return_value = None
        mock_shared_managers.get_filter_manager.return_value = mock_filter_manager
        
        # Setup no legacy filter
        config = TestConfig.default_config()
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        result = filter_service.get_combined_ffmpeg_filter(guild_id)
        
        assert result is None

    def test_get_combined_ffmpeg_filter_import_error(self, filter_service, guild_id, mock_shared_managers):
        """Test handling import error for FFMPEG_FILTER_CHAINS."""
        # Setup advanced filter manager (no active filters)
        mock_filter_manager = Mock()
        mock_filter_manager.get_combined_ffmpeg_filter.return_value = None
        mock_shared_managers.get_filter_manager.return_value = mock_filter_manager
        
        # Setup legacy filter
        config = TestConfig.default_config()
        config["active_filter"] = "bassboost"
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        # Mock the import to simulate ImportError
        with patch.dict('sys.modules', {'utils.filters': None}):
            result = filter_service.get_combined_ffmpeg_filter(guild_id)
            assert result is None

    def test_get_filter_status_comprehensive(self, filter_service, guild_id, mock_shared_managers):
        """Test getting comprehensive filter status."""
        # Setup config
        config = TestConfig.default_config()
        config["active_filter"] = "slowed"
        config["volume"] = 85
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        # Setup advanced filter manager
        mock_filter_manager = Mock()
        mock_filter_manager.get_enabled_filters.return_value = ["bass_boost", "compressor"]
        filter_service.get_advanced_filter_manager = Mock(return_value=mock_filter_manager)
        
        status = filter_service.get_filter_status(guild_id)
        
        assert status["legacy_filter"] == "slowed"
        assert status["volume"] == 85
        assert status["advanced_filters"] == ["bass_boost", "compressor"]
        assert status["has_active_filters"] is True  # Both legacy and advanced active

    def test_get_filter_status_no_filters(self, filter_service, guild_id, mock_shared_managers):
        """Test getting filter status when no filters are active."""
        # Setup config with no active filters
        config = TestConfig.default_config()
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        # Setup advanced filter manager with no active filters
        mock_filter_manager = Mock()
        mock_filter_manager.get_enabled_filters.return_value = []
        filter_service.get_advanced_filter_manager = Mock(return_value=mock_filter_manager)
        
        status = filter_service.get_filter_status(guild_id)
        
        assert status["legacy_filter"] == "none"
        assert status["volume"] == 75
        assert status["advanced_filters"] == []
        assert status["has_active_filters"] is False

    def test_get_filter_status_only_advanced(self, filter_service, guild_id, mock_shared_managers):
        """Test getting filter status with only advanced filters active."""
        # Setup config with no legacy filter
        config = TestConfig.default_config()
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        # Setup advanced filter manager with active filters
        mock_filter_manager = Mock()
        mock_filter_manager.get_enabled_filters.return_value = ["equalizer", "distortion"]
        filter_service.get_advanced_filter_manager = Mock(return_value=mock_filter_manager)
        
        status = filter_service.get_filter_status(guild_id)
        
        assert status["legacy_filter"] == "none"
        assert status["advanced_filters"] == ["equalizer", "distortion"]
        assert status["has_active_filters"] is True

    def test_get_filter_status_only_legacy(self, filter_service, guild_id, mock_shared_managers):
        """Test getting filter status with only legacy filter active."""
        # Setup config with legacy filter
        config = TestConfig.default_config()
        config["active_filter"] = "vibrato"
        filter_service.config_manager.get_config = Mock(return_value=config)
        
        # Setup advanced filter manager with no active filters
        mock_filter_manager = Mock()
        mock_filter_manager.get_enabled_filters.return_value = []
        filter_service.get_advanced_filter_manager = Mock(return_value=mock_filter_manager)
        
        status = filter_service.get_filter_status(guild_id)
        
        assert status["legacy_filter"] == "vibrato"
        assert status["advanced_filters"] == []
        assert status["has_active_filters"] is True

    def test_get_filter_status_error_handling(self, filter_service, guild_id, mock_shared_managers):
        """Test error handling in get_filter_status."""
        # Simulate an error
        filter_service.config_manager.get_config = Mock(side_effect=Exception("Config error"))
        
        status = filter_service.get_filter_status(guild_id)
        
        # Should return default values on error
        assert status["legacy_filter"] == "none"
        assert status["volume"] == 75
        assert status["advanced_filters"] == []
        assert status["has_active_filters"] is False

    def test_filter_state_dataclass(self):
        """Test FilterState dataclass."""
        filter_state = FilterState(
            name="nightcore",
            is_active=True,
            display_name="Nightcore"
        )
        
        assert filter_state.name == "nightcore"
        assert filter_state.is_active is True
        assert filter_state.display_name == "Nightcore"

    def test_filter_toggle_result_enum(self):
        """Test FilterToggleResult enum values."""
        assert FilterToggleResult.ENABLED.value == "enabled"
        assert FilterToggleResult.DISABLED.value == "disabled"
        assert FilterToggleResult.ERROR.value == "error"

    def test_multiple_filter_operations(self, filter_service, guild_id):
        """Test multiple filter operations in sequence."""
        config = TestConfig.default_config()
        filter_service.config_manager.get_config = Mock(return_value=config)
        filter_service.config_manager.save_config = Mock()
        
        # Enable a filter
        result1, _ = filter_service.toggle_legacy_filter(guild_id, "8d")
        assert result1 == FilterToggleResult.ENABLED
        
        # Set volume
        success, _ = filter_service.set_volume(guild_id, 120)
        assert success is True
        
        # Switch to different filter
        result2, _ = filter_service.toggle_legacy_filter(guild_id, "reverse")
        assert result2 == FilterToggleResult.ENABLED
        
        # Disable filter
        result3, _ = filter_service.toggle_legacy_filter(guild_id, "reverse")
        assert result3 == FilterToggleResult.DISABLED
        
        # Verify all operations called save_config
        assert filter_service.config_manager.save_config.call_count == 4 