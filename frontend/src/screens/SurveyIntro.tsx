import { Navigate, useNavigate } from "react-router"
import hug from "../../design/illustrations/hug-blue.svg"
import { Button } from "../components/Button"
import { useUser } from "../state/UserState"

export function SurveyIntro() {
  const { api, me, refresh } = useUser()
  const navigate = useNavigate()
  if (me && me.profile_status !== "done") return <Navigate to="/" replace />
  return (
    <div className="pad">
      <img className="art" src={hug} alt="" />
      <h1 className="h-block">Анкета адаптации питомца</h1>
      <p>
        Анкета займёт около 15 минут. Ответы помогут нам составить план адаптации, который вы увидите в приложении
        после заполнения.
      </p>
      <Button
        block
        onClick={() => {
          void (async () => {
            await api.startSurvey()
            await refresh()
            await navigate("/survey/confidence")
          })()
        }}
      >
        Заполнить анкету
      </Button>
    </div>
  )
}
