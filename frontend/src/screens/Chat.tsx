import { useEffect, useState } from "react"
import { Navigate } from "react-router"
import pattern from "../../design/illustrations/chat-pattern.svg"
import type { ChatMessage, Fault } from "../api/types"
import { BottomSheet } from "../components/BottomSheet"
import { Button } from "../components/Button"
import { ChatBubble } from "../components/ChatBubble"
import { Icon } from "../icons/Icon"
import { useUser } from "../state/UserState"

export function Chat() {
  const { api, me } = useUser()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [text, setText] = useState("")
  const [typing, setTyping] = useState(false)
  const [sheetFor, setSheetFor] = useState<string | null>(null)
  const [comment, setComment] = useState("")

  useEffect(() => {
    if (me && me.profile_status !== "done") return
    void api.listMessages().then(setMessages)
    void api.track("chat_open", "S10")
  }, [api, me])

  async function send(value = text) {
    const body = value.trim()
    if (!body || typing) return
    setTyping(true)
    try {
      setMessages(await api.sendMessage(body))
      setText("")
    } finally {
      setTyping(false)
    }
  }

  async function rate(id: string, rating: "up" | "down" | null) {
    await api.setFeedback(id, rating, rating === "down" ? "" : "")
    setMessages(await api.listMessages())
    if (rating === "down") {
      setComment("")
      setSheetFor(id)
    } else setSheetFor(null)
  }

  async function sendComment() {
    if (!sheetFor || !comment.trim()) return
    await api.setFeedback(sheetFor, "down", comment.trim().slice(0, 500))
    setMessages(await api.listMessages())
    setSheetFor(null)
  }

  async function retry(message: ChatMessage) {
    if (typing) return
    setTyping(true)
    try {
      await api.deleteMessage(message.id)
      setMessages(await api.sendMessage(message.text))
    } finally {
      setTyping(false)
    }
  }

  function setFault(fault: Fault) {
    api.setFault?.(fault)
  }

  if (me && me.profile_status !== "done") return <Navigate to="/" replace />

  return (
    <div className="chat-screen" style={{ ["--chat-pattern" as string]: `url("${pattern}")` }}>
      <p className="disclaimer">Чат не заменяет ветеринара или кинолога. В экстренной ситуации обратитесь к специалисту.</p>
      {import.meta.env.DEV ? (
        <div className="faults">
          <Button variant="secondary" onClick={() => setFault("send")}>Сбой отправки</Button>
          <Button variant="secondary" onClick={() => setFault("timeout")}>Сбой ответа</Button>
          <Button variant="secondary" onClick={() => setFault("none")}>Без сбоя</Button>
        </div>
      ) : null}
      <div className="chat-scroll">
        {messages.map((message) => (
          <ChatBubble key={message.id} message={message} onRate={(id, rating) => void rate(id, rating)} onRetry={(item) => void retry(item)} onDelete={(id) => void api.deleteMessage(id).then(setMessages)} />
        ))}
        {typing ? <p className="caption">Печатает…</p> : null}
      </div>
      <div className="composer-wrap">
        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault()
            void send()
          }}
        >
          <textarea aria-label="Сообщение" value={text} disabled={typing} rows={1} onChange={(event) => setText(event.target.value)} />
          <button className="send" type="submit" aria-label="Отправить" disabled={typing || !text.trim()}>
            <Icon name="send" />
          </button>
        </form>
        <p className="ai-note">ИИ может ошибаться</p>
      </div>
      {sheetFor ? (
        <BottomSheet title="Что не так?" onClose={() => setSheetFor(null)}>
          <textarea aria-label="Что не так?" maxLength={500} value={comment} onChange={(event) => setComment(event.target.value.slice(0, 500))} />
          <Button block disabled={!comment.trim()} onClick={() => void sendComment()}>
            Отправить
          </Button>
        </BottomSheet>
      ) : null}
    </div>
  )
}
