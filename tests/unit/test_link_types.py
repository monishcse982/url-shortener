import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError

from app.schemas.links import LinkPolicyType, ShortenRequest

VALID_POLICIES = {
    "public": {"type": "public"},
    "password_protected": {
        "type": "password_protected",
        "password": "unit-test-password",
    },
    "ip_restricted": {"type": "ip_restricted", "ip_list": ["127.0.0.1"]},
}

with patch("confluent_kafka.Producer"):
    from app.services.links import LinksService


class LinkTypeSchemaTests(unittest.TestCase):
    def test_fixtures_cover_every_supported_policy_type(self) -> None:
        self.assertEqual(set(VALID_POLICIES), {kind.value for kind in LinkPolicyType})

    def test_every_link_type_is_accepted(self) -> None:
        for link_type, policy in VALID_POLICIES.items():
            with self.subTest(link_type=link_type):
                request = ShortenRequest.model_validate(
                    {
                        "url": "https://example.com/target",
                        "ttl_seconds": 3600,
                        "max_visits": 10,
                        "policy": policy,
                    }
                )
                self.assertEqual(request.policy.type.value, link_type)

    def test_protected_links_require_valid_policy_configuration(self) -> None:
        invalid_policies = (
            {"type": "password_protected"},
            {"type": "ip_restricted"},
            {"type": "ip_restricted", "ip_list": ["not-an-ip"]},
            {"type": "public", "password": "secret"},
        )
        for policy in invalid_policies:
            with self.subTest(policy=policy):
                with self.assertRaises(ValidationError):
                    ShortenRequest.model_validate(
                        {
                            "url": "https://example.com/target",
                            "ttl_seconds": 3600,
                            "policy": policy,
                        }
                    )


class LinkTypeCreationTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_link_type_is_persisted(self) -> None:
        for link_type, policy in VALID_POLICIES.items():
            with self.subTest(link_type=link_type):
                expires_at = datetime.now(UTC)
                link = SimpleNamespace(
                    id=1, short_code="example-code", expires_at=expires_at
                )
                repository = SimpleNamespace(create=AsyncMock(return_value=link))
                service = LinksService(repository, MagicMock(), MagicMock())
                request = ShortenRequest.model_validate(
                    {
                        "url": "https://example.com/target",
                        "short_code": "example-code",
                        "ttl_seconds": 3600,
                        "max_visits": 10,
                        "policy": policy,
                    }
                )

                response = await service.shorten_url(request)

                saved = repository.create.await_args.kwargs
                self.assertEqual(saved["short_code"], "example-code")
                self.assertEqual(saved["max_visits"], 10)
                self.assertEqual(saved["policy"]["type"], link_type)
                self.assertAlmostEqual(
                    (saved["expires_at"] - datetime.now(UTC)).total_seconds(),
                    3600,
                    delta=2,
                )
                self.assertTrue(response.shortened_url.endswith("/example-code"))
                self.assertEqual(response.expires_at, expires_at)

                if link_type == "password_protected":
                    self.assertTrue(saved["policy"]["password"].startswith("scrypt$"))
                    self.assertNotIn("unit-test-password", str(saved["policy"]))
                elif link_type == "ip_restricted":
                    self.assertEqual(saved["policy"]["ip_list"], ["127.0.0.1"])
                else:
                    self.assertNotIn("password", saved["policy"])
                    self.assertNotIn("ip_list", saved["policy"])
