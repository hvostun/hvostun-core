import { useEffect, useState } from "react"
import { Navigate, useNavigate } from "react-router"
import { ageOptions, emptyProfile, firstDogOptions, originOptions, sexOptions, type DogProfile } from "../api/types"
import { Button } from "../components/Button"
import { Chips } from "../components/Chips"
import { DatePicker } from "../components/DatePicker"
import { Field } from "../components/Field"
import { Icon } from "../icons/Icon"
import { draftHandler } from "../state/draft"
import { profileErrors } from "../state/profileRules"
import { useUser } from "../state/UserState"

export function ProfileForm() {
  const { api, me, refresh } = useUser()
  const navigate = useNavigate()
  const [profile, setProfile] = useState<DogProfile>(emptyProfile)
  const [submitted, setSubmitted] = useState(false)
  const [pending, setPending] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    void api.getProfile().then((saved) => {
      setProfile(saved)
      setReady(true)
    })
  }, [api])

  useEffect(() => {
    draftHandler.current = async () => {
      await api.saveDraft(profile)
    }
    return () => {
      draftHandler.current = null
    }
  }, [api, profile])

  const errors = submitted ? profileErrors(profile) : {}

  function update<K extends keyof DogProfile>(key: K, value: DogProfile[K]) {
    setProfile((current) => ({ ...current, [key]: value }))
  }

  async function back() {
    await api.saveDraft(profile)
    await refresh()
    await navigate("/")
  }

  async function submit() {
    setSubmitted(true)
    const found = profileErrors(profile)
    const key = (Object.keys(found) as (keyof DogProfile)[])[0]
    if (key) {
      document.getElementById(`field-${key}`)?.scrollIntoView?.({ block: "center" })
      return
    }
    setPending(true)
    await api.saveProfile(profile)
    await refresh()
    await navigate("/")
  }

  if (me?.profile_status === "done") return <Navigate to="/profile" replace />
  if (!ready) return null
  return (
    <div className="pad">
      <header className="top">
        <button type="button" className="round" aria-label="Назад" onClick={() => void back()}>
          <Icon name="back" />
        </button>
      </header>
      <h1 className="h-block">Профиль питомца</h1>
      <Field label="Кличка" error={errors.name}>
        <div id="field-name">
          <input className="input" aria-label="Кличка" value={profile.name} disabled={pending} onChange={(event) => update("name", event.target.value)} />
        </div>
      </Field>
      <Field label="Возраст" error={errors.age}>
        <div id="field-age">
          <Chips label="Возраст" options={ageOptions} value={profile.age} disabled={pending} onChange={(value) => update("age", value)} />
        </div>
      </Field>
      <Field label="Пол" error={errors.sex}>
        <div id="field-sex">
          <Chips label="Пол" options={sexOptions} value={profile.sex} disabled={pending} onChange={(value) => update("sex", value)} />
        </div>
      </Field>
      <Field label="Когда собака появилась дома" error={errors.home_since}>
        <div id="field-home_since">
          <DatePicker value={profile.home_since} disabled={pending} onChange={(value) => update("home_since", value)} />
        </div>
      </Field>
      <Field label="Откуда собака" error={errors.origin}>
        <div id="field-origin">
          <Chips label="Откуда собака" options={originOptions} value={profile.origin} disabled={pending} onChange={(value) => update("origin", value)} />
        </div>
      </Field>
      <Field label="Это ваша первая собака?" error={errors.first_dog}>
        <div id="field-first_dog">
          <Chips label="Это ваша первая собака?" options={firstDogOptions} value={profile.first_dog} disabled={pending} onChange={(value) => update("first_dog", value)} />
        </div>
      </Field>
      <div className="form-actions">
        <Button block disabled={pending} onClick={() => void submit()}>
          {pending ? "Сохранение…" : "Готово"}
        </Button>
      </div>
      </div>
  )
}
