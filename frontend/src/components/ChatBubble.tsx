import type { ChatMessage } from "../api/types"
import { Button } from "./Button"

export function ChatBubble({
  message,
  onRate,
  onRetry,
  onDelete,
}: {
  message: ChatMessage
  onRate: (id: string, rating: "up" | "down" | null) => void
  onRetry: (message: ChatMessage) => void
  onDelete: (id: string) => void
}) {
  if (message.role === "user") {
    return (
      <div className="bubble" data-kind="user" data-status={message.status}>
        <div className={message.status === "failed" ? "msg-me failed" : "msg-me"}>{message.text}</div>
        {message.status === "failed" ? (
          <div className="row-actions">
            <span>Не отправлено</span>
            <Button variant="secondary" onClick={() => onRetry(message)}>
              Повторить
            </Button>
            <Button variant="secondary" onClick={() => onDelete(message.id)}>
              Удалить
            </Button>
          </div>
        ) : null}
        {message.status === "timeout" ? (
          <div className="row-actions">
            <span>Не удалось получить ответ</span>
            <Button variant="secondary" onClick={() => onRetry(message)}>
              Повторить
            </Button>
          </div>
        ) : null}
      </div>
    )
  }
  return (
    <div className="bubble" data-kind={message.kind ?? "greeting"}>
      <div className={message.kind === "urgent" ? "msg-ai urgent" : "msg-ai"}>{message.text}</div>
      {message.kind === "answer" ? (
        <div className="rate">
          <button type="button" aria-pressed={message.rating === "up"} onClick={() => onRate(message.id, message.rating === "up" ? null : "up")}>
            Полезно
          </button>
          <button type="button" aria-pressed={message.rating === "down"} onClick={() => onRate(message.id, message.rating === "down" ? null : "down")}>
            Неполезно
          </button>
        </div>
      ) : null}
    </div>
  )
}
