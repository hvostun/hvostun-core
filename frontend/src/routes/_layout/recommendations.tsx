import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import {
  type RecommendationPublic,
  RecommendationsService,
  UsersService,
} from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { fieldColumns, PAGE_SIZE } from "@/components/Common/fieldColumns"
import { ListFilters } from "@/components/Common/ListFilters"

type RecommendationsSearch = {
  page: number
  name: string
  slug: string
}

export const Route = createFileRoute("/_layout/recommendations")({
  component: RecommendationsPage,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  validateSearch: (search: Record<string, unknown>): RecommendationsSearch => ({
    page: Number(search.page) > 0 ? Number(search.page) : 1,
    name: typeof search.name === "string" ? search.name : "",
    slug: typeof search.slug === "string" ? search.slug : "",
  }),
  head: () => ({ meta: [{ title: "Рекомендации — Hvostun" }] }),
})

const columns = fieldColumns<RecommendationPublic>([
  { key: "id", header: "id" },
  { key: "name", header: "name" },
  { key: "slug", header: "slug" },
  { key: "text", header: "text" },
  { key: "description", header: "description" },
] as const)

function RecommendationsTable() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const pageIndex = search.page - 1

  const { data } = useSuspenseQuery({
    queryKey: ["recommendations", search],
    queryFn: async () =>
      (
        await RecommendationsService.readRecommendations({
          query: {
            skip: pageIndex * PAGE_SIZE,
            limit: PAGE_SIZE,
            name: search.name || null,
            slug: search.slug || null,
          },
        })
      ).data,
  })

  return (
    <>
      <ListFilters
        key={JSON.stringify(search)}
        values={{
          name: search.name,
          slug: search.slug,
        }}
        fields={[
          { name: "name", label: "Название" },
          { name: "slug", label: "slug" },
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

function RecommendationsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold tracking-tight">Рекомендации</h1>
      <Suspense fallback={<p className="text-muted-foreground">Загрузка…</p>}>
        <RecommendationsTable />
      </Suspense>
    </div>
  )
}
