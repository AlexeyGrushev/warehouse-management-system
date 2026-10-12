import { useQuery } from '@tanstack/react-query'
import { Alert, Input, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { useMemo, useState } from 'react'

import { fetchCategories, fetchProducts } from '../../api/catalog'
import type { Product } from '../../api/types'

const PAGE_SIZE = 20

const UNIT_LABELS: Record<string, string> = {
  pcs: 'шт',
  kg: 'кг',
  l: 'л',
  m: 'м',
  box: 'упак',
}

export function ProductsPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  const products = useQuery({
    queryKey: ['products', search, page],
    queryFn: () => fetchProducts({ q: search, page, size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  })
  const categories = useQuery({ queryKey: ['categories'], queryFn: fetchCategories })

  const categoryNames = useMemo(
    () => new Map(categories.data?.map((category) => [category.id, category.name])),
    [categories.data],
  )

  const columns: TableColumnsType<Product> = [
    { title: 'Артикул', dataIndex: 'sku', width: 120 },
    { title: 'Название', dataIndex: 'name' },
    {
      title: 'Категория',
      dataIndex: 'category_id',
      render: (id: number) => categoryNames.get(id) ?? '—',
    },
    {
      title: 'Ед.',
      dataIndex: 'unit',
      width: 80,
      render: (unit: string) => UNIT_LABELS[unit] ?? unit,
    },
    {
      title: 'Мин. остаток',
      dataIndex: 'min_stock',
      align: 'right',
      render: (value: string) => Number(value).toLocaleString('ru-RU'),
    },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      width: 120,
      render: (active: boolean) =>
        active ? <Tag color="green">активен</Tag> : <Tag>в архиве</Tag>,
    },
  ]

  return (
    <>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Товары
      </Typography.Title>
      <Input.Search
        allowClear
        placeholder="Поиск по названию или артикулу"
        style={{ maxWidth: 360, marginBottom: 16 }}
        onSearch={(value) => {
          setSearch(value.trim())
          setPage(1)
        }}
      />
      {products.isError && (
        <Alert type="error" showIcon message={products.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<Product>
        rowKey="id"
        columns={columns}
        dataSource={products.data?.items}
        loading={products.isFetching}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: products.data?.total ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
        locale={{ emptyText: 'Товары не найдены' }}
      />
    </>
  )
}
