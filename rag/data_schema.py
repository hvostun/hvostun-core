from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    """One body for both RAG and no-RAG (`mode=bypass`) so the same JSON can be compared."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "Как приучить щенка к поводку?",
                    "mode": "hybrid",
                    "system_prompt": "Please answer in Russian and format your response as a bulleted list.",
                },
                {
                    "query": "Как приучить щенка к поводку?",
                    "mode": "bypass",
                    "system_prompt": "Please answer in Russian and format your response as a bulleted list.",
                },
            ]
        }
    )

    query: str = Field(description="Текст вопроса.")
    mode: Literal["hybrid", "local", "global", "mix", "naive", "bypass"] = Field(
        "hybrid",
        description=(
            "Режим LightRAG. \nhybrid, local, global, mix, naive — ответ по индексу. "
            "\nbypass — тот же GigaChat без retrieval (baseline). "
            "\nВ bypass учитываются только query, system_prompt и conversation_history."
        ),
    )
    system_prompt: str | None = Field(
        None,
        description="Системная инструкция. Учитывается и в RAG, и в bypass.",
    )
    temperature: float | None = Field(
        None,
        description="Не применяется: прокидывание в LightRAG закомментировано (и RAG, и bypass).",
    )
    max_tokens: int | None = Field(
        None,
        description="Не применяется: прокидывание в LightRAG закомментировано (и RAG, и bypass).",
    )
    top_k: int | None = Field(
        None,
        description="Ширина retrieval (сущности или связи). В bypass игнорируется.",
    )
    chunk_top_k: int | None = Field(
        None,
        description="Сколько текстовых чанков оставить после retrieval. В bypass игнорируется.",
    )
    only_need_context: bool = Field(
        False,
        description="Вернуть найденный контекст вместо ответа. В bypass игнорируется.",
    )
    response_type: str | None = Field(
        None,
        description='Формат ответа RAG, например "Bullet Points". В bypass игнорируется.',
    )
    conversation_history: list[dict[str, Any]] | None = Field(
        None,
        description=(
            'История [{"role", "content"}]. Учитывается и в RAG, и в bypass. '
            "Пример Swagger без role/content отбрасывается."
        ),
    )
    user_prompt: str | None = Field(
        None,
        description="Дополнительные инструкции в промпт RAG. В bypass игнорируются.",
    )
