"""Advanced Audio Filter System for Discord Bot.

This module provides a comprehensive audio filter system that allows:
- Multiple simultaneous filters
- Runtime parameter adjustment
- Custom filter combinations
- Filter presets
"""

from typing import Dict, List, Optional, Union


class FilterParameter:
    """Represents a configurable filter parameter."""
    
    def __init__(
        self, 
        name: str, 
        value: Union[int, float], 
        min_val: Union[int, float], 
        max_val: Union[int, float],
        description: str = ""
    ):
        self.name = name
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        self.description = description
    
    def set_value(self, value: Union[int, float]) -> bool:
        """Set parameter value with validation."""
        if self.min_val <= value <= self.max_val:
            self.value = value
            return True
        return False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'value': self.value,
            'min_val': self.min_val,
            'max_val': self.max_val,
            'description': self.description
        }


class AudioFilter:
    """Represents an audio filter with configurable parameters."""
    
    def __init__(self, name: str, ffmpeg_template: str, description: str = ""):
        self.name = name
        self.ffmpeg_template = ffmpeg_template
        self.description = description
        self.parameters: Dict[str, FilterParameter] = {}
        self.enabled = False
    
    def add_parameter(self, param: FilterParameter):
        """Add a configurable parameter to this filter."""
        self.parameters[param.name] = param
    
    def set_parameter(self, param_name: str, value: Union[int, float]) -> bool:
        """Set a parameter value."""
        if param_name in self.parameters:
            return self.parameters[param_name].set_value(value)
        return False
    
    def get_ffmpeg_filter(self) -> str:
        """Generate FFmpeg filter string with current parameters."""
        if not self.enabled:
            return ""
        
        # Replace template placeholders with actual values
        filter_str = self.ffmpeg_template
        for param_name, param in self.parameters.items():
            placeholder = f"{{{param_name}}}"
            filter_str = filter_str.replace(placeholder, str(param.value))
        
        return filter_str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'ffmpeg_template': self.ffmpeg_template,
            'description': self.description,
            'enabled': self.enabled,
            'parameters': {name: param.to_dict() for name, param in self.parameters.items()}
        }


class FilterPreset:
    """Represents a collection of filters with specific settings."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.filters: Dict[str, Dict] = {}  # filter_name -> parameter settings
    
    def add_filter_config(self, filter_name: str, enabled: bool, parameters: Dict[str, Union[int, float]]):
        """Add a filter configuration to this preset."""
        self.filters[filter_name] = {
            'enabled': enabled,
            'parameters': parameters
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'description': self.description,
            'filters': self.filters
        }


class AdvancedFilterManager:
    """Manages multiple audio filters and their combinations."""
    
    def __init__(self):
        self.filters: Dict[str, AudioFilter] = {}
        self.presets: Dict[str, FilterPreset] = {}
        self._initialize_default_filters()
        self._initialize_default_presets()
    
    def _initialize_default_filters(self):
        """Initialize default audio filters with configurable parameters."""
        
        # Bass Boost Filter
        bass_filter = AudioFilter(
            "bassboost",
            "bass=g={gain},dynaudnorm=f={frequency}",
            "Enhance low-frequency sounds"
        )
        bass_filter.add_parameter(FilterParameter("gain", 15, 0, 30, "Bass gain in dB"))
        bass_filter.add_parameter(FilterParameter("frequency", 200, 100, 500, "Dynamic normalization frequency"))
        self.filters["bassboost"] = bass_filter
        
        # Nightcore Filter
        nightcore_filter = AudioFilter(
            "nightcore",
            "atempo={tempo},asetrate=44100*{pitch_factor},bass=g={bass_gain}",
            "Speed up and pitch up audio"
        )
        nightcore_filter.add_parameter(FilterParameter("tempo", 1.3, 1.0, 2.0, "Playback speed multiplier"))
        nightcore_filter.add_parameter(FilterParameter("pitch_factor", 1.3, 1.0, 2.0, "Pitch adjustment factor"))
        nightcore_filter.add_parameter(FilterParameter("bass_gain", 5, 0, 15, "Bass compensation"))
        self.filters["nightcore"] = nightcore_filter
        
        # Slowed + Reverb Filter
        slowed_filter = AudioFilter(
            "slowed",
            "atempo={tempo},aecho={in_gain}:{out_gain}:{delay}:{decay}",
            "Slow down with reverb effect"
        )
        slowed_filter.add_parameter(FilterParameter("tempo", 0.8, 0.5, 1.0, "Playback speed"))
        slowed_filter.add_parameter(FilterParameter("in_gain", 0.8, 0.1, 1.0, "Input gain"))
        slowed_filter.add_parameter(FilterParameter("out_gain", 0.9, 0.1, 1.0, "Output gain"))
        slowed_filter.add_parameter(FilterParameter("delay", 1000, 100, 2000, "Echo delay in ms"))
        slowed_filter.add_parameter(FilterParameter("decay", 0.3, 0.1, 0.9, "Echo decay"))
        self.filters["slowed"] = slowed_filter
        
        # 8D Audio Filter
        audio_8d_filter = AudioFilter(
            "8d",
            "apulsator=hz={frequency}",
            "Create 8D surround sound effect"
        )
        audio_8d_filter.add_parameter(FilterParameter("frequency", 0.2, 0.1, 2.0, "Pulsation frequency"))
        self.filters["8d"] = audio_8d_filter
        
        # Equalizer Filter
        equalizer_filter = AudioFilter(
            "equalizer",
            "equalizer=f={freq1}:t=h:w={width1}:g={gain1}:f={freq2}:t=h:w={width2}:g={gain2}:f={freq3}:t=h:w={width3}:g={gain3}",
            "3-band equalizer"
        )
        equalizer_filter.add_parameter(FilterParameter("freq1", 100, 20, 500, "Low frequency center"))
        equalizer_filter.add_parameter(FilterParameter("gain1", 0, -20, 20, "Low frequency gain"))
        equalizer_filter.add_parameter(FilterParameter("width1", 50, 10, 200, "Low frequency width"))
        equalizer_filter.add_parameter(FilterParameter("freq2", 1000, 500, 5000, "Mid frequency center"))
        equalizer_filter.add_parameter(FilterParameter("gain2", 0, -20, 20, "Mid frequency gain"))
        equalizer_filter.add_parameter(FilterParameter("width2", 100, 10, 500, "Mid frequency width"))
        equalizer_filter.add_parameter(FilterParameter("freq3", 8000, 2000, 20000, "High frequency center"))
        equalizer_filter.add_parameter(FilterParameter("gain3", 0, -20, 20, "High frequency gain"))
        equalizer_filter.add_parameter(FilterParameter("width3", 200, 10, 1000, "High frequency width"))
        self.filters["equalizer"] = equalizer_filter
        
        # Overdrive Filter (tube-like warm overdrive using different approach)
        overdrive_filter = AudioFilter(
            "overdrive",
            "volume={drive}dB,alimiter=level_in={level_in}:level_out={level_out}:limit={limit}:attack=5:release=50,volume={output}dB",
            "Warm tube-like overdrive effect"
        )
        overdrive_filter.add_parameter(FilterParameter("drive", 12, 3, 30, "Overdrive amount in dB"))
        overdrive_filter.add_parameter(FilterParameter("level_in", 1.0, 0.5, 2.0, "Input level multiplier"))
        overdrive_filter.add_parameter(FilterParameter("level_out", 0.8, 0.3, 1.0, "Output level multiplier"))
        overdrive_filter.add_parameter(FilterParameter("limit", 0.9, 0.5, 0.98, "Limiter threshold"))
        overdrive_filter.add_parameter(FilterParameter("output", -3, -10, 3, "Final output gain in dB"))
        self.filters["overdrive"] = overdrive_filter
        
        # Compressor Filter
        compressor_filter = AudioFilter(
            "compressor",
            "acompressor=threshold={threshold}:ratio={ratio}:attack={attack}:release={release}",
            "Dynamic range compression"
        )
        compressor_filter.add_parameter(FilterParameter("threshold", 0.5, 0.1, 1.0, "Compression threshold"))
        compressor_filter.add_parameter(FilterParameter("ratio", 4, 1, 20, "Compression ratio"))
        compressor_filter.add_parameter(FilterParameter("attack", 5, 1, 100, "Attack time in ms"))
        compressor_filter.add_parameter(FilterParameter("release", 50, 10, 1000, "Release time in ms"))
        self.filters["compressor"] = compressor_filter
    
    def _initialize_default_presets(self):
        """Initialize default filter presets."""
        
        # Gaming preset
        gaming_preset = FilterPreset("gaming", "Optimized for gaming audio")
        gaming_preset.add_filter_config("compressor", True, {"threshold": 0.3, "ratio": 6, "attack": 2, "release": 30})
        gaming_preset.add_filter_config("equalizer", True, {"freq2": 2000, "gain2": 3, "freq3": 6000, "gain3": 2})
        self.presets["gaming"] = gaming_preset
        
        # Music preset
        music_preset = FilterPreset("music", "Enhanced music listening")
        music_preset.add_filter_config("bassboost", True, {"gain": 8, "frequency": 150})
        music_preset.add_filter_config("equalizer", True, {"freq1": 80, "gain1": 2, "freq3": 12000, "gain3": 1})
        self.presets["music"] = music_preset
        
        # Vocal preset
        vocal_preset = FilterPreset("vocal", "Optimized for voice/podcasts")
        vocal_preset.add_filter_config("compressor", True, {"threshold": 0.6, "ratio": 3, "attack": 1, "release": 100})
        vocal_preset.add_filter_config("equalizer", True, {"freq2": 1500, "gain2": 4, "width2": 200})
        self.presets["vocal"] = vocal_preset
    
    def get_filter(self, name: str) -> Optional[AudioFilter]:
        """Get a filter by name."""
        return self.filters.get(name)
    
    def enable_filter(self, name: str) -> bool:
        """Enable a filter."""
        if name in self.filters:
            self.filters[name].enabled = True
            return True
        return False
    
    def disable_filter(self, name: str) -> bool:
        """Disable a filter."""
        if name in self.filters:
            self.filters[name].enabled = False
            return True
        return False
    
    def set_filter_parameter(self, filter_name: str, param_name: str, value: Union[int, float]) -> bool:
        """Set a parameter for a specific filter."""
        if filter_name in self.filters:
            return self.filters[filter_name].set_parameter(param_name, value)
        return False
    
    def get_combined_ffmpeg_filter(self) -> str:
        """Generate combined FFmpeg filter string for all enabled filters."""
        enabled_filters = [f.get_ffmpeg_filter() for f in self.filters.values() if f.enabled]
        if enabled_filters:
            return ",".join(filter(None, enabled_filters))
        return ""
    
    def apply_preset(self, preset_name: str) -> bool:
        """Apply a filter preset."""
        if preset_name not in self.presets:
            return False
        
        preset = self.presets[preset_name]
        
        # First disable all filters
        for filter_obj in self.filters.values():
            filter_obj.enabled = False
        
        # Apply preset configuration
        for filter_name, config in preset.filters.items():
            if filter_name in self.filters:
                self.filters[filter_name].enabled = config['enabled']
                for param_name, param_value in config['parameters'].items():
                    self.set_filter_parameter(filter_name, param_name, param_value)
        
        return True
    
    def get_enabled_filters(self) -> List[str]:
        """Get list of currently enabled filter names."""
        return [name for name, filter_obj in self.filters.items() if filter_obj.enabled]
    
    def get_filter_info(self, filter_name: str) -> Optional[Dict]:
        """Get detailed information about a filter."""
        if filter_name not in self.filters:
            return None
        
        filter_obj = self.filters[filter_name]
        return {
            'name': filter_obj.name,
            'description': filter_obj.description,
            'enabled': filter_obj.enabled,
            'parameters': {
                name: {
                    'value': param.value,
                    'min': param.min_val,
                    'max': param.max_val,
                    'description': param.description
                }
                for name, param in filter_obj.parameters.items()
            }
        }
    
    def list_available_filters(self) -> List[str]:
        """Get list of all available filter names."""
        return list(self.filters.keys())
    
    def list_available_presets(self) -> List[str]:
        """Get list of all available preset names."""
        return list(self.presets.keys())
    
    def to_dict(self) -> dict:
        """Convert entire filter manager state to dictionary."""
        return {
            'filters': {name: filter_obj.to_dict() for name, filter_obj in self.filters.items()},
            'presets': {name: preset.to_dict() for name, preset in self.presets.items()}
        }