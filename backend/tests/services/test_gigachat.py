import json
from pathlib import Path

import httpx
import pytest

from app.services.gigachat import (
    SUMMARY_JSON_SCHEMA,
    GigaChatClient,
    GigaChatError,
    _resolve_ca_bundle,
)


def _oauth_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "access_token": "token-1",
            "expires_at": 4_000_000_000_000,
        },
    )


def _client(handler: httpx.MockTransport | object, **kwargs: object) -> GigaChatClient:
    defaults: dict[str, object] = {
        "auth_key": "test-key",
        "model": "GigaChat-2-Max",
        "base_url": "https://api.giga.chat/v1",
        "oauth_url": "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        "scope": "GIGACHAT_API_PERS",
        "ca_bundle": None,
        "transport": handler,
    }
    defaults.update(kwargs)
    return GigaChatClient(**defaults)  # type: ignore[arg-type]


def test_oauth_cached_and_chat_sends_schema() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/oauth"):
            assert request.headers["Authorization"] == "Basic test-key"
            assert request.headers["RqUID"]
            assert b"scope=GIGACHAT_API_PERS" in request.content
            return _oauth_response()
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["Authorization"] == "Bearer token-1"
        body = json.loads(request.content.decode())
        assert body["model"] in {"GigaChat-2-Max", "GigaChat-2-Pro"}
        seen_models.append(body["model"])
        assert body["response_format"] == {
            "type": "json_schema",
            "schema": SUMMARY_JSON_SCHEMA,
            "strict": True,
        }
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {"narrative": "У нас тест."},
                                ensure_ascii=False,
                            ),
                        }
                    }
                ]
            },
        )

    seen_models: list[str] = []
    client = _client(httpx.MockTransport(handler))
    first = client.rewrite_summary(
        facts_payload={"overview": ["Excitability: 5.00 из 10"]},
        anonymized_history="",
    )
    second = client.chat_json(
        system="sys",
        user="user",
        schema=SUMMARY_JSON_SCHEMA,
        model="GigaChat-2-Pro",
    )
    assert "У нас тест." in first
    assert "У нас тест." in second
    assert seen_models == ["GigaChat-2-Max", "GigaChat-2-Pro"]
    assert calls.count("/api/v2/oauth") == 1
    assert sum(1 for path in calls if path.endswith("/chat/completions")) == 2


def test_chat_500_raises_gigachat_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth"):
            return _oauth_response()
        return httpx.Response(500, json={"error": "boom"})

    client = _client(httpx.MockTransport(handler))
    with pytest.raises(GigaChatError) as exc_info:
        client.rewrite_summary(facts_payload={}, anonymized_history="")
    assert exc_info.value.status_code == 500


def test_disabled_without_key() -> None:
    client = _client(
        httpx.MockTransport(lambda _request: _oauth_response()),
        auth_key=None,
    )
    assert client.enabled is False
    with pytest.raises(GigaChatError, match="не настроен"):
        client.rewrite_summary(facts_payload={}, anonymized_history="")


def test_resolve_ca_bundle_falls_back_to_repo_certs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    certs = tmp_path / "certs"
    certs.mkdir()
    pem = certs / "custom-ca.pem"
    pem.write_text("dummy\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    resolved = _resolve_ca_bundle("/certs/custom-ca.pem")
    assert resolved == str(pem.resolve())


def test_resolve_ca_bundle_missing_raises() -> None:
    with pytest.raises(GigaChatError, match="файл CA не найден"):
        _resolve_ca_bundle("/nonexistent/path/missing-ca.pem")
