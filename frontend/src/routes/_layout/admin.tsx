import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { UserActionsMenu } from "@/components/Admin/UserActionsMenu"
import { DataTable } from "@/components/Common/DataTable"
import { fieldColumns, PAGE_SIZE } from "@/components/Common/fieldColumns"
import { ListFilters } from "@/components/Common/ListFilters"
import PendingUsers from "@/components/Pending/PendingUsers"
import useAuth from "@/hooks/useAuth"

type AdminSearch = {
  page: number
  email: string
  full_name: string
  is_superuser: string
  is_active: string
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  validateSearch: (search: Record<string, unknown>): AdminSearch => ({
    page: Number(search.page) > 0 ? Number(search.page) : 1,
    email: typeof search.email === "string" ? search.email : "",
    full_name: typeof search.full_name === "string" ? search.full_name : "",
    is_superuser:
      typeof search.is_superuser === "string" ? search.is_superuser : "",
    is_active: typeof search.is_active === "string" ? search.is_active : "",
  }),
  head: () => ({
    meta: [{ title: "Администраторы — Hvostun" }],
  }),
})

type UserTableData = UserPublic & { isCurrentUser: boolean }

const columns = [
  ...fieldColumns<UserTableData>([
    { key: "id", header: "id" },
    { key: "email", header: "email" },
    { key: "full_name", header: "full_name" },
    { key: "group", header: "group" },
    { key: "phone", header: "phone" },
    { key: "contact", header: "contact" },
    { key: "is_active", header: "is_active" },
    { key: "is_superuser", header: "is_superuser" },
    { key: "created_at", header: "created_at" },
    { key: "updated_at", header: "updated_at" },
  ]),
  {
    id: "actions",
    header: () => <span className="sr-only">Действия</span>,
    cell: ({ row }: { row: { original: UserTableData } }) => (
      <div className="flex justify-end">
        <UserActionsMenu user={row.original} />
      </div>
    ),
  },
]

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const pageIndex = search.page - 1

  const { data: users } = useSuspenseQuery({
    queryKey: ["users", search],
    queryFn: async () =>
      (
        await UsersService.readUsers({
          query: {
            skip: pageIndex * PAGE_SIZE,
            limit: PAGE_SIZE,
            email: search.email || null,
            full_name: search.full_name || null,
            is_superuser:
              search.is_superuser === ""
                ? null
                : search.is_superuser === "true",
            is_active:
              search.is_active === "" ? null : search.is_active === "true",
          },
        })
      ).data,
  })

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return (
    <>
      <ListFilters
        key={JSON.stringify(search)}
        values={{
          email: search.email,
          full_name: search.full_name,
          is_superuser: search.is_superuser,
          is_active: search.is_active,
        }}
        fields={[
          { name: "email", label: "Email" },
          { name: "full_name", label: "Имя" },
          {
            name: "is_superuser",
            label: "Superuser",
            type: "select",
            options: [
              { value: "true", label: "да" },
              { value: "false", label: "нет" },
            ],
          },
          {
            name: "is_active",
            label: "Активен",
            type: "select",
            options: [
              { value: "true", label: "да" },
              { value: "false", label: "нет" },
            ],
          },
        ]}
        onApply={(next) => navigate({ search: { page: 1, ...next } })}
      />
      <DataTable
        columns={columns}
        data={tableData}
        pageIndex={pageIndex}
        pageCount={Math.max(1, Math.ceil(users.count / PAGE_SIZE))}
        pageSize={PAGE_SIZE}
        totalCount={users.count}
        onPageChange={(next) =>
          navigate({ search: (prev) => ({ ...prev, page: next + 1 }) })
        }
      />
    </>
  )
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function Admin() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Администраторы</h1>
        <AddUser />
      </div>
      <UsersTable />
    </div>
  )
}
