import { MOCK_EXPIRING, MOCK_LOW_STOCK } from './alertsMock'
import { apiFetch } from './client'
import type { ExpiringBatch, LowStockItem, Page, Severity } from './types'

const USE_MOCK = import.meta.env.VITE_MOCK_ALERTS === 'true'

export interface LowStockFilters {
  categoryId?: number
  severity?: Severity
  page: number
  size: number
}

export function fetchLowStock(filters: LowStockFilters): Promise<Page<LowStockItem>> {
  if (USE_MOCK) {
    return Promise.resolve(MOCK_LOW_STOCK)
  }
  const params = new URLSearchParams({ page: String(filters.page), size: String(filters.size) })
  if (filters.categoryId !== undefined) {
    params.set('category_id', String(filters.categoryId))
  }
  if (filters.severity) {
    params.set('severity', filters.severity)
  }
  return apiFetch<Page<LowStockItem>>(`/alerts/low-stock?${params}`)
}

export interface ExpiringFilters {
  days: number
  page: number
  size: number
}

export function fetchExpiringBatches({ days, page, size }: ExpiringFilters): Promise<Page<ExpiringBatch>> {
  if (USE_MOCK) {
    return Promise.resolve(MOCK_EXPIRING)
  }
  const params = new URLSearchParams({ days: String(days), page: String(page), size: String(size) })
  return apiFetch<Page<ExpiringBatch>>(`/alerts/expiring-batches?${params}`)
}
