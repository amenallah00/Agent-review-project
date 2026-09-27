import httpx
import pytest

from app.rate_limit import request_with_retry


def _make_client(responses: list[httpx.Response]) -> httpx.AsyncClient:
    """Fabrique un client httpx dont le transport renvoie les réponses fournies, une par appel."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        return responses[index]

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    client._test_call_count = call_count  # pour inspection dans les tests
    return client


@pytest.mark.asyncio
async def test_succeeds_immediately_when_no_rate_limit(monkeypatch):
    responses = [httpx.Response(200, json={"ok": True})]
    client = _make_client(responses)

    resp = await request_with_retry(client, "GET", "https://api.github.com/test", headers={})
    assert resp.status_code == 200
    assert client._test_call_count["n"] == 1


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds(monkeypatch):
    # On accélère le test : pas de vraie attente
    async def fast_sleep(_seconds):
        return None
    monkeypatch.setattr("app.rate_limit.asyncio.sleep", fast_sleep)

    responses = [
        httpx.Response(429, headers={"retry-after": "1"}, json={"message": "rate limited"}),
        httpx.Response(200, json={"ok": True}),
    ]
    client = _make_client(responses)

    resp = await request_with_retry(client, "POST", "https://api.github.com/test", headers={}, max_retries=3)
    assert resp.status_code == 200
    assert client._test_call_count["n"] == 2


@pytest.mark.asyncio
async def test_retries_on_secondary_rate_limit_403(monkeypatch):
    async def fast_sleep(_seconds):
        return None
    monkeypatch.setattr("app.rate_limit.asyncio.sleep", fast_sleep)

    responses = [
        httpx.Response(403, json={"message": "You have exceeded a secondary rate limit"}),
        httpx.Response(200, json={"ok": True}),
    ]
    client = _make_client(responses)

    resp = await request_with_retry(client, "POST", "https://api.github.com/test", headers={}, max_retries=3)
    assert resp.status_code == 200
    assert client._test_call_count["n"] == 2


@pytest.mark.asyncio
async def test_does_not_retry_on_normal_403_forbidden(monkeypatch):
    """Un 403 'classique' (permissions insuffisantes) ne doit PAS être traité comme un rate limit."""
    responses = [httpx.Response(403, json={"message": "Resource not accessible by integration"})]
    client = _make_client(responses)

    resp = await request_with_retry(client, "GET", "https://api.github.com/test", headers={}, max_retries=3)
    assert resp.status_code == 403
    assert client._test_call_count["n"] == 1  # aucune retry, échec immédiat


@pytest.mark.asyncio
async def test_gives_up_after_max_retries(monkeypatch):
    async def fast_sleep(_seconds):
        return None
    monkeypatch.setattr("app.rate_limit.asyncio.sleep", fast_sleep)

    responses = [httpx.Response(429, json={"message": "rate limited"})]  # toujours rate limited
    client = _make_client(responses)

    resp = await request_with_retry(client, "GET", "https://api.github.com/test", headers={}, max_retries=2)
    assert resp.status_code == 429
    assert client._test_call_count["n"] == 3  # tentative initiale + 2 retries
