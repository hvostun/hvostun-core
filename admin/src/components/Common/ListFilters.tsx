import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export type FilterField = {
  name: string
  label: string
  type?: "text" | "select"
  options?: { value: string; label: string }[]
}

type ListFiltersProps<T extends Record<string, string>> = {
  fields: FilterField[]
  values: T
  onApply: (next: T) => void
}

export function ListFilters<T extends Record<string, string>>({
  fields,
  values,
  onApply,
}: ListFiltersProps<T>) {
  const [draft, setDraft] = useState<T>(values)

  const setField = (name: keyof T, value: string) => {
    setDraft((current) => ({ ...current, [name]: value }))
  }

  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        onApply(draft)
      }}
    >
      {fields.map((field) => (
        <label key={field.name} className="flex min-w-40 flex-col gap-1">
          <span className="text-sm text-muted-foreground">{field.label}</span>
          {field.type === "select" ? (
            <Select
              value={draft[field.name] || "all"}
              onValueChange={(value) =>
                setField(field.name, value === "all" ? "" : value)
              }
            >
              <SelectTrigger>
                <SelectValue placeholder={field.label} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все</SelectItem>
                {field.options?.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              value={draft[field.name] ?? ""}
              onChange={(event) => setField(field.name, event.target.value)}
            />
          )}
        </label>
      ))}
      <Button type="submit" variant="secondary">
        Применить
      </Button>
    </form>
  )
}
