import { useQueries } from '@tanstack/react-query'
import { List, Typography } from 'antd'

import { fetchProduct } from '../../api/catalog'
import type { ReservationItem } from '../../api/types'
import { UNIT_LABELS, formatQuantity } from '../../shared'

/** Позиции резерва с названиями товаров (подгружаются по одному и кэшируются). */
export function ReservationItemsList({ items }: { items: ReservationItem[] }) {
  const products = useQueries({
    queries: items.map((item) => ({
      queryKey: ['product', item.product_id],
      queryFn: () => fetchProduct(item.product_id),
      staleTime: 60_000,
    })),
  })

  return (
    <List
      size="small"
      dataSource={items}
      renderItem={(item, index) => {
        const product = products[index]?.data
        return (
          <List.Item>
            <Typography.Text>
              {product ? `${product.sku} · ${product.name}` : `Товар №${item.product_id}`}
            </Typography.Text>
            <Typography.Text strong>
              {formatQuantity(item.quantity)} {product ? (UNIT_LABELS[product.unit] ?? '') : ''}
            </Typography.Text>
          </List.Item>
        )
      }}
    />
  )
}
