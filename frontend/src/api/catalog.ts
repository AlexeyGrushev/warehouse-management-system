import { apiFetch } from './client'
import type { Category, Page, Product } from './types'

export interface ProductFilters {
  q?: string
  page: number
  size: number
}

export function fetchProducts({ q, page, size }: ProductFilters): Promise<Page<Product>> {
  const params = new URLSearchParams({ page: String(page), size: String(size) })
  if (q) {
    params.set('q', q)
  }
  return apiFetch<Page<Product>>(`/products?${params}`)
}

export function fetchCategories(): Promise<Category[]> {
  return apiFetch<Category[]>('/categories')
}
