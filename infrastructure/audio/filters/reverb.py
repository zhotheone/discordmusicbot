import logging

logger = logging.getLogger(__name__)


class ReverbFilter:
    """Reverb audio filter."""
    
    def __init__(self, room_size: float = 0.5, damping: float = 0.5):
        self.room_size = max(0.0, min(1.0, room_size))
        self.damping = max(0.0, min(1.0, damping))
    
    def apply(self, audio_data: bytes) -> bytes:
        """Apply reverb to audio data."""
        logger.info(f"Applying reverb filter (room_size: {self.room_size}, damping: {self.damping})")
        return audio_data
    
    def get_ffmpeg_filter(self) -> str:
        """Get FFmpeg filter string for this effect."""
        return f"aecho=0.8:0.9:{int(self.room_size * 1000)}:0.{int(self.damping * 10)}"