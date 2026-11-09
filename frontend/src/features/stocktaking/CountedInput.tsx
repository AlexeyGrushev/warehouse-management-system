import { InputNumber } from 'antd'
import { useState } from 'react'

interface Props {
  value: string | null
  unit: string
  disabled?: boolean
  saving?: boolean
  onCommit: (value: string) => void
}

/** Поле «насчитали»: значение сохраняется при потере фокуса или Enter, если оно изменилось. */
export function CountedInput({ value, unit, disabled, saving, onCommit }: Props) {
  const [draft, setDraft] = useState<string | null>(value)

  function commit() {
    if (draft !== null && draft !== '' && Number(draft) !== Number(value)) {
      onCommit(draft)
    }
  }

  return (
    <InputNumber
      stringMode
      min="0"
      precision={unit === 'pcs' ? 0 : 3}
      value={draft}
      disabled={disabled || saving}
      onChange={(next) => setDraft(next === null ? null : String(next))}
      onBlur={commit}
      onPressEnter={commit}
      style={{ width: 130 }}
      placeholder="—"
    />
  )
}
