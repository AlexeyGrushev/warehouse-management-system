import { useQuery } from '@tanstack/react-query'
import { Select } from 'antd'
import { useState } from 'react'

import { fetchProducts } from '../api/catalog'
import type { Product } from '../api/types'
import { useDebounced } from '../hooks'

interface Props {
  value?: number
  onChange?: (id: number | undefined, product?: Product) => void
  allowClear?: boolean
  placeholder?: string
}

/** Выбор товара с поиском по названию и артикулу (только активные товары). */
export function ProductSelect({ value, onChange, allowClear, placeholder }: Props) {
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search.trim())
  const products = useQuery({
    queryKey: ['product-options', debounced],
    queryFn: () => fetchProducts({ q: debounced, isActive: true, page: 1, size: 20 }),
  })
  const items = products.data?.items ?? []

  return (
    <Select
      showSearch
      allowClear={allowClear}
      value={value}
      placeholder={placeholder ?? 'Начните вводить название или артикул'}
      filterOption={false}
      onSearch={setSearch}
      loading={products.isFetching}
      notFoundContent="Ничего не найдено"
      options={items.map((product) => ({
        value: product.id,
        label: `${product.sku} · ${product.name}`,
      }))}
      onChange={(id) => onChange?.(id, items.find((product) => product.id === id))}
    />
  )
}
