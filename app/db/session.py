from tortoise import Tortoise

from app.core.config import settings, tortoise_database_url


async def init_db() -> None:
    await Tortoise.init(
        db_url=tortoise_database_url(settings.database_url),
        modules={"models": ["app.db.models"]},
        use_tz=True,
        timezone="UTC",
        _enable_global_fallback=True,
    )


async def close_db() -> None:
    await Tortoise.close_connections()
