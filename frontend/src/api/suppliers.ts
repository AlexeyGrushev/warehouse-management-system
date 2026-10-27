import { apiFetch } from './client'
import type { Page, Supplier } from './types'

export function fetchSuppliers(q: string): Promise<Page<Supplier>> {
  const params = new URLSearchParams({ page: '1', size: '20', is_active: 'true' })
  if (q) {
    params.set('q', q)
  }
  return apiFetch<Page<Supplier>>(`/suppliers?${params}`)
}
