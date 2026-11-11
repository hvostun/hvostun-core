import { useState } from "react"
import { formatDate, isoDate } from "../state/profileRules"

const weekdays = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

function monthStart(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

export function DatePicker({
  value,
  onChange,
  disabled,
}: {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}) {
  const today = isoDate(new Date())
  const [open, setOpen] = useState(false)
  const [cursor, setCursor] = useState(() => monthStart(value ? new Date(value) : new Date()))
  const year = cursor.getFullYear()
  const month = cursor.getMonth()
  const firstWeekday = (cursor.getDay() + 6) % 7
  const days = new Date(year, month + 1, 0).getDate()
  const cells = [...Array<undefined>(firstWeekday).fill(undefined), ...Array.from({ length: days }, (_, index) => index + 1)]

  return (
    <div>
      <button type="button" className="input" disabled={disabled} onClick={() => setOpen((current) => !current)}>
        {value ? formatDate(value) : "Выберите дату"}
      </button>
      {open ? (
        <div className="stack" style={{ marginTop: 8 }}>
          <div className="row-actions">
            <button type="button" className="round" aria-label="Предыдущий месяц" onClick={() => setCursor(new Date(year, month - 1, 1))}>
              ‹
            </button>
            <span>
              {cursor.toLocaleString("ru", { month: "long", year: "numeric" })}
            </span>
            <button type="button" className="round" aria-label="Следующий месяц" onClick={() => setCursor(new Date(year, month + 1, 1))}>
              ›
            </button>
          </div>
          <div className="days">
            {weekdays.map((day) => (
              <span key={day} className="caption" style={{ textAlign: "center" }}>
                {day}
              </span>
            ))}
            {cells.map((day, index) => {
              if (!day) return <span key={`empty-${index}`} />
              const iso = isoDate(new Date(year, month, day))
              return (
                <button
                  key={iso}
                  type="button"
                  className={iso === value ? "on" : undefined}
                  disabled={iso > today}
                  onClick={() => {
                    onChange(iso)
                    setOpen(false)
                  }}
                >
                  {day}
                </button>
              )
            })}
          </div>
        </div>
      ) : null}
    </div>
  )
}
