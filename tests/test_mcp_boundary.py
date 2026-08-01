"""Verify MCP authentication, runtime fallback, and REST-equivalent access policies."""

from uuid import UUID

from fastapi.testclient import TestClient
from researchmate_api.config import Settings
from researchmate_api.main import create_app

ADMIN = UUID("00000000-0000-4000-8000-000000000099")


def _missing_mcp_runtime() -> None:
    """Raise the exact optional-dependency error accepted by application assembly."""
    error = ModuleNotFoundError("No module named 'mcp'")
    error.name = "mcp"
    raise error


def test_mcp_requires_the_same_bearer_boundary_as_rest(monkeypatch) -> None:
    """Require MCP requests to pass the same bearer-token boundary as REST."""
    import researchmate_api.mcp_server as mcp_module

    monkeypatch.setattr(
        mcp_module,
        "build_mcp_server",
        _missing_mcp_runtime,
    )
    with TestClient(create_app(Settings(app_env="test"))) as client:
        response = client.post("/mcp", headers={"X-Request-ID": "req_mcp_auth_123"})

    assert response.status_code == 401
    assert response.headers["x-request-id"] == "req_mcp_auth_123"
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_mcp_missing_sdk_is_an_explicit_authenticated_503(monkeypatch) -> None:
    """Return an explicit authenticated service error when the MCP SDK is absent."""
    import researchmate_api.mcp_server as mcp_module

    monkeypatch.setattr(
        mcp_module,
        "build_mcp_server",
        _missing_mcp_runtime,
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


def _mcp_headers(token: str) -> dict[str, str]:
    """Build the headers required by FastMCP's stateless JSON transport."""
    return {
        "Host": "127.0.0.1:8000",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _mcp_call(
    client: TestClient, token: str, name: str, arguments: dict, request_id: int
):
    """Invoke one MCP tool through the real Streamable HTTP boundary."""
    return client.post(
        "/mcp/",
        headers=_mcp_headers(token),
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


def test_mcp_personal_project_search_requires_conversation_scope() -> None:
    """Reject project-wide search of the shared personal-project container."""
    with TestClient(create_app(Settings(app_env="test"))) as client:
        personal = client.post(
            "/api/v1/chat/bootstrap",
            headers={"Authorization": "Bearer dev-user-a"},
        ).json()
        response = _mcp_call(
            client,
            "dev-user-a",
            "search_project",
            {"project_id": personal["id"], "query": "private"},
            11,
        )
    assert response.status_code == 200
    assert "PROJECT_SCOPE_REQUIRES_CONVERSATION" in response.text


def test_mcp_trace_access_matches_rest_admin_policy() -> None:
    """Deny a trace owner through MCP when REST also requires a privileged role."""
    user_headers = {"Authorization": "Bearer dev-user-a"}
    with TestClient(create_app(Settings(app_env="test"))) as client:
        project = client.post(
            "/api/v1/projects", json={"name": "Trace"}, headers=user_headers
        ).json()
        ask = client.post(
            "/api/v1/ask",
            json={"project_id": project["id"], "message": "hello"},
            headers=user_headers,
        )
        assert ask.status_code == 200
        trace_id = ask.json()["trace_id"]
        rest = client.get(f"/api/v1/dev/traces/{trace_id}", headers=user_headers)
        mcp = _mcp_call(
            client, "dev-user-a", "get_run_trace", {"trace_id": trace_id}, 12
        )
    assert rest.status_code == 403
    assert mcp.status_code == 200
    assert "ADMIN_REQUIRED" in mcp.text
