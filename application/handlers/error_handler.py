import logging
import traceback
from typing import Any

from core.events import EventBus

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Global error handler for the bot."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def handle_error(self, error: Exception, context: str = "Unknown") -> None:
        """Handle an error with proper logging and notification."""
        logger.error(f"Error in {context}: {error}")
        logger.error(traceback.format_exc())
        
        await self.event_bus.publish("error_occurred", error=error, context=context)