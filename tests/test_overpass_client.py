import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from services.geodata.overpass_client import OverpassClient


def _json_response(
    method: str, url: str, status_code: int, payload: dict
) -> httpx.Response:
    return httpx.Response(
        status_code,
        request=httpx.Request(method, url),
        json=payload,
    )


def _text_response(
    method: str, url: str, status_code: int, text: str
) -> httpx.Response:
    return httpx.Response(
        status_code,
        request=httpx.Request(method, url),
        text=text,
    )


def test_overpass_retries_with_get_when_post_text_is_rejected() -> None:
    client = OverpassClient(
        "https://primary.example/api/interpreter",
        fallback_urls=(),
    )

    with (
        patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=_text_response(
                "POST",
                "https://primary.example/api/interpreter",
                406,
                "Not acceptable",
            ),
        ) as post_mock,
        patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=_json_response(
                "GET",
                "https://primary.example/api/interpreter",
                200,
                {"elements": [{"type": "node", "id": 1, "lat": 43.5, "lon": 16.4}]},
            ),
        ) as get_mock,
    ):
        data = asyncio.run(client._post("[out:json];node(0,0,1,1);out;"))

    assert post_mock.await_count == 1
    assert get_mock.await_count == 1
    assert data["elements"][0]["id"] == 1


def test_fetch_buildings_query_skips_relation_buildings() -> None:
    client = OverpassClient("https://primary.example/api/interpreter", fallback_urls=())

    with patch.object(
        OverpassClient,
        "_post",
        new_callable=AsyncMock,
        return_value={"elements": []},
    ) as post_mock:
        asyncio.run(client.fetch_buildings({"lat": 43.5081, "lng": 16.4391}))

    sent_query = post_mock.await_args.args[0]
    assert 'relation["building"]' not in sent_query
    assert 'way["building"]' in sent_query
