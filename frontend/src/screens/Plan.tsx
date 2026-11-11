import { Navigate } from "react-router"
import leash from "../../design/illustrations/leash-blue.svg"
import { useUser } from "../state/UserState"

export function Plan() {
  const { me } = useUser()
  if (me && me.survey_status !== "done") return <Navigate to="/" replace />
  return (
    <div className="pad">
      <img className="art" src={leash} alt="" />
      <h1 className="h-block">Сервис в разработке</h1>
    </div>
  )
}
