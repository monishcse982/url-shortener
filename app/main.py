import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis
from tortoise import Tortoise

from app.api.exception_handlers import register_exception_handlers
from app.api.routes.links import router as links_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import close_db, init_db
from app.kafka.consumers.visit_consumer import consume_visits, stop_consumer
from app.kafka.producer import kafka_producer

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    cache = Redis.from_url(
        settings.cache_url,
        decode_responses=True,
    )
    consumer_task: asyncio.Task[None] | None = None

    try:
        await cache.ping()
        app.state.cache = cache
        consumer_task = asyncio.create_task(consume_visits())
        yield
    finally:
        stop_consumer()
        if consumer_task is not None:
            await consumer_task
        await cache.aclose()
        await close_db()
        kafka_producer.flush()


app = FastAPI(lifespan=lifespan)


@app.get("/ready", include_in_schema=False)
async def ready() -> dict[str, str]:
    expected = {
        path.stem for path in (Path(__file__).parent / "migrations").glob("[0-9]*.py")
    }
    try:
        rows = await Tortoise.get_connection("default").execute_query_dict(
            "SELECT name FROM tortoise_migrations WHERE app = 'models'"
        )
    except Exception as error:
        raise HTTPException(
            status_code=503, detail="Database migration pending"
        ) from error
    if not expected.issubset({row["name"] for row in rows}):
        raise HTTPException(status_code=503, detail="Database migration pending")
    return {"status": "ready"}


register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
    ],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)
app.add_middleware(
    CorrelationIdMiddleware,
    header_name="X-Correlation-ID",
)
app.include_router(links_router)

Instrumentator().instrument(app).expose(
    app,
    endpoint="/metrics",
    include_in_schema=False,
)
