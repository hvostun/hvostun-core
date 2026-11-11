import type { ButtonHTMLAttributes, ReactNode } from "react"

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary"
  block?: boolean
  children: ReactNode
}

export function Button({ variant = "primary", block, className = "", children, ...props }: Props) {
  const names = ["btn", variant === "primary" ? "btn-primary" : "btn-secondary", block ? "btn-block" : "", className]
  return (
    <button type="button" className={names.filter(Boolean).join(" ")} {...props}>
      {children}
    </button>
  )
}
