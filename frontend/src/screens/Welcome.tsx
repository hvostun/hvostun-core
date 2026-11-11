import { Link, Navigate } from "react-router"
import skate from "../../design/illustrations/skate-cream.svg"
import { TeamLink } from "../components/TeamLink"
import { useUser } from "../state/UserState"

export function Welcome() {
  const { me } = useUser()
  if (me) return <Navigate to="/" replace />
  return (
    <div className="app blue">
      <section className="screen blue">
        <div className="pad">
          <img className="art" src={skate} alt="" />
          <h1 className="hero">Помогаем собаке стать своей</h1>
          <p>
            Сервис поддержки владельцев собак в период адаптации питомца в новом доме. Не сделать собаку удобной, а
            научиться понимать друг друга.
          </p>
          <Link className="btn btn-primary btn-block" to="/login">
            Войти
          </Link>
        </div>
        <div className="center-note">
          <TeamLink screen="S1" />
        </div>
      </section>
    </div>
  )
}
