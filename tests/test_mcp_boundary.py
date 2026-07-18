from uuid import UUID

from fastapi.testclient import TestClient

from researchmate_api.config import Settings
from researchmate_api.main import create_app


ADMIN = UUID("00000000-0000-4000-8000-000000000099")


def test_mcp_requires_the_same_bearer_boundary_as_rest(monkeypatch) -> None:
    import researchmate_api.mcp_server as mcp_module

    monkeypatch.setattr(
        mcp_module,
        "build_mcp_server",
        lambda: (_ for _ in ()).throw(ImportError("test fallback")),
    )
    with TestClient(create_app(Settings(app_env="test"))) as client:
        response = client.post("/mcp", headers={"X-Request-ID": "req_mcp_auth_123"})

    assert response.status_code == 401
    assert response.headers["x-request-id"] == "req_mcp_auth_123"
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_mcp_missing_sdk_is_an_explicit_authenticated_503(monkeypatch) -> None:
    import researchmate_api.mcp_server as mcp_module

    monkeypatch.setattr(
        mcp_module,
        "build_mcp_server",
        lambda: (_ for _ in ()).throw(ImportError("test fallback")),
    )
    with TestClient(create_app(Settings(app_env="test"))) as client:
        response = client.post(
            "/mcp",
            headers={
                "Authorization": f"Bearer dev:{ADMIN}:admin:admin@example.test",
                "X-Request-ID": "req_mcp_sdk_123",
            },
        )

    assert response.status_code == 503
    assert response.headers["x-request-id"] == "req_mcp_sdk_123"
    assert response.json()["error"] == {
        "code": "MCP_RUNTIME_NOT_INSTALLED",
        "message": "Install the pinned MCP SDK to enable Streamable HTTP.",
        "request_id": "req_mcp_sdk_123",
    }


def test_installed_mcp_runtime_initializes_behind_the_rest_bearer_boundary() -> None:
    """Exercise the real Streamable HTTP app rather than only the missing-SDK fallback."""
    headers = {
        "Host": "127.0.0.1:8000",  # FastMCP rejects TestClient's default host by design.
        "Authorization": f"Bearer dev:{ADMIN}:admin:admin@example.test",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "researchmate-test", "version": "1"},
        },
    }

    with TestClient(create_app(Settings(app_env="test"))) as client:
        response = client.post("/mcp/", headers=headers, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["serverInfo"]["name"] == "ResearchMate"
    assert body["result"]["capabilities"]["tools"]["listChanged"] is False
