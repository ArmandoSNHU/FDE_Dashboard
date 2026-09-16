"""GitHub connector: failure classification and response trimming.

Every test runs against httpx.MockTransport — no network, no token.
"""

import time

import httpx
import pytest

from fde_mcp.connectors.github import GitHubConnector
from fde_mcp.errors import ErrorKind, SourceError


def connector(handler) -> GitHubConnector:
    """A configured connector whose transport is a canned responder."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.test")
    return GitHubConnector(token="ghp_test", base_url="https://api.github.test", client=client)


def responding(status: int, *, json=None, headers=None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json if json is not None else {}, headers=headers or {})

    return handler


def raising(exc: Exception):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


async def call(conn: GitHubConnector):
    return await conn.list_open_pulls("octo/repo")


# --- status -> ErrorKind -----------------------------------------------------


@pytest.mark.parametrize(
    ("status", "kind", "retryable"),
    [
        (401, ErrorKind.AUTH, False),
        (403, ErrorKind.AUTH, False),  # no rate-limit headers: a permissions problem
        (404, ErrorKind.NOT_FOUND, False),
        (422, ErrorKind.INVALID_INPUT, False),
        (500, ErrorKind.UNAVAILABLE, True),
        (502, ErrorKind.UNAVAILABLE, True),
    ],
)
async def test_http_status_classification(status, kind, retryable):
    with pytest.raises(SourceError) as exc:
        await call(connector(responding(status)))
    assert (exc.value.source, exc.value.kind, exc.value.retryable) == ("github", kind, retryable)


async def test_403_with_exhausted_rate_limit_is_rate_limited_with_reset_delay():
    reset_at = int(time.time()) + 60
    handler = responding(403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_at)})
    with pytest.raises(SourceError) as exc:
        await call(connector(handler))
    assert exc.value.kind == ErrorKind.RATE_LIMITED
    assert exc.value.retryable is True
    assert 0 < exc.value.retry_after_s <= 60


async def test_429_prefers_retry_after_header():
    handler = responding(429, headers={"Retry-After": "30"})
    with pytest.raises(SourceError) as exc:
        await call(connector(handler))
    assert exc.value.kind == ErrorKind.RATE_LIMITED
    assert exc.value.retry_after_s == 30.0


async def test_rate_limited_without_usable_headers_still_classifies():
    with pytest.raises(SourceError) as exc:
        await call(connector(responding(429)))
    assert exc.value.kind == ErrorKind.RATE_LIMITED
    assert exc.value.retry_after_s is None


@pytest.mark.parametrize(
    "exc",
    [httpx.ConnectTimeout("timed out"), httpx.ReadTimeout("timed out"), httpx.ConnectError("refused")],
)
async def test_transport_failures_are_unavailable_and_retryable(exc):
    with pytest.raises(SourceError) as err:
        await call(connector(raising(exc)))
    assert err.value.kind == ErrorKind.UNAVAILABLE
    assert err.value.retryable is True


async def test_error_message_never_contains_the_token():
    with pytest.raises(SourceError) as exc:
        await call(connector(responding(401, json={"message": "Bad credentials"})))
    assert "ghp_test" not in str(exc.value)


# --- input validation happens before any request -----------------------------


@pytest.mark.parametrize("repo", ["", "no-slash", "too/many/parts", "bad repo/name", "owner/"])
async def test_invalid_repo_slug_rejected_without_a_request(repo):
    def explode(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be sent for an invalid slug")

    with pytest.raises(SourceError) as exc:
        await connector(explode).list_open_pulls(repo)
    assert exc.value.kind == ErrorKind.INVALID_INPUT


# --- success paths: trimmed, predictable shapes ------------------------------

PULL_PAYLOAD = [
    {
        "number": 7,
        "title": "Add retry budget",
        "user": {"login": "mando"},
        "updated_at": "2026-09-14T11:02:00Z",
        "draft": False,
        "html_url": "https://github.test/octo/repo/pull/7",
        "body": "ignored",
        "_links": {"self": {"href": "ignored"}},
    }
]


async def test_list_open_pulls_returns_only_documented_fields():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=PULL_PAYLOAD)

    pulls = await connector(handler).list_open_pulls("octo/repo")
    assert pulls == [
        {
            "number": 7,
            "title": "Add retry budget",
            "author": "mando",
            "updated_at": "2026-09-14T11:02:00Z",
            "draft": False,
            "url": "https://github.test/octo/repo/pull/7",
        }
    ]
    assert "/repos/octo/repo/pulls" in seen["url"]
    assert "state=open" in seen["url"]
    assert seen["auth"] == "Bearer ghp_test"


async def test_get_issue_trims_body_and_flattens_labels():
    payload = {
        "number": 12,
        "title": "Deploy fails on locked DB",
        "state": "open",
        "labels": [{"name": "bug"}, {"name": "ops"}],
        "assignees": [{"login": "mando"}],
        "body": "x" * 5000,
        "html_url": "https://github.test/octo/repo/issues/12",
    }
    issue = await connector(responding(200, json=payload)).get_issue("octo/repo", 12)
    assert issue["number"] == 12
    assert issue["labels"] == ["bug", "ops"]
    assert issue["assignees"] == ["mando"]
    assert len(issue["body"]) < 5000
    assert issue["body_truncated"] is True


async def test_get_issue_keeps_short_bodies_intact():
    payload = {"number": 3, "title": "t", "state": "closed", "labels": [], "assignees": [], "body": "short", "html_url": "u"}
    issue = await connector(responding(200, json=payload)).get_issue("octo/repo", 3)
    assert issue["body"] == "short"
    assert issue["body_truncated"] is False


async def test_missing_body_is_handled():
    payload = {"number": 4, "title": "t", "state": "open", "labels": [], "assignees": [], "body": None, "html_url": "u"}
    issue = await connector(responding(200, json=payload)).get_issue("octo/repo", 4)
    assert issue["body"] == ""


@pytest.mark.parametrize("number", [0, -1])
async def test_non_positive_issue_number_rejected(number):
    def explode(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with pytest.raises(SourceError) as exc:
        await connector(explode).get_issue("octo/repo", number)
    assert exc.value.kind == ErrorKind.INVALID_INPUT
