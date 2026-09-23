import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { SessionsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export const Route = createFileRoute("/_layout/sessions_/$sessionId")({
  component: SessionPage,
  head: () => ({ meta: [{ title: "Ответ — Hvostun" }] }),
})

function ReadOnlyField({
  id,
  label,
  value,
}: {
  id: string
  label: string
  value: string
}) {
  return (
    <div className="flex min-w-40 flex-col gap-1">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} readOnly value={value} />
    </div>
  )
}

function formatAnswer(item: {
  value_num?: number | string | null
  value_text?: string | null
  value_date?: string | null
}): string {
  if (item.value_text) {
    return item.value_text
  }
  if (item.value_num !== null && item.value_num !== undefined) {
    return String(item.value_num)
  }
  if (item.value_date) {
    return item.value_date
  }
  return "—"
}

function SessionDetail() {
  const { sessionId } = Route.useParams()

  const { data: sessionRow } = useSuspenseQuery({
    queryKey: ["session", sessionId],
    queryFn: async () =>
      (
        await SessionsService.readQuestionnaireSession({
          path: { session_id: sessionId },
        })
      ).data,
  })

  const { data: answers } = useSuspenseQuery({
    queryKey: ["session-answers", sessionId],
    queryFn: async () =>
      (
        await SessionsService.readQuestionnaireSessionAnswers({
          path: { session_id: sessionId },
        })
      ).data,
  })

  const { data: recommendations } = useSuspenseQuery({
    queryKey: ["session-recommendations", sessionId],
    queryFn: async () =>
      (
        await SessionsService.readQuestionnaireSessionRecommendations({
          path: { session_id: sessionId },
        })
      ).data,
  })

  const groups: {
    userId: string
    items: (typeof recommendations.data)[number][]
  }[] = []
  for (const item of recommendations.data) {
    const last = groups[groups.length - 1]
    if (last && last.userId === item.user_id) {
      last.items.push(item)
    } else {
      groups.push({ userId: item.user_id, items: [item] })
    }
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight">Ответ</h1>
        <p className="font-mono text-sm text-muted-foreground">
          {sessionRow.id}
        </p>
      </div>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold tracking-tight">
          Вопросы и ответы
        </h2>
        {answers.data.length === 0 ? (
          <p className="text-muted-foreground">Нет вопросов.</p>
        ) : (
          answers.data.map((item) => (
            <div
              key={item.question_id}
              className="grid gap-3 rounded-md border p-4 md:grid-cols-2"
            >
              <ReadOnlyField
                id={`${item.question_id}-question`}
                label="Вопрос"
                value={item.question_text}
              />
              <ReadOnlyField
                id={`${item.question_id}-answer`}
                label="Ответ"
                value={formatAnswer(item)}
              />
            </div>
          ))
        )}
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight">Рекомендации</h2>
          <Button type="button">Добавить рекомендацию</Button>
        </div>
        {groups.length === 0 ? (
          <p className="text-muted-foreground">Нет рекомендаций.</p>
        ) : (
          groups.map((group) => (
            <div key={group.userId} className="flex flex-col gap-3">
              <h3 className="font-mono text-sm text-muted-foreground">
                user_id {group.userId}
              </h3>
              {group.items.map((item) => (
                <div
                  key={item.id}
                  className="grid gap-3 rounded-md border p-4 md:grid-cols-2"
                >
                  <ReadOnlyField
                    id={`${item.id}-name`}
                    label="name"
                    value={item.recommendation_name}
                  />
                  <ReadOnlyField
                    id={`${item.id}-slug`}
                    label="slug"
                    value={item.recommendation_slug}
                  />
                  <ReadOnlyField
                    id={`${item.id}-text`}
                    label="text"
                    value={item.recommendation_text}
                  />
                  <ReadOnlyField
                    id={`${item.id}-chart`}
                    label="chart_number"
                    value={String(item.chart_number)}
                  />
                  <ReadOnlyField
                    id={`${item.id}-weight`}
                    label="weight"
                    value={String(item.weight)}
                  />
                  <ReadOnlyField
                    id={`${item.id}-comment`}
                    label="comment"
                    value={item.comment || "—"}
                  />
                  <ReadOnlyField
                    id={`${item.id}-user`}
                    label="user_id"
                    value={item.user_id}
                  />
                  <ReadOnlyField
                    id={`${item.id}-rec`}
                    label="recomendation_id"
                    value={item.recomendation_id}
                  />
                  <ReadOnlyField
                    id={`${item.id}-session`}
                    label="session_id"
                    value={item.session_id}
                  />
                  <ReadOnlyField
                    id={`${item.id}-id`}
                    label="id"
                    value={item.id}
                  />
                </div>
              ))}
            </div>
          ))
        )}
      </section>
    </>
  )
}

function SessionPage() {
  return (
    <div className="flex flex-col gap-6">
      <Suspense fallback={<p className="text-muted-foreground">Загрузка…</p>}>
        <SessionDetail />
      </Suspense>
    </div>
  )
}
