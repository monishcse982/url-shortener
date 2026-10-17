import unittest
from datetime import UTC, datetime, timedelta

from tortoise import Tortoise

from app.db.models.links import Link
from app.db.repositories.links import LinksRepository
from app.db.repositories.visits import VisitsRepository


class RepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": ["app.db.models"]},
            use_tz=True,
            timezone="UTC",
        )
        await Tortoise.generate_schemas()

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def create_link(
        self,
        *,
        short_code="example-code",
        expires_at=None,
        max_visits=None,
        policy=None,
        owner_sub="user-1",
    ):
        return await LinksRepository.create(
            short_code=short_code,
            original_url="https://example.com/target",
            expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
            title=None,
            max_visits=max_visits,
            policy=policy or {"type": "public"},
            owner_sub=owner_sub,
        )

    async def test_create_and_lookup_only_return_active_link(self):
        created = await self.create_link()

        self.assertTrue(await LinksRepository.short_code_exists("example-code"))
        found = await LinksRepository.find_active_by_short_code("example-code")
        self.assertEqual(found.id, created.id)
        self.assertEqual(found.original_url, "https://example.com/target")

        await Link.filter(id=created.id).update(is_deleted=True)
        self.assertIsNone(
            await LinksRepository.find_active_by_short_code("example-code")
        )
        self.assertTrue(await LinksRepository.short_code_exists("example-code"))

    async def test_soft_delete_is_idempotent_and_preserves_link_row(self):
        created = await self.create_link()

        deleted = await LinksRepository.soft_delete_by_short_code("example-code")
        repeated = await LinksRepository.soft_delete_by_short_code("example-code")

        self.assertEqual(deleted.id, created.id)
        self.assertTrue(deleted.is_deleted)
        self.assertIsNone(repeated)
        self.assertEqual(await Link.all().count(), 1)

    async def test_increment_visit_count_admits_only_within_limit(self):
        link = await self.create_link(max_visits=2)

        first = await LinksRepository.increment_visit_count(link.id)
        second = await LinksRepository.increment_visit_count(link.id)
        third = await LinksRepository.increment_visit_count(link.id)

        self.assertEqual(first.visit_count, 1)
        self.assertEqual(second.visit_count, 2)
        self.assertIsNone(third)

    async def test_increment_visit_count_rejects_unlimited_expired_and_deleted(self):
        unlimited = await self.create_link(short_code="unlimited-code")
        expired = await self.create_link(
            short_code="expired-code",
            max_visits=2,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        deleted = await self.create_link(short_code="deleted-code", max_visits=2)
        await Link.filter(id=deleted.id).update(is_deleted=True)

        self.assertIsNone(await LinksRepository.increment_visit_count(unlimited.id))
        self.assertIsNone(await LinksRepository.increment_visit_count(expired.id))
        self.assertIsNone(await LinksRepository.increment_visit_count(deleted.id))

    async def test_visit_repository_persists_visit_metadata(self):
        link = await self.create_link()

        visit = await VisitsRepository.create(
            link_id=link.id,
            user_agent="unit-test-agent",
            referrer="https://example.com/referrer",
            ip_address="192.0.2.5",
        )

        self.assertEqual(visit.link_id, link.id)
        self.assertEqual(visit.user_agent, "unit-test-agent")
        self.assertEqual(visit.referrer, "https://example.com/referrer")
        self.assertEqual(visit.ip_address, "192.0.2.5")
        self.assertIsNotNone(visit.visited_at)

    async def test_management_mutations_are_owner_scoped(self):
        own = await self.create_link(owner_sub="user-1")
        other = await self.create_link(short_code="other-code", owner_sub="user-2")

        links, total = await LinksRepository.list_by_owner(
            "user-1", limit=100, offset=0
        )
        self.assertEqual(total, 1)
        self.assertEqual([link.id for link in links], [own.id])
        self.assertIsNone(
            await LinksRepository.update_destination(
                "other-code", "user-1", "https://wrong.example"
            )
        )
        self.assertIsNone(
            await LinksRepository.soft_delete_owned("other-code", "user-1")
        )
        self.assertEqual(
            (await LinksRepository.find_by_short_code("other-code")).id, other.id
        )

        changed = await LinksRepository.update_destination(
            "example-code", "user-1", "https://new.example"
        )
        self.assertEqual(changed.original_url, "https://new.example")
        deleted = await LinksRepository.soft_delete_owned("example-code", "user-1")
        self.assertTrue(deleted.is_deleted)
