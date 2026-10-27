export type Role = 'admin' | 'storekeeper' | 'viewer'

export interface User {
  id: number
  email: string
  role: Role
  is_active: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface Category {
  id: number
  parent_id: number | null
  name: string
  is_active: boolean
}

export interface Product {
  id: number
  sku: string
  name: string
  category_id: number
  unit: string
  // количества приходят строками, чтобы не терять точность
  min_stock: string
  target_stock: string | null
  is_active: boolean
}

export interface StockRow {
  product_id: number
  sku: string
  name: string
  unit: string
  on_hand: string
  reserved: string
  available: string
  min_stock: string
  is_low: boolean
}
