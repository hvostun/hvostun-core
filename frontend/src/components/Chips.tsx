export function Chips<T extends string>({
  options,
  value,
  onChange,
  disabled,
  label,
}: {
  options: { value: T; label: string }[]
  value: T | ""
  onChange: (value: T) => void
  disabled?: boolean
  label: string
}) {
  return (
    <div className="chips" role="radiogroup" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={option.value === value ? "chip on" : "chip"}
          aria-checked={option.value === value}
          role="radio"
          disabled={disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
