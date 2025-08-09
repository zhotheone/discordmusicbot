import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, Message

from application.handlers.telegram_bridge import TelegramSender
from config.settings import Settings
from core.dependency_injection import DIContainer
from core.events import EventBus, Events
from domain.services.music_service import MusicService
from infrastructure.audio.sources.spotify import SpotifySource
from infrastructure.audio.sources.youtube import YouTubeSource
from infrastructure.database.repositories import (
    TelegramChatLinkRepository,
    TelegramChatMemberRepository,
)

logger = logging.getLogger(__name__)


class TelegramService(TelegramSender):
    """Aiogram-based Telegram bot service.

    Provides:
    - /list: list online Discord users and statuses
    - /play <query|url>: play a song on Discord
    - /queue: show the current playback queue
    - /stop: stop playback
    - /volume <0-100>: set the playback volume
    """

    def __init__(self, container: DIContainer, settings: Settings):
        self.container = container
        self.settings = settings
        self._bot = None
        self._dp = None
        self._router = None
        self._chat_repo = TelegramChatLinkRepository(container)
        # Cache of telegram chat members for mentions
        self._member_repo = TelegramChatMemberRepository(container)
        # Music control dependencies
        self._music = None  # lazy: resolve from container when used
        self._yt = YouTubeSource()
        self._sp = SpotifySource()
        # Events
        self._event_bus = container.get(EventBus)

    async def start(self) -> None:
        if not self.settings.telegram_token:
            logger.warning("TELEGRAM_TOKEN missing; Telegram service won't start")
            return
        self._bot = Bot(token=self.settings.telegram_token)
        self._dp = Dispatcher()
        self._router = Router()
        self._register_handlers()
        self._dp.include_router(self._router)
        # Subscribe to music/status events to mirror updates into Telegram
        self._subscribe_events()
        # Set bot commands for better UX
        await self._set_bot_commands()
        logger.info("Starting Telegram bot polling...")
        # Run polling in background task
        asyncio.create_task(self._dp.start_polling(self._bot))

    def _register_handlers(self) -> None:
        assert self._router is not None

        @self._router.message(Command("list"))
        async def list_handler(message: Message):
            # Fetch list of online Discord users for the linked guild only
            try:
                guild_id = await self._get_linked_guild_id(message.chat.id)
                if not guild_id:
                    await message.answer(
                        "This chat isn't linked to a Discord server yet. Ask an admin to run /connect_telegram in Discord."
                    )
                    return
                bot = self.container.get("Bot")
                guild = next((g for g in bot.guilds if g.id == guild_id), None)
                if not guild:
                    await message.answer("Linked Discord server is not available.")
                    return
                members = [m for m in guild.members if not m.bot]
                online = [m for m in members if str(m.status) != "offline"]
                if not online:
                    await message.answer(f"No online users in {guild.name}.")
                    return
                lines = [f"<b>{guild.name}</b>:"]
                for m in online:
                    activity = None
                    if m.activities:
                        a = m.activities[0]
                        activity = getattr(a, "name", None)
                        if getattr(a, "details", None):
                            activity += f" — {a.details}"
                    status = str(m.status)
                    if activity:
                        lines.append(f" • {m.display_name} — {status} — {activity}")
                    else:
                        lines.append(f" • {m.display_name} — {status}")
                await message.answer("\n".join(lines), parse_mode="HTML")
            except Exception as e:
                logger.error(f"/list failed: {e}")
                await message.answer("Failed to fetch online users.")

        @self._router.message(Command("play"))
        async def play_handler(message: Message):
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.answer("Usage: /play <query|url>")
                return
            query = args[1].strip()
            guild_id = await self._get_linked_guild_id(message.chat.id)
            if not guild_id:
                await message.answer(
                    "This chat isn't linked to a Discord server yet. In Discord, run /connect_telegram <chat_id> here and try again."
                )
                return
            try:
                await message.bot.send_chat_action(message.chat.id, "upload_voice")
                track = None
                if self._sp.is_supported_url(query):
                    track = await self._sp.get_track_info(query, message.from_user.id)
                elif self._yt.is_supported_url(query):
                    track = await self._yt.get_track_info(query, message.from_user.id)
                else:
                    results = await self._yt.search(query, max_results=1)
                    if results:
                        track = results[0]
                        track.requester_id = message.from_user.id
                if not track:
                    await message.answer("Couldn't find the track.")
                    return
                await self._ensure_voice(guild_id)
                voice_client = self._get_voice_client(guild_id)
                ok = await self._music_service().play(guild_id, track, voice_client)
                await message.answer(
                    "Added to queue." if ok else "Failed to queue track."
                )
            except Exception as e:
                logger.error(f"/play failed: {e}")
                await message.answer("Error while processing track.")

        @self._router.message(Command("queue"))
        async def queue_handler(message: Message):
            guild_id = await self._get_linked_guild_id(message.chat.id)
            if not guild_id:
                await message.answer(
                    "This chat isn't linked to a Discord server yet. Ask an admin to run /connect_telegram in Discord."
                )
                return
            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer(self._format_queue(guild_id))

        @self._router.message(Command("stop"))
        async def stop_handler(message: Message):
            guild_id = await self._get_linked_guild_id(message.chat.id)
            if not guild_id:
                await message.answer(
                    "This chat isn't linked to a Discord server yet. Ask an admin to run /connect_telegram in Discord."
                )
                return
            await message.bot.send_chat_action(message.chat.id, "upload_voice")
            ok = await self._music_service().stop(guild_id)
            # Also disconnect from voice like Discord's /stop does
            try:
                vc = self._get_voice_client(guild_id)
                if vc:
                    await vc.disconnect()
            except Exception as e:
                logger.error(
                    f"Failed to disconnect voice client for guild {guild_id}: {e}"
                )
            await message.answer("Stopped." if ok else "Nothing to stop.")

        @self._router.message(Command("volume"))
        async def volume_handler(message: Message):
            parts = message.text.split()
            if len(parts) < 2:
                await message.answer("Usage: /volume <0-100>")
                return
            try:
                vol = int(parts[1])
                if not 0 <= vol <= 100:
                    raise ValueError
            except ValueError:
                await message.answer("Volume must be 0-100")
                return
            guild_id = await self._get_linked_guild_id(message.chat.id)
            if not guild_id:
                await message.answer(
                    "This chat isn't linked to a Discord server yet. Ask an admin to run /connect_telegram in Discord."
                )
                return
            ok = await self._music_service().set_volume(guild_id, vol / 100.0)
            await message.answer("Volume set." if ok else "Failed to set volume.")

        @self._router.message(Command("id"))
        async def _(message: Message):
            await message.answer(
                f"user_id: {message.from_user.id}\n\nchat_id: {message.chat.id}"
            )

        # Cache members from any message to build @all mentions later
        @self._router.message()
        async def _cache_member(message: Message):
            try:
                u = message.from_user
                if not u:
                    return
                await self._member_repo.upsert_member(
                    chat_id=message.chat.id,
                    user_id=u.id,
                    is_bot=bool(u.is_bot),
                    username=u.username,
                    first_name=u.first_name,
                    last_name=u.last_name,
                )
                logger.info(f"Upserted telegram member: {u}")
            except Exception as e:
                logger.error(f"Failed to upsert telegram member: {e}")

    async def _set_bot_commands(self):
        if not self._bot:
            return
        commands = [
            BotCommand(command="list", description="List all users in the discord"),
            BotCommand(command="play", description="Play a song on Discord"),
            BotCommand(command="stop", description="Stop playback"),
            BotCommand(command="queue", description="Show the current playback queue"),
            BotCommand(command="volume", description="Set the playback volume"),
        ]
        await self._bot.set_my_commands(commands)

    async def send_message(
        self, chat_id: int, text: str, parse_mode: Optional[str] = None
    ) -> None:
        if not self._bot:
            raise RuntimeError("Telegram bot not started")
        if parse_mode:
            logger.debug(f"Sending message with parse_mode: {parse_mode}")
            await self._bot.send_message(chat_id, text, parse_mode=parse_mode)
        else:
            await self._bot.send_message(chat_id, text)

    async def check_bot_in_chat(self, chat_id: int) -> bool:
        if not self._bot:
            return False
        try:
            me = await self._bot.get_me()
            member = await self._bot.get_chat_member(chat_id, me.id)
            return member is not None
        except Exception:
            return False

    async def get_chat_administrators(self, chat_id: int):
        if not self._bot:
            return []
        try:
            return await self._bot.get_chat_administrators(chat_id)
        except Exception as e:
            logger.debug(f"get_chat_administrators failed for {chat_id}: {e}")
            return []

    # Helpers
    async def _get_linked_guild_id(self, chat_id: int) -> Optional[int]:
        try:
            link = await self._chat_repo.get_link_by_chat(chat_id)
            return link.guild_id if link else None
        except Exception as e:
            logger.error(f"Failed to resolve linked guild for chat {chat_id}: {e}")
            return None

    def _get_voice_client(self, guild_id: int):
        bot = self.container.get("Bot")
        guild = next((g for g in bot.guilds if g.id == guild_id), None)
        return guild.voice_client if guild else None

    def _format_queue(self, guild_id: int) -> str:
        playlist = self._music_service().get_playlist(guild_id)
        if not playlist or not playlist.tracks:
            return "Queue is empty."
        lines = []
        for idx, t in enumerate(playlist.tracks, start=1):
            prefix = "▶️" if idx - 1 == playlist.current_index else f"{idx}."
            lines.append(f"{prefix} {t.display_title}")
        return "\n".join(lines)

    def _music_service(self) -> MusicService:
        if self._music is None:
            self._music = self.container.get(MusicService)
        return self._music

    async def _ensure_voice(self, guild_id: int) -> None:
        """Ensure the bot is connected to some voice channel in the guild."""
        bot = self.container.get("Bot")
        guild = next((g for g in bot.guilds if g.id == guild_id), None)
        if not guild:
            return
        if guild.voice_client and guild.voice_client.is_connected():
            return
        # Pick the most populated voice channel or any
        candidates = getattr(guild, "voice_channels", [])
        if not candidates:
            return
        channel = max(candidates, key=lambda c: len(getattr(c, "members", []) or []))
        try:
            await channel.connect()
        except Exception as e:
            logger.error(f"Failed to connect to voice channel in guild {guild_id}: {e}")

    # Event subscriptions and handlers
    def _subscribe_events(self) -> None:
        """Subscribe to music and status events to forward updates to Telegram."""
        self._event_bus.subscribe(Events.TRACK_STARTED, self._on_track_started)
        self._event_bus.subscribe(Events.TRACK_SKIPPED, self._on_track_skipped)
        self._event_bus.subscribe(Events.TRACK_ENDED, self._on_track_ended)
        # String-based events from MusicService
        self._event_bus.subscribe("playback_stopped", self._on_playback_stopped)
        self._event_bus.subscribe("queue_finished", self._on_queue_finished)
        self._event_bus.subscribe("volume_changed", self._on_volume_changed)
        self._event_bus.subscribe("playback_paused", self._on_playback_paused)
        self._event_bus.subscribe("playback_resumed", self._on_playback_resumed)
        self._event_bus.subscribe("track_age_restricted_notification", self._on_track_age_restricted)

    async def _send_if_linked(self, guild_id: int, text: str) -> None:
        try:
            link = await self._chat_repo.get_link_by_guild(guild_id)
            if link and self._bot:
                await self.send_message(link.telegram_chat_id, text)
        except Exception as e:
            logger.error(
                f"Failed to forward event to Telegram for guild {guild_id}: {e}"
            )

    # Event handlers
    async def _on_track_started(self, guild_id: int, track) -> None:
        title = getattr(track, "display_title", getattr(track, "title", "Track"))
        duration = getattr(track, "duration_formatted", None)
        src = getattr(getattr(track, "source", None), "value", None)
        parts = ["▶️ Now playing:", f"{title}"]
        if duration:
            parts.append(f"[{duration}]")
        if src:
            parts.append(f"• {src.title()}")
        await self._send_if_linked(guild_id, " ".join(parts))

    async def _on_track_skipped(self, guild_id: int, track) -> None:
        title = getattr(track, "display_title", getattr(track, "title", "Track"))
        await self._send_if_linked(guild_id, f"⏭️ Skipped: {title}")

    async def _on_track_ended(self, guild_id: int, track) -> None:
        title = getattr(track, "display_title", getattr(track, "title", "Track"))
        await self._send_if_linked(guild_id, f"🏁 Finished: {title}")

    async def _on_playback_stopped(self, guild_id: int) -> None:
        await self._send_if_linked(guild_id, "⏹️ Playback stopped and queue cleared.")

    async def _on_queue_finished(self, guild_id: int) -> None:
        await self._send_if_linked(guild_id, "📭 Queue finished.")

    async def _on_volume_changed(self, guild_id: int, volume: float) -> None:
        pct = int(round(volume * 100))
        await self._send_if_linked(guild_id, f"🔊 Volume set to {pct}%")

    async def _on_playback_paused(self, guild_id: int) -> None:
        await self._send_if_linked(guild_id, "⏸️ Paused.")

    async def _on_playback_resumed(self, guild_id: int) -> None:
        await self._send_if_linked(guild_id, "▶️ Resumed.")
    
    async def _on_track_age_restricted(self, guild_id: int, track, url: str, reason: str) -> None:
        title = getattr(track, "display_title", getattr(track, "title", "Track"))
        await self._send_if_linked(guild_id, f"🔞 Age-restricted: {title}\n🔗 {url}\n⏭️ Skipping to next track...")
