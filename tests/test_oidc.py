import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import oidc


@pytest.fixture(scope="module")
def signing_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


class FakeSigningKey:
    def __init__(self, key):
        self.key = key


class FakeJwksClient:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, _token):
        return FakeSigningKey(self.key)


def make_token(private_key, *, audience=oidc.OIDC_AUDIENCE, expires_at=None):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "demo-user",
            "iss": oidc.OIDC_ISSUER,
            "aud": audience,
            "iat": now,
            "exp": expires_at or now + 60,
        },
        private_key,
        algorithm="RS256",
    )


def test_oidc_accepts_signed_token_with_expected_issuer_and_audience(monkeypatch, signing_keys):
    private_key, public_key = signing_keys
    monkeypatch.setattr(oidc, "_jwks_client", FakeJwksClient(public_key))
    token = make_token(private_key)

    user = oidc.require_authenticated_user(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )

    assert user["sub"] == "demo-user"


def test_oidc_rejects_token_with_unexpected_audience(monkeypatch, signing_keys):
    private_key, public_key = signing_keys
    monkeypatch.setattr(oidc, "_jwks_client", FakeJwksClient(public_key))
    token = make_token(private_key, audience="another-api")

    with pytest.raises(HTTPException) as error:
        oidc.require_authenticated_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )

    assert error.value.status_code == 401


def test_oidc_rejects_expired_token(monkeypatch, signing_keys):
    private_key, public_key = signing_keys
    monkeypatch.setattr(oidc, "_jwks_client", FakeJwksClient(public_key))
    token = make_token(private_key, expires_at=int(time.time()) - 60)

    with pytest.raises(HTTPException) as error:
        oidc.require_authenticated_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )

    assert error.value.status_code == 401


def test_oidc_requires_bearer_credentials():
    with pytest.raises(HTTPException) as error:
        oidc.require_authenticated_user(None)

    assert error.value.status_code == 401
