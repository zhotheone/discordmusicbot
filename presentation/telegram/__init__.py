import logging

from application.handlers.telegram_bridge import TelegramBridge
from config.settings import Settings
from core.dependency_injection import DIContainer

from .bot import TelegramService

logger = logging.getLogger(__name__)


async def start_telegram(container: DIContainer, settings: Settings) -> None:
    if not settings.enable_telegram:
        logger.info("Telegram is disabled; skipping startup")
        return

    bridge = TelegramBridge(container)
    container.register(TelegramBridge, bridge)

    service = TelegramService(container, settings)
    # Register sender into the bridge so Discord code can call Telegram
    bridge.register_sender(service)

    await service.start()
