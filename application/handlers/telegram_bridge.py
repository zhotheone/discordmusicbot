import html
import logging
from typing import Optional

from core.dependency_injection import DIContainer
from infrastructure.database.repositories import (
    TelegramChatLinkRepository,
    TelegramChatMemberRepository,
)

logger = logging.getLogger(__name__)


class TelegramBridge:
    """Bridge that allows Discord components to communicate with Telegram service."""

    def __init__(self, container: DIContainer):
        self.container = container
        self._chat_repo = TelegramChatLinkRepository(container)
        self._member_repo = TelegramChatMemberRepository(container)
        # TelegramService will register itself here
        self._sender = None  # Optional[TelegramSender]

    def register_sender(self, sender: "TelegramSender") -> None:
        self._sender = sender

    async def send_mention_all(self, guild_id: int, text: Optional[str] = None) -> bool:
        """Send an @all-style mention to linked Telegram chat for a guild.

        Builds per-user HTML mentions for known (non-bot) members in the chat.
        Falls back to plain text if no members are cached.
        """
        try:
            link = await self._chat_repo.get_link_by_guild(guild_id)
            if not link:
                return False
            if not self._sender:
                logger.warning("Telegram sender not registered")
                return False
            header = text or "Summoning everyone from Discord: @all"

            # Fetch known human members from cache
            members = await self._member_repo.list_humans(link.telegram_chat_id)
            logger.info(
                "mention_all: cached human members for chat %s -> %d",
                link.telegram_chat_id,
                len(members),
            )
            # If cache is empty, try falling back to chat administrators
            if not members:
                try:
                    admins = await self._sender.get_chat_administrators(
                        link.telegram_chat_id
                    )
                except Exception as e:
                    logger.info("Failed to get chat admins: %s", e)
                    admins = []
                # Build minimal member-like rows from admins
                admin_members = []
                for adm in admins or []:
                    try:
                        u = getattr(adm, "user", adm)
                        if getattr(u, "is_bot", False):
                            continue
                        admin_members.append(
                            type(
                                "M",
                                (),
                                {
                                    "user_id": getattr(u, "id", None),
                                    "first_name": getattr(u, "first_name", None),
                                    "last_name": getattr(u, "last_name", None),
                                    "username": getattr(u, "username", None),
                                },
                            )
                        )
                    except Exception:
                        continue
                members = admin_members
                logger.info(
                    "mention_all: using admins fallback for chat %s -> %d",
                    link.telegram_chat_id,
                    len(members),
                )
                if not members:
                    # Fallback: send header only
                    await self._sender.send_message(link.telegram_chat_id, header)
                    return True

            # Build HTML mentions
            def display_name(m) -> str:
                name = m.first_name or m.username or "user"
                # Compose full name if available
                if m.last_name and m.first_name:
                    name = f"{m.first_name} {m.last_name}"
                return html.escape(name)

            mentions: list[str] = [
                f'<a href="tg://user?id={m.user_id}">{display_name(m)}</a>'
                for m in members
            ]

            # Telegram has a 4096 char limit; chunk mentions across messages
            MAX_LEN = 4096
            prefix = html.escape(header)
            chunks: list[str] = []
            current = prefix
            sep = "\n"  # put mentions on new lines
            for mention in mentions:
                candidate = (current + sep + mention) if current else mention
                if len(candidate) > MAX_LEN:
                    chunks.append(current)
                    current = mention
                else:
                    current = candidate
            if current:
                chunks.append(current)

            # Send chunks with HTML parse mode
            for idx, chunk in enumerate(chunks):
                await self._sender.send_message(
                    link.telegram_chat_id, chunk, parse_mode="HTML"
                )
            return True
        except Exception as e:
            logger.error(f"Failed to send mention all: {e}")
            return False

    async def link_guild_to_chat(self, guild_id: int, chat_id: int) -> bool:
        """Link a Discord guild to a Telegram chat after verifying bot membership."""
        if not self._sender:
            logger.warning("Telegram sender not registered")
            return False
        try:
            in_chat = await self._sender.check_bot_in_chat(chat_id)
            if not in_chat:
                return False
            await self._chat_repo.upsert_link(guild_id, chat_id)
            return True
        except Exception as e:
            logger.error(f"Failed to link guild {guild_id} to chat {chat_id}: {e}")
            return False


class TelegramSender:
    """Interface that Telegram service implements to send messages."""

    async def send_message(
        self, chat_id: int, text: str, parse_mode: Optional[str] = None
    ) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def check_bot_in_chat(
        self, chat_id: int
    ) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    async def get_chat_administrators(
        self, chat_id: int
    ):  # pragma: no cover - interface
        """Return chat administrators. Implementations may return aiogram types; caller will access `.user` or user-like attrs."""
        raise NotImplementedError
