"""Shared pytest fixtures for gitea-mcp tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from gitea_mcp.client import GiteaClient
from gitea_mcp.server import mcp


@pytest_asyncio.fixture
async def client() -> AsyncIterator[GiteaClient]:
    """A real GiteaClient pointed at a fake base URL.

    Tests use ``pytest-httpx`` to mock the HTTP layer, so no actual network
    traffic occurs. Auth header is set so we can assert on it.
    """
    c = GiteaClient(
        base_url="https://gitea.example.com",
        token="test-token",
        timeout=5.0,
    )
    try:
        yield c
    finally:
        await c.close()


@pytest.fixture(autouse=True)
def reset_server_client(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Some tool tests want the singleton GiteaClient to point at our fake.

    Tests that need this should depend on the ``client`` fixture AND request
    this fixture explicitly; otherwise it's a no-op. To wire the singleton,
    use ``monkeypatch.setattr('gitea_mcp.server._client', client)`` inside
    the test, or use the ``patched_server_client`` fixture below.
    """
    # Reset module-level state between tests by clearing the singleton.
    import gitea_mcp.server as server

    monkeypatch.setattr(server, "_client", None, raising=False)


@pytest_asyncio.fixture
async def patched_server_client(
    client: GiteaClient, monkeypatch: pytest.MonkeyPatch
) -> GiteaClient:
    """Bind the test GiteaClient as the singleton ``get_client()`` returns."""
    import gitea_mcp.server as server

    monkeypatch.setattr(server, "_client", client, raising=False)
    return client


__all__ = ["client", "reset_server_client", "patched_server_client", "mcp"]
