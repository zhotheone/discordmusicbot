import logging

logger = logging.getLogger(__name__)


class SlowFilter:
    """Speed adjustment filter."""
    
    def __init__(self, speed: float = 0.8, pitch: float = 1.0):
        self.speed = max(0.25, min(4.0, speed))
        self.pitch = max(0.25, min(4.0, pitch))
    
    def apply(self, audio_data: bytes) -> bytes:
        """Apply speed/pitch adjustment to audio data."""
        logger.info(f"Applying speed filter (speed: {self.speed}, pitch: {self.pitch})")
        return audio_data
    
    def get_ffmpeg_filter(self) -> str:
        """Get FFmpeg filter string for this effect."""
        if self.speed != self.pitch:
            # Different speed and pitch - need both filters
            return f"atempo={self.speed},rubberband=pitch={self.pitch}"
        else:
            # Same speed and pitch - just use atempo
            return f"atempo={self.speed}"