import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

with patch("confluent_kafka.Producer"):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.exception_handlers import register_exception_handlers
    from app.api.routes.links import (
        get_cache,
        get_kafka_producer,
        get_links_repository,
        get_links_service,
        get_visits_repository,
        router,
    )
    from app.core.auth import get_current_user
    from app.core.exceptions import UnauthorizedError
    from app.db.repositories.links import LinksRepository
    from app.db.repositories.visits import VisitsRepository
    from app.kafka.producer import KafkaProducer, kafka_producer
    from app.schemas.links import ManagedLink, ManagedLinkList, ShortenResponse


def make_client(service, *, authenticated=True):
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_links_service] = lambda: service
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: "user-1"
    return TestClient(app)


class LinkHttpTests(unittest.TestCase):
    def managed_link(self):
        return ManagedLink(
            id=1,
            short_code="example-code",
            shortened_url="http://localhost:8000/link/example-code",
            original_url="https://example.com/target",
            title=None,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC),
            visit_count=0,
            max_visits=None,
            status="active",
            policy_type="public",
        )

    def test_dependency_factories_use_supplied_resources(self):
        links_repository = object()
        producer = object()
        cache = object()
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(cache=cache))
        )

        service = get_links_service(links_repository, producer, cache)

        self.assertIs(service.links_repository, links_repository)
        self.assertIs(service.kafka_producer, producer)
        self.assertIs(service.cache, cache)
        self.assertIs(get_cache(request), cache)
        self.assertIsInstance(get_links_repository(), LinksRepository)
        self.assertIsInstance(get_visits_repository(), VisitsRepository)
        self.assertIsInstance(get_kafka_producer(), KafkaProducer)
        self.assertIs(get_kafka_producer(), kafka_producer)

    def test_create_endpoint_returns_validated_response(self):
        service = SimpleNamespace(
            shorten_url=AsyncMock(
                return_value=ShortenResponse(
                    shortened_url="http://localhost:8000/link/example-code",
                    expires_at=datetime.now(UTC),
                )
            )
        )

        with make_client(service) as client:
            response = client.post(
                "/link/",
                json={"url": "https://example.com/target", "ttl_seconds": 60},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["shortened_url"],
            "http://localhost:8000/link/example-code",
        )
        service.shorten_url.assert_awaited_once()

    def test_create_endpoint_rejects_invalid_request_before_service_call(self):
        service = SimpleNamespace(shorten_url=AsyncMock())

        with make_client(service) as client:
            response = client.post("/link/", json={"url": "ftp://example.com"})

        self.assertEqual(response.status_code, 422)
        service.shorten_url.assert_not_awaited()

    def test_redirect_endpoint_returns_302_and_forwards_auth_headers(self):
        service = SimpleNamespace(
            get_url=AsyncMock(return_value="https://example.com/target")
        )

        with make_client(service) as client:
            response = client.get(
                "/link/example-code",
                headers={"password": "secret"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "https://example.com/target")
        self.assertEqual(service.get_url.await_args.kwargs["password"], "secret")
        self.assertIsNotNone(service.get_url.await_args.kwargs["ip_address"])

    def test_application_errors_are_mapped_to_http_responses(self):
        service = SimpleNamespace(
            get_url=AsyncMock(
                side_effect=UnauthorizedError(message="Password required")
            )
        )

        with make_client(service) as client:
            response = client.get("/link/example-code")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "unauthorized")
        self.assertEqual(response.json()["detail"], "Password required")

    def test_disable_endpoint_returns_204(self):
        service = SimpleNamespace(disable_shortened_url=AsyncMock())

        with make_client(service) as client:
            response = client.delete("/links/example-code")

        self.assertEqual(response.status_code, 204)
        service.disable_shortened_url.assert_awaited_once_with("example-code", "user-1")

    def test_legacy_disable_path_remains_authenticated_alias(self):
        service = SimpleNamespace(disable_shortened_url=AsyncMock())
        with make_client(service) as client:
            response = client.delete("/link/example-code")
        self.assertEqual(response.status_code, 204)
        service.disable_shortened_url.assert_awaited_once_with("example-code", "user-1")

    def test_management_endpoints_pass_owner_and_validate_edit(self):
        link = self.managed_link()
        service = SimpleNamespace(
            list_managed_links=AsyncMock(
                return_value=ManagedLinkList(items=[link], total=1)
            ),
            get_managed_link=AsyncMock(return_value=link),
            update_destination=AsyncMock(return_value=link),
        )
        with make_client(service) as client:
            listed = client.get("/links?limit=20&offset=0")
            detail = client.get("/links/example-code")
            invalid = client.patch(
                "/links/example-code", json={"url": "ftp://example.com"}
            )
            edited = client.patch(
                "/links/example-code", json={"url": "https://new.example/"}
            )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 1)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(edited.status_code, 200)
        service.list_managed_links.assert_awaited_once_with(
            "user-1", limit=20, offset=0
        )
        service.get_managed_link.assert_awaited_once_with("example-code", "user-1")
        service.update_destination.assert_awaited_once_with(
            "example-code", "user-1", "https://new.example/"
        )

    def test_management_requires_bearer_token(self):
        from app.core.config import settings

        with (
            patch.object(
                settings, "cognito_issuer", "https://cognito-idp.example.test/pool"
            ),
            patch.object(settings, "cognito_client_id", "spa-client"),
            make_client(SimpleNamespace(), authenticated=False) as client,
        ):
            responses = [
                client.post(
                    "/link/", json={"url": "https://example.com", "ttl_seconds": 60}
                ),
                client.get("/links"),
                client.get("/links/example-code"),
                client.patch(
                    "/links/example-code", json={"url": "https://example.com"}
                ),
                client.delete("/links/example-code"),
            ]
        self.assertTrue(all(response.status_code == 401 for response in responses))

    def test_dummy_target_endpoint_returns_ok(self):
        with make_client(SimpleNamespace()) as client:
            response = client.get("/dummy-target")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
