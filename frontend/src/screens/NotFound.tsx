import { Link } from "react-router"

export function NotFound() {
  return (
    <div className="pad">
      <h1 className="h-block">Такой страницы нет</h1>
      <Link className="btn btn-primary" to="/">
        На главную
      </Link>
    </div>
  )
}
