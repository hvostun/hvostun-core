import letter from "../../design/illustrations/letter-cream.svg"
import { Button } from "../components/Button"

export function ServiceDown({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="app blue">
      <section className="screen blue">
        <div className="pad">
          <img className="art" src={letter} alt="" />
          <h1 className="hero">Сервис временно недоступен. Попробуйте позже.</h1>
          <Button onClick={onRetry}>Повторить</Button>
        </div>
      </section>
    </div>
  )
}
