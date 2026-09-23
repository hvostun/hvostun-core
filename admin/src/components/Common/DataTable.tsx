import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table"
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  pageIndex?: number
  pageCount?: number
  pageSize?: number
  totalCount?: number
  onPageChange?: (pageIndex: number) => void
  onRowClick?: (row: TData) => void
}

export function DataTable<TData, TValue>({
  columns,
  data,
  pageIndex = 0,
  pageCount,
  pageSize = 50,
  totalCount,
  onPageChange,
  onRowClick,
}: DataTableProps<TData, TValue>) {
  const isServerPaged = pageCount != null && onPageChange != null
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: isServerPaged ? undefined : getPaginationRowModel(),
    manualPagination: isServerPaged,
    pageCount: isServerPaged ? pageCount : undefined,
    state: isServerPaged ? { pagination: { pageIndex, pageSize } } : undefined,
  })

  const currentPage = isServerPaged
    ? pageIndex
    : table.getState().pagination.pageIndex
  const pages = isServerPaged ? pageCount : table.getPageCount()
  const total = totalCount ?? data.length
  const from = total === 0 ? 0 : currentPage * pageSize + 1
  const to = Math.min((currentPage + 1) * pageSize, total)

  const goTo = (next: number) => {
    if (isServerPaged) {
      onPageChange(next)
      return
    }
    table.setPageIndex(next)
  }

  return (
    <div className="flex flex-col gap-4">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-transparent">
              {headerGroup.headers.map((header) => {
                return (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                className={onRowClick ? "cursor-pointer" : undefined}
                onClick={
                  onRowClick ? () => onRowClick(row.original) : undefined
                }
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow className="hover:bg-transparent">
              <TableCell
                colSpan={columns.length}
                className="h-32 text-center text-muted-foreground"
              >
                Нет записей.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {pages > 1 && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 border-t bg-muted/20">
          <div className="text-sm text-muted-foreground">
            Показаны {from}–{to} из{" "}
            <span className="font-medium text-foreground">{total}</span>
          </div>

          <div className="flex items-center gap-x-6">
            <div className="flex items-center gap-x-1 text-sm text-muted-foreground">
              <span>Страница</span>
              <span className="font-medium text-foreground">
                {currentPage + 1}
              </span>
              <span>из</span>
              <span className="font-medium text-foreground">{pages}</span>
            </div>

            <div className="flex items-center gap-x-1">
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goTo(0)}
                disabled={currentPage === 0}
              >
                <span className="sr-only">Первая страница</span>
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goTo(currentPage - 1)}
                disabled={currentPage === 0}
              >
                <span className="sr-only">Предыдущая страница</span>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goTo(currentPage + 1)}
                disabled={currentPage >= pages - 1}
              >
                <span className="sr-only">Следующая страница</span>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => goTo(pages - 1)}
                disabled={currentPage >= pages - 1}
              >
                <span className="sr-only">Последняя страница</span>
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
