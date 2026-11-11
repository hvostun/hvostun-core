import { useEffect, useState } from "react"
import { useNavigate } from "react-router"
import { ageOptions, firstDogOptions, labelOf, originOptions, sexOptions, type DogProfile } from "../api/types"
import { Button } from "../components/Button"
import bow from "../../design/illustrations/bow-cream.svg"
import { TeamLink } from "../components/TeamLink"
import { formatDate } from "../state/profileRules"
import { useUser } from "../state/UserState"

export function ProfileView() {
  const { api, refresh } = useUser()
  const navigate = useNavigate()
  const [profile, setProfile] = useState<DogProfile | null>(null)
  useEffect(() => {
    void api.getProfile().then(setProfile)
  }, [api])
  if (!profile) return null
  const rows = [
    ["Кличка", profile.name],
    ["Возраст", labelOf(ageOptions, profile.age)],
    ["Пол", labelOf(sexOptions, profile.sex)],
    ["Дома с", formatDate(profile.home_since)],
    ["Откуда", labelOf(originOptions, profile.origin)],
    ["Первая собака", labelOf(firstDogOptions, profile.first_dog)],
  ]
  return (
    <div className="pad">
      <img className="art" src={bow} alt="" />
      <h1 className="h-block">Профиль питомца</h1>
      {rows.map(([label, value]) => (
        <p key={label}>
          <span className="caption">{label}</span>
          <br />
          {value}
        </p>
      ))}
      <h2 className="h-block">Аккаунт</h2>
      <TeamLink screen="S4b" />
      <Button
        variant="secondary"
        onClick={() => {
          void (async () => {
            await api.logout()
            await refresh()
            await navigate("/welcome")
          })()
        }}
      >
        Выйти
      </Button>
    </div>
  )
}
