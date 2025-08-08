import asyncio
from typing import Any, Callable, Dict, List
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """Event bus for decoupled communication between components."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_name: str, handler: Callable) -> None:
        """Subscribe to an event."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(handler)
        logger.debug(f"Subscribed handler to event: {event_name}")
    
    def unsubscribe(self, event_name: str, handler: Callable) -> None:
        """Unsubscribe from an event."""
        if event_name in self._subscribers:
            try:
                self._subscribers[event_name].remove(handler)
                logger.debug(f"Unsubscribed handler from event: {event_name}")
            except ValueError:
                pass
    
    async def publish(self, event_name: str, **kwargs: Any) -> None:
        """Publish an event to all subscribers."""
        if event_name not in self._subscribers:
            return
        
        logger.debug(f"Publishing event: {event_name}")
        
        tasks = []
        for handler in self._subscribers[event_name]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(**kwargs))
                else:
                    handler(**kwargs)
            except Exception as e:
                logger.error(f"Error in event handler for {event_name}: {e}")
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Event names constants
class Events:
    TRACK_STARTED = "track_started"
    TRACK_ENDED = "track_ended"
    TRACK_SKIPPED = "track_skipped"
    QUEUE_UPDATED = "queue_updated"
    FILTER_APPLIED = "filter_applied"
    FILTER_REMOVED = "filter_removed"
    USER_JOINED_VOICE = "user_joined_voice"
    USER_LEFT_VOICE = "user_left_voice"
    BOT_DISCONNECTED = "bot_disconnected"