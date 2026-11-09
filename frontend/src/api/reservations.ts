import { apiFetch } from './client'
import type { Page, Reservation, ReservationInput, ReservationStatus } from './types'

export interface ReservationFilters {
  status?: ReservationStatus
  reference?: string
  page: number
  size: number
}

export function fetchReservations(filters: ReservationFilters): Promise<Page<Reservation>> {
  const params = new URLSearchParams({ page: String(filters.page), size: String(filters.size) })
  if (filters.status) {
    params.set('status', filters.status)
  }
  if (filters.reference) {
    params.set('reference', filters.reference)
  }
  return apiFetch<Page<Reservation>>(`/reservations?${params}`)
}

export function fetchReservation(id: number): Promise<Reservation> {
  return apiFetch<Reservation>(`/reservations/${id}`)
}

export function createReservation(data: ReservationInput): Promise<Reservation> {
  return apiFetch<Reservation>('/reservations', { method: 'POST', body: JSON.stringify(data) })
}

export function cancelReservation(id: number): Promise<Reservation> {
  return apiFetch<Reservation>(`/reservations/${id}/cancel`, { method: 'POST' })
}

export function fulfillReservation(id: number): Promise<Reservation> {
  return apiFetch<Reservation>(`/reservations/${id}/fulfill`, { method: 'POST' })
}
