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

Responses are trimmed to documented fields: an MCP client pays tokens for every byte,
and GitHub payloads are mostly URLs the model can't use.
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from fde_mcp.connectors.base import Connector, ConnectorStatus
from fde_mcp.errors import ErrorKind, SourceError
from fde_mcp.untrusted import clean_text

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"
TIMEOUT_S = 10.0
MAX_PULLS = 100  # one page; deeper history is a job for the ops DB, not this tool
MAX_BODY_CHARS = 2000
REPO_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubConnector(Connector):
    name = "github"

    def __init__(self, token: str | None, *, base_url: str = API_BASE, client: httpx.AsyncClient | None = None) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._client = client  # injectable for tests (httpx.MockTransport)

    def status(self) -> ConnectorStatus:
        if not self._token:
            return ConnectorStatus(False, "GITHUB_TOKEN is not set")
        return ConnectorStatus(True, "token present (validity checked on first call)")

    async def list_open_pulls(self, repo: str) -> list[dict[str, Any]]:
        """Open PRs for `owner/name`: number, title, author, updated_at, draft, url."""
        self._require_configured()
        self._validate_repo(repo)
        payload = await self._get(f"/repos/{repo}/pulls", {"state": "open", "per_page": MAX_PULLS})
        # Every string here was written by a stranger: see fde_mcp.untrusted.
        return [
            {
                "number": pr.get("number"),
                "title": clean_text(pr.get("title"), limit=300),
                "author": clean_text((pr.get("user") or {}).get("login"), limit=100),
                "updated_at": clean_text(pr.get("updated_at"), limit=40),
                "draft": bool(pr.get("draft")),
                "url": clean_text(pr.get("html_url"), limit=500),
            }
            for pr in payload
        ]

    async def get_issue(self, repo: str, number: int) -> dict[str, Any]:
        """One issue: number, title, state, labels, assignees, body (truncated), url."""
        self._require_configured()
        self._validate_repo(repo)
        if not isinstance(number, int) or number < 1:
            raise SourceError(self.name, ErrorKind.INVALID_INPUT, f"issue number must be positive, got {number!r}")
        issue = await self._get(f"/repos/{repo}/issues/{number}")
        raw_body = issue.get("body") or ""
        return {
            "number": issue.get("number"),
            "title": clean_text(issue.get("title"), limit=300),
            "state": clean_text(issue.get("state"), limit=40),
            "labels": [clean_text(label.get("name"), limit=100) for label in issue.get("labels") or []],
            "assignees": [clean_text(user.get("login"), limit=100) for user in issue.get("assignees") or []],
            "body": clean_text(raw_body, limit=MAX_BODY_CHARS),
            "body_truncated": len(raw_body) > MAX_BODY_CHARS,
            "url": clean_text(issue.get("html_url"), limit=500),
        }

    def _validate_repo(self, repo: str) -> None:
        if not isinstance(repo, str) or not REPO_SLUG.match(repo):
            raise SourceError(self.name, ErrorKind.INVALID_INPUT, f"repo must look like 'owner/name', got {repo!r}")

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
        }
        try:
            if self._client is not None:
                response = await self._client.get(f"{self._base_url}{path}", params=params, headers=headers, timeout=TIMEOUT_S)
            else:
                async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                    response = await client.get(f"{self._base_url}{path}", params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise SourceError(self.name, ErrorKind.UNAVAILABLE, f"request timed out after {TIMEOUT_S:g}s", retryable=True) from exc
        except httpx.HTTPError as exc:
            # str(exc) is the transport's own message; it never carries our headers.
            raise SourceError(self.name, ErrorKind.UNAVAILABLE, f"cannot reach GitHub: {exc}", retryable=True) from exc

        self._classify_response(response)
        return response.json()

    def _classify_response(self, response: httpx.Response) -> None:
        """Raise the SourceError matching the module docstring table. Returns None on 2xx."""
        status = response.status_code
        if status < 400:
            return
        if status == 429 or (status == 403 and response.headers.get("X-RateLimit-Remaining") == "0"):
            raise SourceError(
                self.name,
                ErrorKind.RATE_LIMITED,
                "GitHub rate limit reached",
                retryable=True,
                retry_after_s=self._retry_after(response),
            )
        if status in (401, 403):
            raise SourceError(self.name, ErrorKind.AUTH, "GitHub rejected the token or it lacks access to this repo")
        if status == 404:
            raise SourceError(self.name, ErrorKind.NOT_FOUND, "not found (or private to this token)")
        if status == 422:
            raise SourceError(self.name, ErrorKind.INVALID_INPUT, "GitHub rejected the request parameters")
        if status >= 500:
            raise SourceError(self.name, ErrorKind.UNAVAILABLE, f"GitHub returned {status}", retryable=True)
        raise SourceError(self.name, ErrorKind.UNAVAILABLE, f"unexpected GitHub status {status}")

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        """Seconds to wait: `Retry-After` wins, else the epoch in `X-RateLimit-Reset`."""
        if (header := response.headers.get("Retry-After")) is not None:
            try:
                return float(header)
            except ValueError:
                return None  # HTTP-date form: rare here, and a wrong number is worse than none
        if (reset := response.headers.get("X-RateLimit-Reset")) is not None:
            try:
                return max(0.0, float(reset) - time.time())
            except ValueError:
                return None
        return None
