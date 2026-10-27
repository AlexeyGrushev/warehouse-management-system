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

export interface Supplier {
  id: number
  name: string
  contact: string | null
  is_active: boolean
}

export interface Batch {
  id: number
  product_id: number
  supplier_id: number | null
  batch_no: string
  qty_received: string
  qty_remaining: string
  unit_cost: string
  received_at: string
  expires_at: string | null
}

export interface ReceiptInput {
  product_id: number
  supplier_id: number
  batch_no: string
  quantity: string
  unit_cost: string
  received_at: string
  expires_at: string | null
}

export type MovementType = 'RECEIPT' | 'WRITE_OFF' | 'RESERVE' | 'RELEASE' | 'ADJUSTMENT'

export interface Movement {
  id: number
  type: MovementType
  product_id: number
  product_sku: string
  product_name: string
  batch_id: number | null
  batch_no: string | null
  quantity_delta: string
  reserved_delta: string
  reason: string | null
  comment: string | null
  user_id: number
  user_email: string
  created_at: string
}
