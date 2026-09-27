import hashlib
import hmac

import pytest
from fastapi import HTTPException, Request

from app.security import verify_signature

SECRET = "test-secret"


def _make_request(body: bytes, signature: str | None) -> Request:
    headers = []
    if signature is not None:
        headers.append((b"x-hub-signature-256", signature.encode()))

    scope = {
        "type": "http",
        "headers": headers,
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_valid_signature_passes():
    body = b'{"action": "opened"}'
    signature = _sign(body, SECRET)
    request = _make_request(body, signature)

    result = await verify_signature(request, SECRET)
    assert result == body


@pytest.mark.asyncio
async def test_invalid_signature_raises_401():
    body = b'{"action": "opened"}'
    wrong_signature = _sign(body, "wrong-secret")
    request = _make_request(body, wrong_signature)

    with pytest.raises(HTTPException) as exc_info:
        await verify_signature(request, SECRET)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_signature_header_raises_401():
    body = b'{"action": "opened"}'
    request = _make_request(body, None)

    with pytest.raises(HTTPException) as exc_info:
        await verify_signature(request, SECRET)
    assert exc_info.value.status_code == 401
