import { useQuery } from '@tanstack/react-query'
import { Alert, Input, Space, Switch, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { useState } from 'react'

import { fetchStock } from '../../api/stock'
import type { StockRow } from '../../api/types'
import { UNIT_LABELS, formatQuantity } from '../../shared'

const PAGE_SIZE = 20

export function StockPage() {
  const [search, setSearch] = useState('')
  const [lowOnly, setLowOnly] = useState(false)
  const [page, setPage] = useState(1)

  const stock = useQuery({
    queryKey: ['stock', search, lowOnly, page],
    queryFn: () => fetchStock({ q: search, lowOnly, page, size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  })

  const quantity = (value: string) => formatQuantity(value)
  const columns: TableColumnsType<StockRow> = [
    { title: 'Артикул', dataIndex: 'sku', width: 120 },
    { title: 'Название', dataIndex: 'name' },
    {
      title: 'Ед.',
      dataIndex: 'unit',
      width: 80,
      render: (unit: string) => UNIT_LABELS[unit] ?? unit,
    },
    { title: 'На складе', dataIndex: 'on_hand', align: 'right', render: quantity },
    { title: 'В резерве', dataIndex: 'reserved', align: 'right', render: quantity },
    {
      title: 'Доступно',
      dataIndex: 'available',
      align: 'right',
      render: (value: string, row) => (
        <strong style={{ color: row.is_low ? '#cf1322' : undefined }}>{quantity(value)}</strong>
      ),
    },
    { title: 'Мин. остаток', dataIndex: 'min_stock', align: 'right', render: quantity },
    {
      title: 'Статус',
      dataIndex: 'is_low',
      width: 170,
      render: (low: boolean) =>
        low ? <Tag color="red">ниже минимума</Tag> : <Tag color="green">в норме</Tag>,
    },
  ]

  return (
    <>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Остатки
      </Typography.Title>
      <Space wrap size="large" style={{ marginBottom: 16 }}>
        <Input.Search
          allowClear
          placeholder="Поиск по названию или артикулу"
          style={{ width: 360 }}
          onSearch={(value) => {
            setSearch(value.trim())
            setPage(1)
          }}
        />
        <Space>
          <Switch
            checked={lowOnly}
            onChange={(checked) => {
              setLowOnly(checked)
              setPage(1)
            }}
          />
          Только ниже минимума
        </Space>
      </Space>
      {stock.isError && (
        <Alert type="error" showIcon message={stock.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<StockRow>
        rowKey="product_id"
        columns={columns}
        dataSource={stock.data?.items}
        loading={stock.isFetching}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: stock.data?.total ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
        locale={{ emptyText: 'Товары не найдены' }}
      />
    </>
  )
}
