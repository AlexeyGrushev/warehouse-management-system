import { apiFetch } from './client'
import type { Page, StocktakingDetail, StocktakingStatus, StocktakingSummary } from './types'

export interface StocktakingFilters {
  status?: StocktakingStatus
  page: number
  size: number
}

export function fetchStocktakings(filters: StocktakingFilters): Promise<Page<StocktakingSummary>> {
  const params = new URLSearchParams({ page: String(filters.page), size: String(filters.size) })
  if (filters.status) {
    params.set('status', filters.status)
  }
  return apiFetch<Page<StocktakingSummary>>(`/stocktakings?${params}`)
}

export function fetchStocktaking(id: number): Promise<StocktakingDetail> {
  return apiFetch<StocktakingDetail>(`/stocktakings/${id}`)
}

/** Без categoryId инвентаризация охватывает все активные товары. */
export function createStocktaking(categoryId?: number): Promise<StocktakingDetail> {
  return apiFetch<StocktakingDetail>('/stocktakings', {
    method: 'POST',
    body: JSON.stringify({ category_id: categoryId ?? null }),
  })
}

export function startStocktaking(id: number): Promise<StocktakingDetail> {
  return apiFetch<StocktakingDetail>(`/stocktakings/${id}/start`, { method: 'POST' })
}

export function cancelStocktaking(id: number): Promise<StocktakingDetail> {
  return apiFetch<StocktakingDetail>(`/stocktakings/${id}/cancel`, { method: 'POST' })
}

export function setCountedQuantity(
  id: number,
  productId: number,
  countedQty: string,
): Promise<StocktakingDetail> {
  return apiFetch<StocktakingDetail>(`/stocktakings/${id}/lines/${productId}`, {
    method: 'PUT',
    body: JSON.stringify({ counted_qty: countedQty }),
  })
}

export function closeStocktaking(id: number): Promise<StocktakingDetail> {
  return apiFetch<StocktakingDetail>(`/stocktakings/${id}/close`, { method: 'POST' })
}
