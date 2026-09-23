from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings


def normalize_database_url(raw_url: str) -> str:
    """Convert Neon/PostgreSQL URLs to SQLAlchemy's asyncpg format."""
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url.removeprefix("postgres://")
    if raw_url.startswith("postgresql://"):
        raw_url = "postgresql+asyncpg://" + raw_url.removeprefix("postgresql://")

    if raw_url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(raw_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        # asyncpg uses `ssl`; Neon commonly supplies libpq's `sslmode`.
        if query.pop("sslmode", None):
            query["ssl"] = "require"
        query.pop("channel_binding", None)
        raw_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return raw_url


settings = get_settings()
engine = create_async_engine(
    normalize_database_url(settings.database_url),
    pool_pre_ping=True,
    echo=settings.app_env == "debug",
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

