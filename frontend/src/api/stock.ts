import { apiFetch } from './client'
import type { Page, StockRow } from './types'

export interface StockFilters {
  q?: string
  lowOnly: boolean
  page: number
  size: number
}

export function fetchStock({ q, lowOnly, page, size }: StockFilters): Promise<Page<StockRow>> {
  const params = new URLSearchParams({ page: String(page), size: String(size) })
  if (q) {
    params.set('q', q)
  }
  if (lowOnly) {
    params.set('low_only', 'true')
  }
  return apiFetch<Page<StockRow>>(`/stock?${params}`)
}
