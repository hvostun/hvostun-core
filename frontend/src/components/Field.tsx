import type { ReactNode, Ref } from "react"

export function Field({
  label,
  error,
  children,
  fieldRef,
}: {
  label: string
  error?: string
  children: ReactNode
  fieldRef?: Ref<HTMLDivElement>
}) {
  return (
    <div className={error ? "field miss" : "field"} ref={fieldRef}>
      <div className="field-head">
        <label>{label}</label>
        {error ? (
          <span className="err" role="alert">
            {error}
          </span>
        ) : null}
      </div>
      {children}
    </div>
  )
}
