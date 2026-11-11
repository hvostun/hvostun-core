import { useState, type FormEvent } from "react"
import { Link, Navigate, useNavigate } from "react-router"
import { ApiError } from "../api"
import { consentUrl } from "../config"
import { Button } from "../components/Button"
import { ErrorBanner } from "../components/ErrorBanner"
import { Icon } from "../icons/Icon"
import { TeamLink } from "../components/TeamLink"
import { useUser } from "../state/UserState"

export function Login() {
  const { me, api, refresh } = useUser()
  const navigate = useNavigate()
  const [login, setLogin] = useState("")
  const [password, setPassword] = useState("")
  const [consent, setConsent] = useState(false)
  const [show, setShow] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(false)
  if (me) return <Navigate to="/" replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!consent || pending) return
    setPending(true)
    setError(false)
    try {
      await api.login(login, password, consent)
      await refresh()
      await navigate("/")
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "E2") setError(true)
    } finally {
      setPending(false)
    }
  }

  const consentText = "согласие на обработку персональных данных"
  return (
    <div className="app blue">
      <section className="screen blue">
        <header className="top">
          <Link className="round" to="/welcome" aria-label="Назад">
            <Icon name="back" />
          </Link>
        </header>
        <form className="pad" onSubmit={(event) => void submit(event)}>
          <h1 className="hero">Вход</h1>
          {error ? <ErrorBanner>Логин или пароль не подошли</ErrorBanner> : null}
          <label className="field">
            Логин
            <input className="input" name="login" autoComplete="username" value={login} disabled={pending} onChange={(event) => setLogin(event.target.value)} />
          </label>
          <div className="field">
            <label htmlFor="password">Пароль</label>
            <span className="password">
              <input id="password" className="input" name="password" type={show ? "text" : "password"} autoComplete="current-password" value={password} disabled={pending} onChange={(event) => setPassword(event.target.value)} />
              <button type="button" className="round" aria-label="Показать пароль" onClick={() => setShow((current) => !current)}>
                <Icon name="eye" />
              </button>
            </span>
          </div>
          <label className="consent">
            <input type="checkbox" checked={consent} disabled={pending} onChange={(event) => setConsent(event.target.checked)} />
            <span>
              Даю{" "}
              {consentUrl ? (
                <a href={consentUrl} target="_blank" rel="noreferrer">
                  {consentText}
                </a>
              ) : (
                consentText
              )}
            </span>
          </label>
          <Button type="submit" block disabled={!consent || pending}>
            {pending ? "Вход…" : "Войти"}
          </Button>
          <TeamLink screen="S2" />
        </form>
      </section>
    </div>
  )
}
