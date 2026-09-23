import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { SessionsService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { fieldColumns, PAGE_SIZE } from "@/components/Common/fieldColumns"
import { ListFilters } from "@/components/Common/ListFilters"

type SessionsSearch = {
  page: number
  status: string
  user_id: string
  dog_id: string
  questionnaire_id: string
}

export const Route = createFileRoute("/_layout/sessions")({
  component: SessionsPage,
  validateSearch: (search: Record<string, unknown>): SessionsSearch => ({
    page: Number(search.page) > 0 ? Number(search.page) : 1,
    status: typeof search.status === "string" ? search.status : "",
    user_id: typeof search.user_id === "string" ? search.user_id : "",
    dog_id: typeof search.dog_id === "string" ? search.dog_id : "",
    questionnaire_id:
      typeof search.questionnaire_id === "string" ? search.questionnaire_id : "",
  }),
  head: () => ({ meta: [{ title: "Анкеты — Hvostun" }] }),
})

const columns = fieldColumns([
  { key: "id", header: "id" },
  { key: "user_id", header: "user_id" },
  { key: "dog_id", header: "dog_id" },
  { key: "questionnaire_id", header: "questionnaire_id" },
  { key: "status", header: "status" },
  { key: "client_metadata", header: "client_metadata" },
  { key: "created_at", header: "created_at" },
  { key: "updated_at", header: "updated_at" },
] as const)

function SessionsTable() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const pageIndex = search.page - 1

  const { data } = useSuspenseQuery({
    queryKey: ["sessions", search],
    queryFn: async () =>
      (
        await SessionsService.readQuestionnaireSessions({
          query: {
            skip: pageIndex * PAGE_SIZE,
            limit: PAGE_SIZE,
            status: search.status || null,
            user_id: search.user_id || null,
            dog_id: search.dog_id || null,
            questionnaire_id: search.questionnaire_id || null,
          },
        })
      ).data,
  })

  return (
    <>
      <ListFilters
        key={JSON.stringify(search)}
        values={{
          status: search.status,
          user_id: search.user_id,
          dog_id: search.dog_id,
          questionnaire_id: search.questionnaire_id,
        }}
        fields={[
          {
            name: "status",
            label: "Статус",
            type: "select",
            options: [
              { value: "draft", label: "draft" },
              { value: "finished", label: "finished" },
              { value: "canceled", label: "canceled" },
            ],
          },
          { name: "user_id", label: "user_id" },
          { name: "dog_id", label: "dog_id" },
          { name: "questionnaire_id", label: "questionnaire_id" },
        ]}
        onApply={(next) => navigate({ search: { page: 1, ...next } })}
      />
      <DataTable
        columns={columns}
        data={data.data}
        pageIndex={pageIndex}
        pageCount={Math.max(1, Math.ceil(data.count / PAGE_SIZE))}
        pageSize={PAGE_SIZE}
        totalCount={data.count}
        onPageChange={(next) =>
          navigate({ search: (prev) => ({ ...prev, page: next + 1 }) })
        }
      />
    </>
  )
}

function SessionsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold tracking-tight">Анкеты</h1>
      <Suspense fallback={<p className="text-muted-foreground">Загрузка…</p>}>
        <SessionsTable />
      </Suspense>
    </div>
  )
}
