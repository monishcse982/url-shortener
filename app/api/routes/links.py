import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from starlette import status

from app.db.repositories.links import LinksRepository
from app.db.repositories.visits import VisitsRepository
from app.kafka.producer import KafkaProducer, kafka_producer
from app.schemas.links import ShortenRequest, ShortenResponse
from app.services.links import LinksService

router = APIRouter(tags=["shorten-requests"])
logger = logging.getLogger(__name__)


def get_links_repository() -> LinksRepository:
    return LinksRepository()


def get_kafka_producer() -> KafkaProducer:
    return kafka_producer


def get_visits_repository() -> VisitsRepository:
    return VisitsRepository()


def get_cache(request: Request) -> Redis:
    return request.app.state.cache


def get_links_service(
    links_repository: LinksRepository = Depends(get_links_repository),
    producer: KafkaProducer = Depends(get_kafka_producer),
    cache: Redis = Depends(get_cache),
) -> LinksService:
    return LinksService(links_repository, producer, cache)


@router.post("/link/", response_model=ShortenResponse)
async def shorten_url(
    request: ShortenRequest,
    links_service: LinksService = Depends(get_links_service),
) -> ShortenResponse:
    logger.info("Shorten request received")
    return await links_service.shorten_url(request)


@router.get("/link/{short_code}")
async def redirect_to_url(
    short_code: str,
    request: Request,
    links_service: LinksService = Depends(get_links_service),
) -> RedirectResponse:
    logger.info("Redirect request received short_code=%s", short_code)
    original_url = await links_service.get_url(
        short_code,
        password=request.headers.get("password"),
        user_agent=request.headers.get("user-agent"),
        referrer=request.headers.get("referer"),
        ip_address=request.client.host if request.client else None,
    )

    return RedirectResponse(url=original_url, status_code=302)


@router.get("/dummy-target")
async def dummy_target() -> dict[str, str]:
    return {"status": "ok"}


@router.delete(
    "/link/{short_code}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disable_shortened_url(
    short_code: str,
    links_service: LinksService = Depends(get_links_service),
) -> None:
    await links_service.disable_shortened_url(short_code)
