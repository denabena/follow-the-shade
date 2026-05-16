"""Tests for GET /places/photo proxy."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.config import settings
from services.places.photo_token import encode_place_photo_p


def test_place_photo_rejects_invalid_token() -> None:
    with TestClient(app) as client:
        r = client.get("/places/photo", params={"p": "not-a-valid-token"})
    assert r.status_code == 400


def test_place_photo_rejects_empty_p() -> None:
    with TestClient(app) as client:
        r = client.get("/places/photo", params={"p": ""})
    assert r.status_code == 400


def test_place_photo_503_when_no_google_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", None)
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", None)
    p = encode_place_photo_p(variant="legacy", ref="photo_ref_test")
    assert p is not None
    with TestClient(app) as client:
        r = client.get("/places/photo", params={"p": p})
    assert r.status_code == 503


def test_place_photo_streams_bytes_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "unit-test-key")
    p = encode_place_photo_p(variant="legacy", ref="ref-xyz")
    assert p is not None

    async def fake_fetch(api_key: str, spec: dict) -> tuple[bytes, str]:
        assert api_key == "unit-test-key"
        assert spec.get("v") == "legacy"
        assert spec.get("ref") == "ref-xyz"
        return b"\xff\xd8\xff", "image/jpeg"

    with (
        patch(
            "app.api.places.routes.fetch_place_photo_bytes",
            new_callable=AsyncMock,
            side_effect=fake_fetch,
        ),
        TestClient(app) as client,
    ):
        r = client.get("/places/photo", params={"p": p})

    assert r.status_code == 200
    assert r.content == b"\xff\xd8\xff"
    assert "image/jpeg" in (r.headers.get("content-type") or "")
