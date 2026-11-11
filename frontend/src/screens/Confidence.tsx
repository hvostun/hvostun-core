import { useState } from "react"
import { Navigate, useNavigate } from "react-router"
import { Button } from "../components/Button"
import { useUser } from "../state/UserState"

export function Confidence() {
  const { api, me, refresh } = useUser()
  const navigate = useNavigate()
  const [value, setValue] = useState<number | null>(null)
  const [pending, setPending] = useState(false)
  if (me && me.survey_status === "none") return <Navigate to="/" replace />

  async function close() {
    if (value !== null) await api.saveAnswer(value)
    await refresh()
    await navigate("/")
  }

  async function next() {
    if (value === null || pending) return
    setPending(true)
    await api.saveAnswer(value)
    await api.finishSurvey()
    await refresh()
    await navigate("/plan")
  }

  return (
    <div className="pad">
      <header className="top">
        <button type="button" className="round" aria-label="Закрыть" onClick={() => void close()}>
          ×
        </button>
      </header>
      <p className="caption">Шаг 0 из 20</p>
      <h1 className="h-block">Насколько вы уверены в своих действиях по уходу за собакой и ее воспитанию?</h1>
      <div className="scale" role="radiogroup" aria-label="Уверенность">
        {Array.from({ length: 11 }, (_, index) => (
          <button key={index} type="button" className={value === index ? "on" : undefined} aria-checked={value === index} role="radio" onClick={() => setValue(index)}>
            {index}
          </button>
        ))}
      </div>
      <p className="caption">совсем не уверен(а) — полностью уверен(а)</p>
      <Button block disabled={value === null || pending} onClick={() => void next()}>
        Далее
      </Button>
    </div>
  )
}
