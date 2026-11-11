import { apiFetch } from './client'
import type { Page, Supplier, SupplierInput } from './types'

export function fetchSuppliers(q: string): Promise<Page<Supplier>> {
  const params = new URLSearchParams({ page: '1', size: '20', is_active: 'true' })
  if (q) {
    params.set('q', q)
  }
  return apiFetch<Page<Supplier>>(`/suppliers?${params}`)
}

export interface SupplierFilters {
  q?: string
  isActive?: boolean
  page: number
  size: number
}

export function fetchSupplierPage({ q, isActive, page, size }: SupplierFilters): Promise<Page<Supplier>> {
  const params = new URLSearchParams({ page: String(page), size: String(size) })
  if (q) {
    params.set('q', q)
  }
  if (isActive !== undefined) {
    params.set('is_active', String(isActive))
  }
  return apiFetch<Page<Supplier>>(`/suppliers?${params}`)
}

export function createSupplier(data: SupplierInput): Promise<Supplier> {
  return apiFetch<Supplier>('/suppliers', { method: 'POST', body: JSON.stringify(data) })
}

export function updateSupplier(id: number, data: SupplierInput): Promise<Supplier> {
  return apiFetch<Supplier>(`/suppliers/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function archiveSupplier(id: number): Promise<void> {
  return apiFetch<void>(`/suppliers/${id}/archive`, { method: 'POST' })
}
