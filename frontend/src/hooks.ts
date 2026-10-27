import { useEffect, useState } from 'react'

/** Значение, которое обновляется с задержкой — чтобы не слать запрос на каждую набранную букву. */
export function useDebounced<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}
