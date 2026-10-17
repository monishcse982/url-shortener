import hmac
from functools import lru_cache

import jwt
from fastapi import Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import settings
from app.core.exceptions import ApplicationError, UnauthorizedError

bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=4)
def jwks_client(issuer: str) -> PyJWKClient:
    return PyJWKClient(f"{issuer.rstrip('/')}/.well-known/jwks.json")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if not settings.cognito_issuer or not settings.cognito_client_id:
        raise ApplicationError("Cognito authentication is not configured")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError(message="Bearer access token required")

    try:
        signing_key = await run_in_threadpool(
            jwks_client(settings.cognito_issuer).get_signing_key_from_jwt,
            credentials.credentials,
        )
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.cognito_issuer,
            options={
                "verify_aud": False,
                "require": ["exp", "iat", "iss", "sub", "client_id", "token_use"],
            },
        )
        if (
            claims.get("token_use") != "access"
            or not hmac.compare_digest(
                str(claims["client_id"]), settings.cognito_client_id
            )
            or not isinstance(claims["sub"], str)
            or not claims["sub"]
            or not isinstance(claims.get("username"), str)
        ):
            raise ValueError("Wrong token type or app client")
        return claims["sub"]
    except (jwt.PyJWTError, ValueError, TypeError) as error:
        raise UnauthorizedError(message="Invalid or expired access token") from error
