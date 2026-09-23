import type { ColumnDef } from "@tanstack/react-table"

export const PAGE_SIZE = 50

export function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—"
  }
  if (typeof value === "boolean") {
    return value ? "да" : "нет"
  }
  if (typeof value === "object") {
    return JSON.stringify(value)
  }
  return String(value)
}

export function fieldColumns<T extends object>(
  fields: { key: keyof T & string; header: string }[],
): ColumnDef<T>[] {
  return fields.map(({ key, header }) => ({
    accessorKey: key,
    header,
    cell: ({ row }) => {
      const value = row.original[key]
      const text = formatCell(value)
      const isId = key === "id" || key.endsWith("_id")
      return (
        <span
          className={
            isId || typeof value === "object"
              ? "font-mono text-xs break-all"
              : undefined
          }
          title={text}
        >
          {isId && text.length > 12 ? `${text.slice(0, 8)}…` : text}
        </span>
      )
    },
  }))
}
