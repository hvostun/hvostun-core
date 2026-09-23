import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import { type OwnerPublic, OwnersService, UsersService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { fieldColumns, PAGE_SIZE } from "@/components/Common/fieldColumns"
import { ListFilters } from "@/components/Common/ListFilters"

type OwnersSearch = {
  page: number
  name: string
  email: string
  phone: string
}

export const Route = createFileRoute("/_layout/owners")({
  component: OwnersPage,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  validateSearch: (search: Record<string, unknown>): OwnersSearch => ({
    page: Number(search.page) > 0 ? Number(search.page) : 1,
    name: typeof search.name === "string" ? search.name : "",
    email: typeof search.email === "string" ? search.email : "",
    phone: typeof search.phone === "string" ? search.phone : "",
  }),
  head: () => ({ meta: [{ title: "Владельцы — Hvostun" }] }),
})

const columns = fieldColumns<OwnerPublic>([
  { key: "id", header: "id" },
  { key: "name", header: "name" },
  { key: "email", header: "email" },
  { key: "phone", header: "phone" },
  { key: "contact", header: "contact" },
] as const)

function OwnersTable() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const pageIndex = search.page - 1

  const { data } = useSuspenseQuery({
    queryKey: ["owners", search],
    queryFn: async () =>
      (
        await OwnersService.readOwners({
          query: {
            skip: pageIndex * PAGE_SIZE,
            limit: PAGE_SIZE,
            name: search.name || null,
            email: search.email || null,
            phone: search.phone || null,
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
          email: search.email,
          phone: search.phone,
        }}
        fields={[
          { name: "name", label: "Имя" },
          { name: "email", label: "Email" },
          { name: "phone", label: "Телефон" },
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

function OwnersPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold tracking-tight">Владельцы</h1>
      <Suspense fallback={<p className="text-muted-foreground">Загрузка…</p>}>
        <OwnersTable />
      </Suspense>
    </div>
  )
}
