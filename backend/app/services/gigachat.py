"""GigaChat HTTP client for expert-contour session summaries."""

from __future__ import annotations

import json
import logging
import ssl
import threading
import time
import uuid
from pathlib import Path
from typing import Any, cast

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Low temperature keeps rewrites close to the supplied facts.
_CHAT_TEMPERATURE = 0.2
_TOKEN_SKEW_SECONDS = 60
_UNSET: object = object()


class GigaChatError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


SUMMARY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "narrative": {
            "type": "string",
            "description": (
                "Цельный рассказ от лица владельца кинологу: что рассказали "
                "в приюте при передаче (поле history — прошлое до семьи), "
                "факты из dog и наблюдаемое поведение из strengths/concerns. "
                "Без разделов и списков."
            ),
        },
    },
    "required": ["narrative"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
Ты помогаешь кинологу-эксперту понять собаку по анкете и заметкам владельца.

Напиши один цельный рассказ от первого лица владельца («у нас…», «мы заметили…») \
кинологу. Не дели текст на «сильные стороны» и «зоны внимания», не используй \
маркированные списки и заголовки разделов — только связный текст.

Пиши по-русски, живо и по-человечески, без канцелярита. Не используй слова \
«шкала», «домен», «балл из 10» — говори о поведении обычными словами. Цифры \
из фактов можно оставить, если они помогают (сроки, вес и т.п.).

Опирайся только на переданные facts и history:
- поле history — это история собаки до попадания в семью (жизнь в приюте \
и раньше). В рассказе владельца передавай эти факты как то, что ему \
рассказали в приюте при передаче собаки («в приюте сказали…», «при \
выдаче нам сообщили…»), а не как то, что владелец сам наблюдал дома;
- из dog — кто собака сейчас в семье (пол, возраст, порода, статус, сроки \
в статусе и т.п.);
- в facts.dog есть «Пол: …» — согласуй род местоимений и глаголов с полом \
собаки (самка/сука/female → она, привыкла, лает; кобель/male → он, привык, \
лает). Если пола нет — нейтрально («собака», без он/она);
- из facts.strengths и facts.concerns — наблюдаемое поведение по анкете \
уже в семье (спокойные стороны и то, на что стоит обратить внимание); \
вплети в тот же рассказ, без ярлыков «плюс/минус».

Ты только пересказываешь уже сказанное. Не делай умозаключений и не достраивай \
картину: не пиши, что собака «привыкла», «адаптировалась», «освоилась», \
«чувствует себя как дома», «спокойна в новом месте», «всё хорошо» и т.п., \
если этих слов нет в переданных фактах. Из факта «недавно в семье / из \
приюта / N дней» не следует вывод об успехе адаптации — передай срок и \
обстоятельства словами блока dog, а прошлое из history — как слова приюта.

Жёсткие правила:
- ничего не выдумывай и не интерпретируй «между строк»;
- не ставь диагнозов, не назначай препараты и не давай план дрессировки;
- не называй кличку и имя владельца, если их нет в переданных фактах \
(в истории они уже обезличены: «собака», «[владелец]»);
- если history пустое, всё равно расскажи о поведении по facts.strengths и \
facts.concerns и блоку dog; если и фактов мало — короткий честный текст \
без домыслов.

Верни JSON с одним полем narrative.
"""


def _resolve_ca_bundle(ca_bundle: str | None) -> str | None:
    """Return an existing PEM path, or None if CA is not configured.

    Compose sets ``GIGACHAT_CA_BUNDLE=/certs/...``; on the host the same env
    often points at a missing path — fall back to ``certs/<name>`` under cwd
    or the repo root so ``uv run python scripts/...`` works.
    """
    if not ca_bundle or not ca_bundle.strip():
        return None
    configured = Path(ca_bundle).expanduser()
    if configured.is_file():
        return str(configured.resolve())
    name = configured.name
    roots = (
        Path.cwd(),
        Path.cwd().parent,
        Path(__file__).resolve().parents[3],
    )
    for root in roots:
        candidate = root / "certs" / name
        if candidate.is_file():
            logger.info(
                "GigaChat CA: %s not found, using %s",
                ca_bundle,
                candidate,
            )
            return str(candidate.resolve())
    raise GigaChatError(
        f"GigaChat: файл CA не найден ({ca_bundle}). "
        "Положите сертификат в certs/ или укажите существующий "
        "GIGACHAT_CA_BUNDLE."
    )


def _ssl_context(ca_bundle: str | None) -> ssl.SSLContext:
    context = ssl.create_default_context()
    resolved = _resolve_ca_bundle(ca_bundle)
    if resolved:
        context.load_verify_locations(resolved)
    return context


class GigaChatClient:
    def __init__(
        self,
        *,
        auth_key: str | None | object = _UNSET,
        scope: str | None | object = _UNSET,
        model: str | None | object = _UNSET,
        base_url: str | None | object = _UNSET,
        oauth_url: str | None | object = _UNSET,
        ca_bundle: str | None | object = _UNSET,
        timeout: float | None | object = _UNSET,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._auth_key = cast(
            str | None,
            settings.GIGACHAT_AUTH_KEY if auth_key is _UNSET else auth_key,
        )
        self._scope = cast(str, settings.GIGACHAT_SCOPE if scope is _UNSET else scope)
        self._model = cast(str, settings.GIGACHAT_MODEL if model is _UNSET else model)
        raw_base = cast(
            str, settings.GIGACHAT_BASE_URL if base_url is _UNSET else base_url
        )
        self._base_url = raw_base.rstrip("/")
        self._oauth_url = cast(
            str, settings.GIGACHAT_OAUTH_URL if oauth_url is _UNSET else oauth_url
        )
        self._ca_bundle = cast(
            str | None,
            settings.GIGACHAT_CA_BUNDLE if ca_bundle is _UNSET else ca_bundle,
        )
        self._timeout = cast(
            float,
            settings.GIGACHAT_TIMEOUT_SECONDS if timeout is _UNSET else timeout,
        )
        self._transport = transport
        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    @property
    def model(self) -> str:
        return self._model

    @property
    def enabled(self) -> bool:
        return bool(self._auth_key)

    def _client(self) -> httpx.Client:
        kwargs: dict[str, Any] = {
            "timeout": self._timeout,
            "verify": _ssl_context(self._ca_bundle),
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def _request_token(self) -> tuple[str, float]:
        if not self._auth_key:
            raise GigaChatError("GigaChat не настроен")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self._auth_key}",
        }
        try:
            with self._client() as client:
                response = client.post(
                    self._oauth_url,
                    headers=headers,
                    data={"scope": self._scope},
                )
        except httpx.HTTPError as exc:
            logger.warning("GigaChat OAuth transport error: %s", type(exc).__name__)
            raise GigaChatError("GigaChat недоступен") from exc
        if response.status_code >= 400:
            logger.warning("GigaChat OAuth status=%s", response.status_code)
            raise GigaChatError(
                "GigaChat: ошибка авторизации",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise GigaChatError("GigaChat: некорректный ответ OAuth") from exc
        token = payload.get("access_token")
        expires_at_ms = payload.get("expires_at")
        if not isinstance(token, str) or not token:
            raise GigaChatError("GigaChat: в ответе OAuth нет access_token")
        if isinstance(expires_at_ms, int | float):
            expires_at = float(expires_at_ms) / 1000.0
        else:
            expires_at = time.time() + 25 * 60
        return token, expires_at

    def _get_token(self) -> str:
        with self._lock:
            if (
                self._access_token
                and time.time() < self._token_expires_at - _TOKEN_SKEW_SECONDS
            ):
                return self._access_token
            token, expires_at = self._request_token()
            self._access_token = token
            self._token_expires_at = expires_at
            return token

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        model: str | None = None,
    ) -> str:
        token = self._get_token()
        body = {
            "model": (model or self._model).strip() or self._model,
            "temperature": _CHAT_TEMPERATURE,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "schema": schema,
                "strict": True,
            },
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        url = f"{self._base_url}/chat/completions"
        try:
            with self._client() as client:
                response = client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            logger.warning("GigaChat chat transport error: %s", type(exc).__name__)
            raise GigaChatError("GigaChat недоступен") from exc
        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    message = payload.get("message")
                    if isinstance(message, str) and message.strip():
                        detail = message.strip()
            except ValueError:
                detail = ""
            logger.warning(
                "GigaChat chat status=%s detail=%s",
                response.status_code,
                detail or "-",
            )
            suffix = f" ({detail})" if detail else ""
            raise GigaChatError(
                f"GigaChat: ошибка генерации{suffix}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise GigaChatError("GigaChat: некорректный JSON ответа") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GigaChatError("GigaChat: пустой ответ модели") from exc
        if isinstance(content, list):
            parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            content = "".join(parts)
        if not isinstance(content, str) or not content.strip():
            raise GigaChatError("GigaChat: пустой ответ модели")
        return content

    def rewrite_summary(
        self,
        *,
        facts_payload: dict[str, Any],
        anonymized_history: str,
        model: str | None = None,
    ) -> str:
        user = json.dumps(
            {
                "facts": facts_payload,
                "history": anonymized_history,
            },
            ensure_ascii=False,
        )
        return self.chat_json(
            system=SYSTEM_PROMPT,
            user=user,
            schema=SUMMARY_JSON_SCHEMA,
            model=model,
        )


def get_client() -> GigaChatClient:
    return GigaChatClient()
