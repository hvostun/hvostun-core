export function ErrorBanner({ children }: { children: string }) {
  return (
    <div className="note error" role="alert">
      {children}
    </div>
  )
}
