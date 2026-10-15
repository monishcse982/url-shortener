import base64
import hashlib
import hmac
import json
import logging
import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from tortoise.exceptions import IntegrityError

from app.core.config import settings
from app.core.exceptions import (
    ApplicationError,
    ResourceGoneError,
    ResourceNotFoundError,
    ShortCodeConflictError,
    UnauthorizedError,
)
from app.core.metrics import (
    short_link_access_request_count,
    short_links_create_duration_seconds,
    short_links_created,
    short_links_creation_error,
    short_links_creation_requests,
    time_limited_link_cache_hits,
    time_limited_link_cache_misses,
)
from app.db.models.links import Link
from app.db.repositories.links import LinksRepository
from app.kafka.events import LinkVisitedEvent, event_to_bytes
from app.kafka.producer import KafkaProducer
from app.kafka.topics import LINK_VISITED_TOPIC
from app.schemas.links import ShortenRequest, ShortenResponse

logger = logging.getLogger(__name__)


class LinksService:
    def __init__(
        self,
        links_repository: LinksRepository,
        kafka_producer: KafkaProducer,
        cache: Redis,
    ):
        self.links_repository = links_repository
        self.kafka_producer = kafka_producer
        self.cache = cache

    async def shorten_url(self, request: ShortenRequest) -> ShortenResponse:
        short_links_creation_requests.inc()
        with short_links_create_duration_seconds.time():
            try:
                expires_at = datetime.now(UTC) + timedelta(seconds=request.ttl_seconds)
                policy_config = request.policy.model_dump(
                    mode="json",
                    exclude={"password"},
                    exclude_none=True,
                )

                if request.policy.password is not None:
                    policy_config["password"] = self._hash_password(
                        request.policy.password
                    )

                # Retry only generated codes: a caller-supplied code collision is
                # deterministic and should be reported as a client conflict.
                attempts = 5 if request.short_code is None else 1
                for attempt in range(attempts):
                    short_code = request.short_code or self._generate_code()
                    logger.info(f"Creating short link short_code={short_code}")
                    try:
                        link = await self.links_repository.create(
                            short_code=short_code,
                            original_url=str(request.url),
                            title=request.title,
                            max_visits=request.max_visits,
                            expires_at=expires_at,
                            policy=policy_config,
                        )
                        break
                    except IntegrityError:
                        if request.short_code is not None:
                            raise ShortCodeConflictError(short_code) from None
                        if attempt == attempts - 1:
                            raise ApplicationError(
                                "Could not generate a unique short code"
                            ) from None

                logger.info(
                    "Short link created link_id=%s short_code=%s",
                    link.id,
                    link.short_code,
                )
                short_links_created.inc()

                return ShortenResponse(
                    shortened_url=f"{settings.base_url}/link/{link.short_code}",
                    expires_at=link.expires_at,
                )

            except ApplicationError as error:
                short_links_creation_error.labels(
                    error_type=type(error).__name__,
                ).inc()
                raise

            except Exception as error:
                error_type = type(error).__name__

                short_links_creation_error.labels(
                    error_type=error_type,
                ).inc()

                logger.exception(
                    "Short link creation failed short_code=%s",
                    request.short_code,
                )

                raise ApplicationError(
                    "Short link creation failed",
                    details={"error_type": error_type},
                ) from error

    async def get_url(
        self,
        short_code: str,
        *,
        password: str | None,
        user_agent: str | None,
        referrer: str | None,
        ip_address: str | None,
    ) -> str:
        short_link_access_request_count.inc()
        link, resolved_from_cache = await self._resolve_link(short_code)
        await self._ensure_link_can_be_visited(link)
        await self._admit_visit_if_limited(link)
        stored_password = link.policy.get("password")
        if stored_password is not None:
            if password is None:
                raise UnauthorizedError(
                    message=f"Password required for short link short_code={short_code}"
                ) from None
            if not self._verify_password(password, stored_password):
                raise UnauthorizedError(
                    message=f"Invalid password for short link short_code={short_code}"
                ) from None

        if not resolved_from_cache and stored_password is None:
            await self._cache_if_eligible(link)

        self._publish_visit_event(
            link=link,
            user_agent=user_agent,
            referrer=referrer,
            ip_address=ip_address,
        )

        self._record_cache_resolution(link, resolved_from_cache)
        return str(link.original_url)

    async def _resolve_link(self, short_code: str) -> tuple[Link, bool]:
        cached_link = await self.get_cached_link(short_code)
        if cached_link is not None:
            logger.debug("Short link cache hit short_code=%s", short_code)
            return cached_link, True

        logger.debug("Short link cache miss short_code=%s", short_code)
        link = await self._get_existing_link(short_code)
        return link, False

    async def _cache_if_eligible(self, link: Link) -> None:
        if link.max_visits is not None:
            return

        remaining_ttl = int((link.expires_at - datetime.now(UTC)).total_seconds())
        if remaining_ttl <= 0:
            return

        await self.cache_link(
            short_code=str(link.short_code),
            link=link,
            ttl_seconds=min(settings.cache_ttl, remaining_ttl),
        )

    async def _admit_visit_if_limited(self, link: Link) -> None:
        if link.max_visits is None:
            return

        admitted_link = await self.links_repository.increment_visit_count(
            link_id=int(link.id),
        )
        if admitted_link is None:
            logger.info(
                "Short link admission rejected link_id=%s short_code=%s",
                link.id,
                link.short_code,
            )
            raise ResourceGoneError(
                resource="Short link",
                identifier=str(link.short_code),
                reason="Link visit limit reached",
                code="link_visit_limit_reached",
            )

        link.visit_count = admitted_link.visit_count

    def _publish_visit_event(
        self,
        *,
        link: Link,
        user_agent: str | None,
        referrer: str | None,
        ip_address: str | None,
    ) -> None:
        logger.info(
            "Publishing visit event link_id=%s short_code=%s", link.id, link.short_code
        )
        event = LinkVisitedEvent(
            link_id=int(link.id),
            short_code=link.short_code,
            visited_at=datetime.now(UTC),
            user_agent=user_agent,
            referrer=referrer,
            ip_address=ip_address,
        )

        self.kafka_producer.publish(
            topic=LINK_VISITED_TOPIC,
            key=str(link.short_code),
            value=event_to_bytes(event=event),
        )

    async def _get_existing_link(self, short_code: str) -> Link:
        link = await self.links_repository.find_active_by_short_code(short_code)

        if link is None:
            logger.warning("Short link not found short_code=%s", short_code)
            raise ResourceNotFoundError(
                resource="Short link",
                identifier=short_code,
            )

        return link

    async def _ensure_link_can_be_visited(self, link: Link) -> None:
        if self._is_expired(link):
            await self._soft_delete_link(link)
            logger.info(
                "Short link expired link_id=%s short_code=%s", link.id, link.short_code
            )
            raise ResourceGoneError(
                resource="Short link",
                identifier=str(link.short_code),
                reason="Link expired",
                code="link_expired",
            )

        if self._has_reached_visit_limit(link):
            await self._soft_delete_link(link)
            logger.info(
                "Short link visit limit reached link_id=%s short_code=%s"
                "visit_count=%s max_visits=%s",
                link.id,
                link.short_code,
                link.visit_count,
                link.max_visits,
            )
            raise ResourceGoneError(
                resource="Short link",
                identifier=str(link.short_code),
                reason="Link visit limit reached",
                code="link_visit_limit_reached",
            )

    async def cache_link(
        self,
        *,
        short_code: str,
        link: Link,
        ttl_seconds: int,
    ) -> None:
        await self.cache.set(
            self._cache_key(short_code),
            json.dumps(self._link_to_cache_payload(link)),
            ex=ttl_seconds,
        )
        logger.debug("Short link cached short_code=%s ttl=%s", short_code, ttl_seconds)

    async def invalidate_cached_link(self, short_code: str) -> None:
        await self.cache.delete(self._cache_key(short_code))

    async def get_cached_link(self, short_code: str) -> Link | None:
        value = await self.cache.get(self._cache_key(short_code))
        if value is None:
            return None

        try:
            payload: dict[str, Any] = json.loads(value)
            return self._link_from_cache_payload(payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.exception("Invalid cached short link short_code=%s", short_code)
            await self.invalidate_cached_link(short_code)
            return None

    async def disable_shortened_url(self, short_code: str) -> None:
        logger.info("Disabling short link short_code=%s", short_code)
        link = await self.links_repository.soft_delete_by_short_code(
            short_code=short_code,
        )

        if link is None:
            raise ResourceNotFoundError(
                resource="Active short link",
                identifier=short_code,
            )

        await self.invalidate_cached_link(short_code)
        logger.info(
            "Short link disabled link_id=%s short_code=%s",
            link.id,
            link.short_code,
        )

    async def _soft_delete_link(self, link: Link) -> None:
        await self.links_repository.soft_delete_by_short_code(
            short_code=str(link.short_code),
        )
        await self.invalidate_cached_link(link.short_code)
        logger.info(
            "Short link soft deleted link_id=%s short_code=%s", link.id, link.short_code
        )

    @staticmethod
    def _is_expired(link: Link) -> bool:
        return link.expires_at < datetime.now(UTC)

    @staticmethod
    def _has_reached_visit_limit(link: Link) -> bool:
        return link.max_visits is not None and link.visit_count >= link.max_visits

    @staticmethod
    def _record_cache_resolution(link: Link, resolved_from_cache: bool) -> None:
        if link.max_visits is not None:
            return

        if resolved_from_cache:
            time_limited_link_cache_hits.inc()
            return

        time_limited_link_cache_misses.inc()

    @staticmethod
    def _cache_key(short_code: str) -> str:
        return f"link:{short_code}"

    @staticmethod
    def _link_to_cache_payload(link: Link) -> dict[str, object]:
        return {
            "id": int(link.id),
            "short_code": str(link.short_code),
            "original_url": str(link.original_url),
            "title": link.title,
            "max_visits": link.max_visits,
            "is_deleted": bool(link.is_deleted),
            "created_at": link.created_at.isoformat(),
            "expires_at": link.expires_at.isoformat(),
            "visit_count": int(link.visit_count),
        }

    @staticmethod
    def _link_from_cache_payload(payload: dict[str, Any]) -> Link:
        return Link(
            id=int(payload["id"]),
            short_code=str(payload["short_code"]),
            original_url=str(payload["original_url"]),
            title=payload.get("title"),
            max_visits=payload.get("max_visits"),
            is_deleted=bool(payload["is_deleted"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            visit_count=int(payload["visit_count"]),
        )

    @staticmethod
    def _generate_code(length: int = 8) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return "$".join(
            (
                "scrypt",
                base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
                base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
            )
        )

    @staticmethod
    def _verify_password(password: str, stored: str) -> bool:
        algorithm, salt_b64, digest_b64 = stored.split("$")
        if algorithm != "scrypt":
            return False

        def decode(value: str) -> bytes:
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

        salt = decode(salt_b64)
        expected = decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
