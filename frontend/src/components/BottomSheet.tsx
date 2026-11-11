import type { ReactNode } from "react"

export function BottomSheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <>
      <button type="button" className="overlay" aria-label="Закрыть" onClick={onClose} />
      <div className="sheet" role="dialog" aria-label={title}>
        <h2 className="h-block">{title}</h2>
        {children}
      </div>
    </>
  )
}
