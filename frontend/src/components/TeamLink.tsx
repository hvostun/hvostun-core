import { teamUrl } from "../config"

export function TeamLink({ screen }: { screen: string }) {
  if (!teamUrl) return null
  return (
    <a className="link-quiet" href={teamUrl} target="_blank" rel="noreferrer" data-screen={screen}>
      Написать команде
    </a>
  )
}
