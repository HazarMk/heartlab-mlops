"""OIDC bearer-token validation for the protected API routes."""
import os
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError

OIDC_ISSUER = os.getenv("OIDC_ISSUER", "http://127.0.0.1:8080/realms/heart-demo").rstrip("/")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "heart-api")
OIDC_JWKS_URL = os.getenv(
    "OIDC_JWKS_URL",
    f"{OIDC_ISSUER}/protocol/openid-connect/certs",
)

_bearer = HTTPBearer(auto_error=False)
_jwks_client = PyJWKClient(OIDC_JWKS_URL, cache_keys=True, timeout=5)


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(credentials.credentials)
        return jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            audience=OIDC_AUDIENCE,
            issuer=OIDC_ISSUER,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except PyJWKClientConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail="Identity provider is temporarily unavailable",
        ) from exc
    except (jwt.InvalidTokenError, PyJWKClientError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
