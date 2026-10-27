import { apiFetch } from './client'
import type { Batch, Movement, MovementType, Page, ReceiptInput, StockRow } from './types'

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

export function createReceipt(data: ReceiptInput): Promise<Batch> {
  return apiFetch<Batch>('/receipts', { method: 'POST', body: JSON.stringify(data) })
}

export interface MovementFilters {
  productId?: number
  type?: MovementType
  dateFrom?: string
  dateTo?: string
  page: number
  size: number
}

export function fetchMovements(filters: MovementFilters): Promise<Page<Movement>> {
  const params = new URLSearchParams({ page: String(filters.page), size: String(filters.size) })
  if (filters.productId !== undefined) {
    params.set('product_id', String(filters.productId))
  }
  if (filters.type) {
    params.set('type', filters.type)
  }
  if (filters.dateFrom) {
    params.set('date_from', filters.dateFrom)
  }
  if (filters.dateTo) {
    params.set('date_to', filters.dateTo)
  }
  return apiFetch<Page<Movement>>(`/movements?${params}`)
}
