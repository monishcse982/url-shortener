import logging

from app.db.models.visits import Visit

logger = logging.getLogger(__name__)


class VisitsRepository:
    @staticmethod
    async def create(
        *,
        link_id: int,
        user_agent: str | None,
        referrer: str | None,
        ip_address: str | None,
    ) -> Visit:
        visit = await Visit.create(
            link_id=link_id,
            user_agent=user_agent,
            referrer=referrer,
            ip_address=ip_address,
        )

        logger.info(f"Visit row created visit_id={visit.id}")
        return visit
