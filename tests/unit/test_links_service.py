import json
import unittest
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from tortoise.exceptions import IntegrityError

from app.core.exceptions import (
    ApplicationError,
    ResourceGoneError,
    ResourceNotFoundError,
    ShortCodeConflictError,
    UnauthorizedError,
)
from app.schemas.links import ShortenRequest

with patch("confluent_kafka.Producer"):
    from app.services.links import LinksService


def make_link(**overrides):
    values = {
        "id": 42,
        "short_code": "example-code",
        "original_url": "https://example.com/target",
        "title": None,
        "max_visits": None,
        "is_deleted": False,
        "created_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "visit_count": 0,
        "policy": {"type": "public"},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_service(link=None):
    repository = SimpleNamespace(
        create=AsyncMock(return_value=link),
        find_active_by_short_code=AsyncMock(return_value=link),
        increment_visit_count=AsyncMock(return_value=link),
        soft_delete_by_short_code=AsyncMock(return_value=link),
    )
    producer = MagicMock()
    cache = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(),
        delete=AsyncMock(),
    )
    return LinksService(repository, producer, cache), repository, producer, cache


async def visit(service, *, password=None, ip_address="127.0.0.1"):
    return await service.get_url(
        "example-code",
        password=password,
        user_agent="unit-test-agent",
        referrer="https://example.com/referrer",
        ip_address=ip_address,
    )


class ShortenUrlTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_supplied_code_creates_successfully_without_retry(self):
        link = make_link(short_code="my-code")
        service, repository, _, _ = make_service(link)
        repository.create.return_value = link
        request = ShortenRequest.model_validate(
            {
                "url": "https://example.com/target",
                "ttl_seconds": 60,
                "short_code": "my-code",
            }
        )

        response = await service.shorten_url(request)

        self.assertTrue(response.shortened_url.endswith("/my-code"))
        repository.create.assert_awaited_once()

    async def test_custom_code_collision_returns_bad_request_without_retry(self):
        service, repository, _, _ = make_service(make_link())
        repository.create.side_effect = IntegrityError("duplicate")
        request = ShortenRequest.model_validate(
            {
                "url": "https://example.com/target",
                "ttl_seconds": 60,
                "short_code": "example-code",
            }
        )

        with self.assertRaises(ShortCodeConflictError) as raised:
            await service.shorten_url(request)

        self.assertEqual(raised.exception.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(raised.exception.details, {"short_code": "example-code"})
        self.assertEqual(repository.create.await_count, 1)

    async def test_generated_code_collision_uses_new_code(self):
        service, repository, _, _ = make_service(make_link(short_code="second123"))
        repository.create.side_effect = [
            IntegrityError("duplicate"),
            make_link(short_code="second123"),
        ]
        request = ShortenRequest.model_validate(
            {"url": "https://example.com/target", "ttl_seconds": 60}
        )

        with patch.object(
            service, "_generate_code", side_effect=["first123", "second123"]
        ):
            response = await service.shorten_url(request)

        self.assertEqual(repository.create.await_count, 2)
        self.assertEqual(
            repository.create.await_args_list[0].kwargs["short_code"], "first123"
        )
        self.assertEqual(
            repository.create.await_args_list[1].kwargs["short_code"], "second123"
        )
        self.assertTrue(response.shortened_url.endswith("/second123"))

    async def test_generated_code_success_on_first_attempt(self):
        service, repository, _, _ = make_service(make_link(short_code="generated1"))
        request = ShortenRequest.model_validate(
            {"url": "https://example.com/target", "ttl_seconds": 60}
        )

        with patch.object(service, "_generate_code", return_value="generated1"):
            response = await service.shorten_url(request)

        repository.create.assert_awaited_once()
        self.assertEqual(
            repository.create.await_args.kwargs["short_code"], "generated1"
        )
        self.assertTrue(response.shortened_url.endswith("/generated1"))

    async def test_generated_code_exhaustion_raises_application_error(self):
        service, repository, _, _ = make_service()
        repository.create.side_effect = IntegrityError("duplicate")
        request = ShortenRequest.model_validate(
            {"url": "https://example.com/target", "ttl_seconds": 60}
        )

        with self.assertRaisesRegex(
            ApplicationError, "Could not generate a unique short code"
        ):
            await service.shorten_url(request)

        self.assertEqual(repository.create.await_count, 5)

    async def test_unexpected_persistence_error_is_wrapped(self):
        service, repository, _, _ = make_service()
        repository.create.side_effect = RuntimeError("database unavailable")
        request = ShortenRequest.model_validate(
            {"url": "https://example.com/target", "ttl_seconds": 60}
        )

        with (
            patch("app.services.links.logger.exception"),
            self.assertRaises(ApplicationError) as raised,
        ):
            await service.shorten_url(request)

        self.assertEqual(raised.exception.details, {"error_type": "RuntimeError"})
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)


class VisitTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_link_publishes_visit_and_caches_with_bounded_ttl(self):
        link = make_link(expires_at=datetime.now(UTC) + timedelta(seconds=30))
        service, repository, producer, cache = make_service(link)

        result = await visit(service)

        self.assertEqual(result, link.original_url)
        repository.find_active_by_short_code.assert_awaited_once_with("example-code")
        repository.increment_visit_count.assert_not_awaited()
        cache.set.assert_awaited_once()
        self.assertEqual(cache.set.await_args.args[0], "link:example-code")
        self.assertGreater(cache.set.await_args.kwargs["ex"], 0)
        self.assertLessEqual(cache.set.await_args.kwargs["ex"], 30)
        self.assertEqual(producer.publish.call_count, 1)
        event = json.loads(producer.publish.call_args.kwargs["value"])
        self.assertEqual(event["link_id"], 42)
        self.assertEqual(event["user_agent"], "unit-test-agent")
        self.assertEqual(event["ip_address"], "127.0.0.1")

    async def test_cache_ttl_obeys_configured_cap(self):
        link = make_link(expires_at=datetime.now(UTC) + timedelta(seconds=30))
        service, _, _, cache = make_service(link)

        with patch("app.services.links.settings.cache_ttl", 5):
            await visit(service)

        self.assertEqual(cache.set.await_args.kwargs["ex"], 5)

    async def test_cached_public_link_uses_cache_without_repository_lookup(self):
        link = make_link()
        service, repository, producer, cache = make_service(link)
        cache.get.return_value = json.dumps(service._link_to_cache_payload(link))

        self.assertEqual(await visit(service), link.original_url)

        repository.find_active_by_short_code.assert_not_awaited()
        cache.set.assert_not_awaited()
        producer.publish.assert_called_once()

    async def test_expired_cached_link_is_invalidated_without_database_lookup(self):
        link = make_link(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        service, repository, producer, cache = make_service(link)
        cache.get.return_value = json.dumps(service._link_to_cache_payload(link))

        with self.assertRaises(ResourceGoneError) as raised:
            await visit(service)

        self.assertEqual(raised.exception.code, "link_expired")
        repository.find_active_by_short_code.assert_not_awaited()
        cache.delete.assert_awaited_once_with("link:example-code")
        producer.publish.assert_not_called()

    async def test_legacy_public_link_without_policy_remains_visitable(self):
        link = make_link(policy=None)
        service, _, producer, cache = make_service(link)

        self.assertEqual(await visit(service), link.original_url)

        cached_payload = json.loads(cache.set.await_args.args[1])
        self.assertEqual(cached_payload["policy"], {})
        producer.publish.assert_called_once()

    async def test_invalid_or_old_cached_payload_is_deleted_and_refetched(self):
        legacy_payload = LinksService._link_to_cache_payload(make_link())
        del legacy_payload["policy"]
        for payload in (
            "not-json",
            json.dumps([]),
            json.dumps({"id": 42}),
            json.dumps(legacy_payload),
        ):
            with self.subTest(payload=payload):
                link = make_link()
                service, repository, _, cache = make_service(link)
                cache.get.return_value = payload

                with patch("app.services.links.logger.exception"):
                    self.assertEqual(await visit(service), link.original_url)

                cache.delete.assert_awaited_once_with("link:example-code")
                repository.find_active_by_short_code.assert_awaited_once()

    async def test_unknown_link_is_not_published(self):
        service, _, producer, cache = make_service()

        with (
            patch("app.services.links.logger.warning"),
            self.assertRaises(ResourceNotFoundError),
        ):
            await visit(service)

        producer.publish.assert_not_called()
        cache.set.assert_not_awaited()

    async def test_expired_link_is_disabled_and_not_published(self):
        service, repository, producer, cache = make_service(
            make_link(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )

        with self.assertRaises(ResourceGoneError) as raised:
            await visit(service)

        self.assertEqual(raised.exception.code, "link_expired")
        repository.soft_delete_by_short_code.assert_awaited_once_with(
            short_code="example-code"
        )
        cache.delete.assert_awaited_once_with("link:example-code")
        producer.publish.assert_not_called()

    async def test_exhausted_link_is_disabled_and_not_published(self):
        service, repository, producer, _ = make_service(
            make_link(max_visits=2, visit_count=2)
        )

        with self.assertRaises(ResourceGoneError) as raised:
            await visit(service)

        self.assertEqual(raised.exception.code, "link_visit_limit_reached")
        repository.soft_delete_by_short_code.assert_awaited_once()
        repository.increment_visit_count.assert_not_awaited()
        producer.publish.assert_not_called()

    async def test_limited_link_increments_count_without_caching(self):
        link = make_link(max_visits=2, visit_count=0)
        admitted = make_link(max_visits=2, visit_count=1)
        service, repository, producer, cache = make_service(link)
        repository.increment_visit_count.return_value = admitted

        self.assertEqual(await visit(service), link.original_url)

        repository.increment_visit_count.assert_awaited_once_with(link_id=42)
        self.assertEqual(link.visit_count, 1)
        cache.set.assert_not_awaited()
        producer.publish.assert_called_once()

    async def test_limited_link_rejected_by_repository_is_not_published(self):
        service, repository, producer, cache = make_service(make_link(max_visits=1))
        repository.increment_visit_count.return_value = None

        with self.assertRaises(ResourceGoneError) as raised:
            await visit(service)

        self.assertEqual(raised.exception.code, "link_visit_limit_reached")
        cache.set.assert_not_awaited()
        producer.publish.assert_not_called()

    async def test_password_link_requires_correct_password_every_visit(self):
        test_password = "test-password"
        password_hash = LinksService._hash_password(test_password)
        link = make_link(
            max_visits=2,
            policy={"type": "password_protected", "password": password_hash},
        )
        service, repository, producer, cache = make_service(link)

        for password in (None, "wrong-password"):
            with self.subTest(password=password):
                with self.assertRaises(UnauthorizedError):
                    await visit(service, password=password)

        repository.increment_visit_count.assert_not_awaited()
        producer.publish.assert_not_called()
        cache.set.assert_not_awaited()

        self.assertEqual(
            await visit(service, password=test_password), link.original_url
        )
        repository.increment_visit_count.assert_awaited_once()
        producer.publish.assert_called_once()
        cache.set.assert_not_awaited()

        with self.assertRaises(UnauthorizedError):
            await visit(service)
        self.assertEqual(repository.increment_visit_count.await_count, 1)
        self.assertEqual(producer.publish.call_count, 1)

    async def test_unlimited_password_link_is_never_cached(self):
        link = make_link(
            policy={
                "type": "password_protected",
                "password": LinksService._hash_password("secret"),
            }
        )
        service, _, producer, cache = make_service(link)

        with patch("app.services.links.time_limited_link_cache_misses") as misses:
            self.assertEqual(await visit(service, password="secret"), link.original_url)

        cache.set.assert_not_awaited()
        producer.publish.assert_called_once()
        misses.inc.assert_not_called()

    async def test_ip_restricted_link_accepts_only_configured_address_or_cidr(self):
        link = make_link(
            max_visits=2,
            policy={"type": "ip_restricted", "ip_list": ["192.0.2.0/24", "::1"]},
        )
        service, repository, producer, cache = make_service(link)

        for ip_address in (None, "198.51.100.1", "bad-ip"):
            with self.subTest(ip_address=ip_address):
                with self.assertRaises(UnauthorizedError):
                    await visit(service, ip_address=ip_address)

        repository.increment_visit_count.assert_not_awaited()
        producer.publish.assert_not_called()

        self.assertEqual(
            await visit(service, ip_address="192.0.2.5"), link.original_url
        )
        self.assertEqual(await visit(service, ip_address="::1"), link.original_url)
        self.assertEqual(repository.increment_visit_count.await_count, 2)
        self.assertEqual(producer.publish.call_count, 2)
        cache.set.assert_not_awaited()

    async def test_malformed_stored_policies_fail_closed(self):
        malformed_policies = (
            "password_protected",
            42,
            {"password": 42},
            {"type": "ip_restricted", "ip_list": "127.0.0.1"},
            {"type": "ip_restricted", "ip_list": [None]},
            {"type": "ip_restricted", "ip_list": ["not-a-network"]},
        )
        for policy in malformed_policies:
            with self.subTest(policy=policy):
                service, repository, producer, _ = make_service(
                    make_link(max_visits=1, policy=policy)
                )

                with self.assertRaises(UnauthorizedError):
                    await visit(service, password="irrelevant")

                repository.increment_visit_count.assert_not_awaited()
                producer.publish.assert_not_called()

    async def test_unsupported_password_hash_algorithm_is_rejected(self):
        link = make_link(
            policy={"type": "password_protected", "password": "legacy$a$b"}
        )
        service, repository, producer, cache = make_service(link)

        with self.assertRaises(UnauthorizedError):
            await visit(service, password="secret")

        repository.increment_visit_count.assert_not_awaited()
        producer.publish.assert_not_called()
        cache.set.assert_not_awaited()

    async def test_expired_link_is_not_cached(self):
        link = make_link(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        service, _, _, cache = make_service(link)

        await service._cache_if_eligible(link)

        cache.set.assert_not_awaited()

    async def test_unlimited_ip_restricted_link_is_never_cached(self):
        link = make_link(policy={"type": "ip_restricted", "ip_list": ["127.0.0.1"]})
        service, _, producer, cache = make_service(link)

        self.assertEqual(await visit(service), link.original_url)

        cache.set.assert_not_awaited()
        producer.publish.assert_called_once()


class DisableTests(unittest.IsolatedAsyncioTestCase):
    async def test_disable_active_link_invalidates_cache(self):
        service, repository, _, cache = make_service(make_link())

        await service.disable_shortened_url("example-code")

        repository.soft_delete_by_short_code.assert_awaited_once_with(
            short_code="example-code"
        )
        cache.delete.assert_awaited_once_with("link:example-code")

    async def test_disable_unknown_or_already_disabled_link_returns_not_found(self):
        service, repository, _, cache = make_service()
        repository.soft_delete_by_short_code.return_value = None

        with self.assertRaises(ResourceNotFoundError):
            await service.disable_shortened_url("example-code")

        cache.delete.assert_not_awaited()
