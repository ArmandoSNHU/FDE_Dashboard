"""GitHub REST API connector (read-only).

Auth: fine-grained personal access token in GITHUB_TOKEN, sent as
`Authorization: Bearer <token>`. Grant only read access (Metadata, Contents,
Issues, Pull requests) on the specific repos the server should see — the token's
scope is the outer boundary; our policy layer is the inner one.

Failure mapping (implemented in `_classify_response`):
    401                                   -> AUTH          (not retryable)
    403 + X-RateLimit-Remaining: 0, 429   -> RATE_LIMITED  (retry_after_s from Retry-After / X-RateLimit-Reset)
    403 otherwise                         -> AUTH          (token lacks repo permission)
    404                                   -> NOT_FOUND     (also what GitHub returns for private repos you can't see)
    422                                   -> INVALID_INPUT
    5xx, timeout, connection error        -> UNAVAILABLE   (retryable)
"""

from __future__ import annotations

from typing import Any

import httpx

from fde_mcp.connectors.base import Connector, ConnectorStatus

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
TIMEOUT_S = 10.0


class GitHubConnector(Connector):
    name = "github"

    def __init__(self, token: str | None, *, base_url: str = API_BASE, client: httpx.AsyncClient | None = None) -> None:
        self._token = token
        self._base_url = base_url
        self._client = client  # injectable for tests (httpx.MockTransport)

    def status(self) -> ConnectorStatus:
        if not self._token:
            return ConnectorStatus(False, "GITHUB_TOKEN is not set")
        return ConnectorStatus(True, "token present (validity checked on first call)")

    async def list_open_pulls(self, repo: str) -> list[dict[str, Any]]:
        """Open PRs for `owner/name`: number, title, author, updated_at, draft, url."""
        self._require_configured()
        # TODO: validate repo slug -> INVALID_INPUT; GET /repos/{repo}/pulls?state=open; trim fields.
        raise NotImplementedError

    async def get_issue(self, repo: str, number: int) -> dict[str, Any]:
        """One issue: number, title, state, labels, assignees, body (truncated), url."""
        self._require_configured()
        # TODO: GET /repos/{repo}/issues/{number}; trim fields; cap body length.
        raise NotImplementedError

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        # TODO: send with auth + version headers and TIMEOUT_S; map transport errors
        # to UNAVAILABLE; pass response through _classify_response.
        raise NotImplementedError

    def _classify_response(self, response: httpx.Response) -> None:
        # TODO: implement the mapping table in the module docstring.
        raise NotImplementedError
