from datetime import datetime
from typing import List

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from config.database import Base


class User(Base):
    """User model for Discord users."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    settings: Mapped["UserSettings"] = relationship(
        "UserSettings", back_populates="user", uselist=False
    )
    history: Mapped[List["UserHistory"]] = relationship(
        "UserHistory", back_populates="user", order_by="desc(UserHistory.played_at)"
    )


class UserSettings(Base):
    """User settings and preferences."""

    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), primary_key=True
    )
    default_volume: Mapped[float] = mapped_column(Float, default=0.5)
    preferred_filters: Mapped[List[str]] = mapped_column(JSON, default=list)
    auto_play: Mapped[bool] = mapped_column(Boolean, default=False)
    repeat_mode: Mapped[str] = mapped_column(String(20), default="off")
    bass_boost_level: Mapped[int] = mapped_column(Integer, default=0)
    custom_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="settings")


class UserHistory(Base):
    """User listening history."""

    __tablename__ = "user_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    track_title: Mapped[str] = mapped_column(String(500))
    track_url: Mapped[str] = mapped_column(Text, nullable=True)
    track_duration: Mapped[int] = mapped_column(Integer, nullable=True)
    artist: Mapped[str] = mapped_column(String(200), nullable=True)
    album: Mapped[str] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(50))
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)
    track_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    played_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="history")


class GuildSettings(Base):
    """Guild/Server specific settings."""

    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    max_queue_size: Mapped[int] = mapped_column(Integer, default=100)
    default_volume: Mapped[float] = mapped_column(Float, default=0.5)
    allowed_filters: Mapped[List[str]] = mapped_column(
        JSON, default=lambda: ["bass_boost", "reverb", "slow", "8d"]
    )
    command_prefix: Mapped[str] = mapped_column(String(10), default="/")
    auto_disconnect_timeout: Mapped[int] = mapped_column(
        Integer, default=300
    )  # 5 minutes
    max_track_duration: Mapped[int] = mapped_column(Integer, default=3600)  # 1 hour
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PlaybackSession(Base):
    """Playback session tracking for analytics."""

    __tablename__ = "playback_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    track_title: Mapped[str] = mapped_column(String(500))
    track_url: Mapped[str] = mapped_column(Text)
    duration_played: Mapped[int] = mapped_column(Integer)  # Seconds actually played
    total_duration: Mapped[int] = mapped_column(Integer)  # Total track duration
    completion_percentage: Mapped[float] = mapped_column(Float)
    filters_applied: Mapped[List[str]] = mapped_column(JSON, default=list)
    volume_level: Mapped[float] = mapped_column(Float)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class TelegramChatLink(Base):
    """Mapping between a Discord guild and a Telegram chat/channel."""

    __tablename__ = "telegram_chat_links"
    __table_args__ = (UniqueConstraint("telegram_chat_id", name="uq_telegram_chat_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class TelegramChatMember(Base):
    """Known Telegram chat members for building @all mentions."""

    __tablename__ = "telegram_chat_members"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_chat_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )
