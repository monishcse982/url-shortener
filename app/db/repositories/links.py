import logging
from datetime import UTC, datetime

from tortoise.expressions import F
from tortoise.transactions import in_transaction

from app.db.models.links import Link

logger = logging.getLogger(__name__)


class LinksRepository:
    @staticmethod
    async def short_code_exists(short_code: str) -> bool:
        return await Link.filter(short_code=short_code).exists()

    @staticmethod
    async def find_active_by_short_code(short_code: str) -> Link | None:
        return await Link.get_or_none(short_code=short_code, is_deleted=False)

    @staticmethod
    async def soft_delete_by_short_code(
        short_code: str,
    ) -> Link | None:
        async with in_transaction() as connection:
            link = await (
                Link.filter(short_code=short_code, is_deleted=False)
                .using_db(connection)
                .select_for_update()
                .first()
            )
            if link is not None:
                await (
                    Link.filter(id=link.id).using_db(connection).update(is_deleted=True)
                )
                link.is_deleted = True

        if link is None:
            logger.warning(
                "Soft delete skipped: active link not found short_code=%s", short_code
            )
        else:
            logger.info(
                "Link soft deleted link_id=%s short_code=%s", link.id, link.short_code
            )

        return link

    @staticmethod
    async def increment_visit_count(
        link_id: int,
    ) -> Link | None:
        async with in_transaction() as connection:
            updated = await (
                Link.filter(
                    id=link_id,
                    is_deleted=False,
                    max_visits__not_isnull=True,
                    visit_count__lt=F("max_visits"),
                    expires_at__gt=datetime.now(UTC),
                )
                .using_db(connection)
                .update(visit_count=F("visit_count") + 1)
            )
            link = (
                await Link.filter(id=link_id).using_db(connection).first()
                if updated
                else None
            )
        if link is None:
            logger.warning(
                "Visit count increment skipped: active link not found link_id=%s",
                link_id,
            )
        else:
            logger.info(
                "Visit count incremented link_id=%s visit_count=%s",
                link.id,
                link.visit_count,
            )

        return link

    @staticmethod
    async def create(
        short_code: str,
        original_url: str,
        expires_at: datetime,
        title: str | None,
        policy: dict[str, object],
        max_visits: int | None = None,
    ) -> Link:
        link = await Link.create(
            short_code=short_code,
            original_url=original_url,
            title=title,
            max_visits=max_visits,
            expires_at=expires_at,
            policy=policy,
        )

        logger.info(
            "Link row created link_id=%s short_code=%s", link.id, link.short_code
        )
        return link
