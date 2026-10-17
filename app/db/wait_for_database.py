"""Wait for PostgreSQL before a fresh Helm install runs migrations."""

import asyncio
import time

import asyncpg

from app.core.config import settings, tortoise_database_url


async def main() -> None:
    deadline = time.monotonic() + 180
    print("Waiting for PostgreSQL", flush=True)
    while time.monotonic() < deadline:
        try:
            connection = await asyncio.wait_for(
                asyncpg.connect(tortoise_database_url(settings.migration_database_url)),
                timeout=5,
            )
        except (OSError, asyncpg.PostgresError, TimeoutError):
            await asyncio.sleep(2)
        else:
            await connection.close()
            print("PostgreSQL is ready", flush=True)
            return
    raise SystemExit("PostgreSQL did not become ready before the migration deadline")


if __name__ == "__main__":
    asyncio.run(main())
