import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { type DogPublic, DogsService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { fieldColumns, PAGE_SIZE } from "@/components/Common/fieldColumns"
import { ListFilters } from "@/components/Common/ListFilters"

type DogsSearch = {
  page: number
  name: string
  status: string
  shelter_id: string
  owner_id: string
}

export const Route = createFileRoute("/_layout/dogs")({
  component: DogsPage,
  validateSearch: (search: Record<string, unknown>): DogsSearch => ({
    page: Number(search.page) > 0 ? Number(search.page) : 1,
    name: typeof search.name === "string" ? search.name : "",
    status: typeof search.status === "string" ? search.status : "",
    shelter_id: typeof search.shelter_id === "string" ? search.shelter_id : "",
    owner_id: typeof search.owner_id === "string" ? search.owner_id : "",
  }),
  head: () => ({ meta: [{ title: "Собаки — Hvostun" }] }),
})

const columns = fieldColumns<DogPublic>([
  { key: "id", header: "id" },
  { key: "name", header: "name" },
  { key: "sex", header: "sex" },
  { key: "neutered", header: "neutered" },
  { key: "status", header: "status" },
  { key: "description", header: "description" },
  { key: "shelter_id", header: "shelter_id" },
  { key: "assigned_volunteer_id", header: "assigned_volunteer_id" },
  { key: "owner_id", header: "owner_id" },
  { key: "birthday", header: "birthday" },
  { key: "adopted_at", header: "adopted_at" },
  { key: "breed", header: "breed" },
  { key: "mixed", header: "mixed" },
  { key: "created_by_id", header: "created_by_id" },
] as const)

function DogsTable() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const pageIndex = search.page - 1

  const { data } = useSuspenseQuery({
    queryKey: ["dogs", search],
    queryFn: async () =>
      (
        await DogsService.readDogs({
          query: {
            skip: pageIndex * PAGE_SIZE,
            limit: PAGE_SIZE,
            name: search.name || null,
            status: search.status || null,
            shelter_id: search.shelter_id || null,
            owner_id: search.owner_id || null,
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
          status: search.status,
          shelter_id: search.shelter_id,
          owner_id: search.owner_id,
        }}
        fields={[
          { name: "name", label: "Имя" },
          {
            name: "status",
            label: "Статус",
            type: "select",
            options: [
              { value: "shelter", label: "shelter" },
              { value: "home", label: "home" },
              { value: "overexposure", label: "overexposure" },
              { value: "unknown", label: "unknown" },
            ],
          },
          { name: "shelter_id", label: "shelter_id" },
          { name: "owner_id", label: "owner_id" },
        ]}
        onApply={(next) =>
          navigate({
            search: { page: 1, ...next },
          })
        }
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

function DogsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold tracking-tight">Собаки</h1>
      <Suspense fallback={<p className="text-muted-foreground">Загрузка…</p>}>
        <DogsTable />
      </Suspense>
    </div>
  )
}
