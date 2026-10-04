import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import get_settings
from app.main import app

PROTECTED = [
    ("get", "/api/auth/me"),
    ("post", "/api/chat"),
    ("get", "/api/conversations"),
    ("get", "/api/documents"),
    ("post", "/api/documents"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_endpoints_require_token(anon_client, method, path):
    response = getattr(anon_client, method)(path)
    assert response.status_code == 401


def test_health_is_public(anon_client):
    assert anon_client.get("/health").json() == {"status": "ok"}


@pytest.fixture
def signing(monkeypatch):
    """Sign tokens with a local RSA key and make the backend trust it instead of Keycloak."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class _Key:
        def __init__(self):
            self.key = key.public_key()

    class _Client:
        def get_signing_key_from_jwt(self, _token):
            return _Key()

    monkeypatch.setattr(security, "_jwk_client", lambda _url: _Client())
    settings = get_settings()

    def make(**overrides):
        now = int(time.time())
        claims = {
            "sub": "kc-user-1",
            "preferred_username": "katniss",
            "email": "katniss@district12.pn",
            "iss": settings.keycloak_issuer,
            "aud": settings.keycloak_audience,
            "iat": now,
            "exp": now + 300,
            "realm_access": {"roles": ["user"]},
        }
        claims.update(overrides)
        return jwt.encode(claims, key, algorithm="RS256")

    return make


def _me(token):
    app.dependency_overrides.clear()
    return TestClient(app).get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_valid_token(signing):
    response = _me(signing())
    assert response.status_code == 200
    assert response.json()["username"] == "katniss"
    assert response.json()["roles"] == ["user"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-api"},
        {"iss": "http://evil.example/realms/x"},
        {"exp": int(time.time()) - 10},
    ],
)
def test_invalid_tokens_are_rejected(signing, overrides):
    assert _me(signing(**overrides)).status_code == 401


def test_garbage_token_is_rejected(signing):
    assert _me("not-a-jwt").status_code == 401
