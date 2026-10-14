import asyncio
from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis

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
register_exception_handlers(app)
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
