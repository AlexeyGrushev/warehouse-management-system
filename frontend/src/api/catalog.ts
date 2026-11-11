import { apiFetch } from './client'
import type { Category, Page, Product, ProductInput } from './types'

export interface ProductFilters {
  q?: string
  isActive?: boolean
  page: number
  size: number
}

export function fetchProducts({ q, isActive, page, size }: ProductFilters): Promise<Page<Product>> {
  const params = new URLSearchParams({ page: String(page), size: String(size) })
  if (q) {
    params.set('q', q)
  }
  if (isActive !== undefined) {
    params.set('is_active', String(isActive))
  }
  return apiFetch<Page<Product>>(`/products?${params}`)
}

export function fetchCategories(): Promise<Category[]> {
  return apiFetch<Category[]>('/categories')
}

export function fetchProduct(id: number): Promise<Product> {
  return apiFetch<Product>(`/products/${id}`)
}

export function createProduct(data: ProductInput): Promise<Product> {
  return apiFetch<Product>('/products', { method: 'POST', body: JSON.stringify(data) })
}

export function updateProduct(id: number, data: ProductInput): Promise<Product> {
  return apiFetch<Product>(`/products/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function archiveProduct(id: number): Promise<void> {
  return apiFetch<void>(`/products/${id}/archive`, { method: 'POST' })
}
