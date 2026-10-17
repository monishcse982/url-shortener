import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth import get_current_user
from app.core.exceptions import UnauthorizedError

ISSUER = "https://cognito-idp.example.test/pool"
CLIENT_ID = "spa-client"


class CognitoAuthTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def token(self, **overrides):
        now = datetime.now(UTC)
        claims = {
            "iss": ISSUER,
            "sub": "user-1",
            "client_id": CLIENT_ID,
            "token_use": "access",
            "username": "someone",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(
            claims, self.private_key, algorithm="RS256", headers={"kid": "test-key"}
        )

    async def check(self, token):
        with (
            patch("app.core.auth.settings.cognito_issuer", ISSUER),
            patch("app.core.auth.settings.cognito_client_id", CLIENT_ID),
            patch("app.core.auth.jwks_client") as client,
        ):
            client.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(
                key=self.private_key.public_key()
            )
            return await get_current_user(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            )

    async def test_valid_access_token_returns_subject(self):
        self.assertEqual(await self.check(self.token()), "user-1")

    async def test_rejects_wrong_client_id_token_expired_token_and_machine_token(self):
        for claims in (
            {"client_id": "another-client"},
            {"token_use": "id"},
            {"exp": datetime.now(UTC) - timedelta(seconds=1)},
            {"username": None},
        ):
            with self.subTest(claims=claims), self.assertRaises(UnauthorizedError):
                await self.check(self.token(**claims))

    async def test_rejects_missing_bearer_token(self):
        with (
            patch("app.core.auth.settings.cognito_issuer", ISSUER),
            patch("app.core.auth.settings.cognito_client_id", CLIENT_ID),
            self.assertRaises(UnauthorizedError),
        ):
            await get_current_user(None)

    async def test_rejects_token_signed_by_another_key(self):
        claims = jwt.decode(self.token(), options={"verify_signature": False})
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        forged = jwt.encode(
            claims, other_key, algorithm="RS256", headers={"kid": "test-key"}
        )
        with self.assertRaises(UnauthorizedError):
            await self.check(forged)
