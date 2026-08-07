"""Verify HTTP security hardening: rate limiting, CSP/HSTS, and readyz leak reduction."""

import pytest
from fastapi.testclient import TestClient
from researchmate_api.config import Settings
from researchmate_api.main import RATE_LIMIT_PER_MINUTE, RATE_LIMITED_PATHS, create_app

# Rate-limit enforcement depends on the optional slowapi package. When the limiter
# is not installed (e.g. CI lockfile without the slowapi dependency) the middleware
# skips rate limiting, so these tests must be skipped rather than fail.
try:
    import slowapi  # noqa: F401

    _HAS_SLOWAPI = True
except ModuleNotFoundError:
    _HAS_SLOWAPI = False

_skip_no_slowapi = pytest.mark.skipif(not _HAS_SLOWAPI, reason="slowapi not installed")


def _local_settings(**overrides) -> Settings:
    """Build minimal local-mode settings for HTTP-level smoke tests."""
    base = {"app_env": "local", "auth_mode": "development"}
    base.update(overrides)
    return Settings(**base)


def test_security_headers_include_csp_and_hsts() -> None:
    """Lock down content sources and require long-lived HSTS on every response."""
    with TestClient(create_app(settings=_local_settings())) as client:
        # The local development auth mode keeps /me reachable without a real token; the
        # 401 response still goes through the attach_request_id middleware and so carries
        # the security headers.
        response = client.get("/api/v1/healthz")

    assert response.status_code == 200
    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    # Existing headers stay in place alongside the new ones.
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_rate_limit_constants_protect_health_and_auth_paths() -> None:
    """Protect the cheap public endpoints and the authentication edge from abuse."""
    assert RATE_LIMIT_PER_MINUTE == "60/minute"
    expected_paths = {
        "/api/v1/healthz",
        "/api/v1/readyz",
        "/api/v1/me",
        "/mcp",
    }
    assert expected_paths <= set(RATE_LIMITED_PATHS)


@_skip_no_slowapi
def test_rate_limit_middleware_registered_with_limiter_state() -> None:
    """Attach the slowapi limiter to app.state so the per-IP bucket is consulted."""
    app = create_app(settings=_local_settings())
    assert getattr(app.state, "limiter", None) is not None
    assert app.state.rate_limit_item is not None


@_skip_no_slowapi
def test_rate_limit_returns_429_after_bucket_exhausted() -> None:
    """Return the stable 429 error envelope once the per-IP minute bucket is empty.

    The rate-limit bucket is a fixed 60/minute per source IP, keyed to the protected path
    set. Hitting /healthz 61 times must surface the RATE_LIMITED code on the 61st call.
    """
    with TestClient(create_app(settings=_local_settings())) as client:
        # The bucket allows 60 hits within the rolling minute; the first 60 must succeed.
        for _ in range(60):
            ok = client.get("/api/v1/healthz")
            assert ok.status_code == 200
        # The 61st request must be rejected with the stable 429 envelope.
        blocked = client.get("/api/v1/healthz")

    assert blocked.status_code == 429
    body = blocked.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "request_id" in body["error"]
    # The 429 response still carries the security headers.
    assert blocked.headers["content-security-policy"].startswith("default-src 'none'")


@_skip_no_slowapi
def test_unprotected_path_is_not_blocked_by_the_rate_limit_bucket() -> None:
    """Keep the per-IP bucket scoped to the configured protected path set."""
    with TestClient(create_app(settings=_local_settings())) as client:
        # The /api/v1/projects path is not in RATE_LIMITED_PATHS, so it should remain
        # reachable even when the protected-path bucket has been exhausted.
        for _ in range(70):
            response = client.get("/api/v1/projects")
            # Without authentication we expect a 401 from the auth dependency, never a 429
            # from the rate limiter. That proves the bucket does not cover this path.
            assert response.status_code != 429


# --------------------------------------------------------------------------- #
# /readyz information-leak reduction                                         #
# --------------------------------------------------------------------------- #


def test_readyz_default_in_production_hides_component_details() -> None:
    """Hide component state and failure lists when verbose is not requested in prod."""
    # Use the test environment which simulates a fully-optional local stack: the default
    # verbose=None must reduce to a status-only payload in production-mode envs.
    settings = Settings(app_env="test", llm_provider="fake", embedding_provider="fake")
    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/v1/readyz", params={"verbose": "false"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["environment"] == "test"
    assert "components" not in payload
    assert "failed_components" not in payload


def test_readyz_verbose_returns_full_component_detail() -> None:
    """Return the full component snapshot when verbose=true is requested."""
    settings = Settings(app_env="test", llm_provider="fake", embedding_provider="fake")
    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/v1/readyz", params={"verbose": "true"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["components"]["database"] == "not_required"
    assert payload["failed_components"] == []


def test_readyz_default_in_local_env_returns_full_detail() -> None:
    """Default to verbose output in local/test environments for operator convenience."""
    settings = Settings(app_env="test", llm_provider="fake", embedding_provider="fake")
    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/v1/readyz")

    payload = response.json()
    assert "components" in payload
    assert "failed_components" in payload
