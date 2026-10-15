import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.schemas.links import ShortenRequest

with patch("confluent_kafka.Producer"):
    from app.api.routes.links import (
        disable_shortened_url,
        redirect_to_url,
        shorten_url,
    )


class LinkRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_route_passes_validated_request_to_service(self):
        request = ShortenRequest.model_validate(
            {"url": "https://example.com/target", "ttl_seconds": 60}
        )
        expected_response = object()
        service = SimpleNamespace(shorten_url=AsyncMock(return_value=expected_response))

        self.assertIs(await shorten_url(request, service), expected_response)

        service.shorten_url.assert_awaited_once_with(request)

    async def test_redirect_forwards_auth_header_and_client_ip(self):
        request = SimpleNamespace(
            headers={
                "password": "secret",
                "user-agent": "unit-test-agent",
                "referer": "https://example.com/referrer",
            },
            client=SimpleNamespace(host="192.0.2.5"),
        )
        service = SimpleNamespace(
            get_url=AsyncMock(return_value="https://example.com/target")
        )

        response = await redirect_to_url("example-code", request, service)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "https://example.com/target")
        service.get_url.assert_awaited_once_with(
            "example-code",
            password="secret",
            user_agent="unit-test-agent",
            referrer="https://example.com/referrer",
            ip_address="192.0.2.5",
        )

    async def test_redirect_handles_missing_optional_headers_and_client(self):
        request = SimpleNamespace(headers={}, client=None)
        service = SimpleNamespace(
            get_url=AsyncMock(return_value="https://example.com/target")
        )

        await redirect_to_url("example-code", request, service)

        service.get_url.assert_awaited_once_with(
            "example-code",
            password=None,
            user_agent=None,
            referrer=None,
            ip_address=None,
        )

    async def test_disable_route_forwards_short_code(self):
        service = SimpleNamespace(disable_shortened_url=AsyncMock())

        await disable_shortened_url("example-code", service)

        service.disable_shortened_url.assert_awaited_once_with("example-code")
