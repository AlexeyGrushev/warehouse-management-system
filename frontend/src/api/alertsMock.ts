// Заглушки ответов для разработки экранов без бэкенда: VITE_MOCK_ALERTS=true npm run dev
import type { ExpiringBatch, LowStockItem, Page } from './types'

function page<T>(items: T[]): Page<T> {
  return { items, total: items.length, page: 1, size: items.length }
}

export const MOCK_LOW_STOCK: Page<LowStockItem> = page([
  {
    product_id: 1,
    sku: 'MLK-001',
    name: 'Молоко 2,5% 1 л',
    unit: 'pcs',
    category_id: 2,
    category_name: 'Молочные продукты',
    on_hand: '0.000',
    reserved: '0.000',
    available: '0.000',
    min_stock: '40.000',
    target_stock: '120.000',
    deficit: '40.000',
    recommended_order_qty: '120.000',
    severity: 'CRITICAL',
  },
  {
    product_id: 2,
    sku: 'BRD-002',
    name: 'Хлеб ржаной',
    unit: 'pcs',
    category_id: 3,
    category_name: 'Хлеб и выпечка',
    on_hand: '22.000',
    reserved: '4.000',
    available: '18.000',
    min_stock: '20.000',
    target_stock: '60.000',
    deficit: '2.000',
    recommended_order_qty: '42.000',
    severity: 'WARNING',
  },
])

export const MOCK_EXPIRING: Page<ExpiringBatch> = page([
  {
    id: 1,
    product_id: 1,
    supplier_id: 1,
    batch_no: '20261110-1',
    qty_received: '30.000',
    qty_remaining: '12.000',
    unit_cost: '47.00',
    received_at: '2026-11-10',
    expires_at: '2026-11-20',
    product_sku: 'MLK-001',
    product_name: 'Молоко 2,5% 1 л',
    product_unit: 'pcs',
    supplier_name: 'ООО «Молочный дом»',
    days_left: -4,
    is_expired: true,
  },
  {
    id: 2,
    product_id: 3,
    supplier_id: 1,
    batch_no: '20261115-2',
    qty_received: '40.000',
    qty_remaining: '25.000',
    unit_cost: '61.00',
    received_at: '2026-11-15',
    expires_at: '2026-11-29',
    product_sku: 'MLK-003',
    product_name: 'Кефир 1% 0,9 л',
    product_unit: 'pcs',
    supplier_name: 'ООО «Молочный дом»',
    days_left: 5,
    is_expired: false,
  },
])
