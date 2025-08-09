import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine: Optional[object] = None
        self.session_factory: Optional[async_sessionmaker] = None

    async def initialize(self) -> None:
        """Initialize the database engine and session factory."""
        try:
            # Convert sqlite URL for async support
            if self.database_url.startswith("sqlite://"):
                self.database_url = self.database_url.replace(
                    "sqlite://", "sqlite+aiosqlite://"
                )

            self.engine = create_async_engine(
                self.database_url, echo=False, future=True
            )

            self.session_factory = async_sessionmaker(
                bind=self.engine, class_=AsyncSession, expire_on_commit=False
            )

            # Create all tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def get_session(self) -> AsyncSession:
        """Get a new database session."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        return self.session_factory()

    async def close(self) -> None:
        """Close the database connection."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")
