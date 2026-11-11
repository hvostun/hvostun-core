import { Link } from "react-router"
import { Icon, type IconName } from "../icons/Icon"
import { greeting, screenAccess } from "../state/access"
import { TeamLink } from "../components/TeamLink"
import { useUser } from "../state/UserState"

const LOCKED = "Откроется после заполнения профиля"

export function Home() {
  const { me } = useUser()
  if (!me) return null
  const access = screenAccess(me)
  const profileDone = me.profile_status === "done"
  const planLocked = !profileDone
  const chatLocked = !profileDone
  const planTo = me.survey_status === "started" ? "/survey/confidence" : me.survey_status === "done" ? "/plan" : "/survey"
  const planNote = me.survey_status === "started" ? `Шаг ${me.survey_step} из 20, продолжить` : planLocked ? LOCKED : undefined

  return (
    <div className="pad">
      <h1 className={profileDone ? "name" : "hello"}>{greeting(me)}</h1>
      {access.next ? (
        <Link className="next" to={access.next.to} data-testid="next-step">
          <span>
            <span className="k">Следующий шаг</span>
            <span className="t">{access.next.text}</span>
          </span>
          <span className="arrow">
            <Icon name="forward" />
          </span>
        </Link>
      ) : null}
      <div className="stack">
        <Card icon="paw" tile="profile" title="Профиль" to={profileDone ? "/profile" : "/profile/edit"} />
        <Card icon="plan" tile="plan" title="План адаптации" to={planTo} locked={planLocked} note={planNote} />
        <Card icon="chat" tile="chat" title="Чат" to="/chat" locked={chatLocked} note={chatLocked ? LOCKED : undefined} />
        <Card icon="vet" tile="plan" title="Специалист" locked note="Консультация специалиста. Сервис в разработке." />
      </div>
      <TeamLink screen="S3" />
    </div>
  )
}

function Card({
  icon,
  tile,
  title,
  to,
  locked,
  note,
}: {
  icon: IconName
  tile: string
  title: string
  to?: string
  locked?: boolean
  note?: string
}) {
  const body = (
    <>
      <span className={`tile ${tile}`}>
        <Icon name={locked ? "lock" : icon} />
      </span>
      <span>
        <span className="h-block">{title}</span>
        {note ? <span className="caption">{note}</span> : null}
      </span>
    </>
  )
  if (locked || !to) return <div className="card off">{body}</div>
  return (
    <Link className="card" to={to}>
      {body}
    </Link>
  )
}
