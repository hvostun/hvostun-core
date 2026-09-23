import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { type QuestionPublic, QuestionnairesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { fieldColumns } from "@/components/Common/fieldColumns"

export const Route = createFileRoute(
  "/_layout/questionnaires_/$questionnaireId",
)({
  component: QuestionnairePage,
  head: () => ({ meta: [{ title: "Анкета — Hvostun" }] }),
})

const questionColumns = fieldColumns<QuestionPublic>([
  { key: "order_number", header: "order_number" },
  { key: "global_id", header: "global_id" },
  { key: "id", header: "id" },
  { key: "text", header: "text" },
  { key: "scale_name", header: "scale" },
  { key: "questionnaire_id", header: "questionnaire_id" },
] as const)

function QuestionnaireQuestions() {
  const { questionnaireId } = Route.useParams()

  const { data: questionnaire } = useSuspenseQuery({
    queryKey: ["questionnaire", questionnaireId],
    queryFn: async () =>
      (
        await QuestionnairesService.readQuestionnaire({
          path: { questionnaire_id: questionnaireId },
        })
      ).data,
  })

  const { data: questions } = useSuspenseQuery({
    queryKey: ["questionnaire-questions", questionnaireId],
    queryFn: async () =>
      (
        await QuestionnairesService.readQuestionnaireQuestions({
          path: { questionnaire_id: questionnaireId },
        })
      ).data,
  })

  return (
    <>
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight">
          {questionnaire.name}
        </h1>
        <p className="font-mono text-sm text-muted-foreground">
          {questionnaire.slug}
        </p>
        {questionnaire.description ? (
          <p className="text-muted-foreground">{questionnaire.description}</p>
        ) : null}
      </div>
      <DataTable columns={questionColumns} data={questions.data} />
    </>
  )
}

function QuestionnairePage() {
  return (
    <div className="flex flex-col gap-6">
      <Suspense fallback={<p className="text-muted-foreground">Загрузка…</p>}>
        <QuestionnaireQuestions />
      </Suspense>
    </div>
  )
}
