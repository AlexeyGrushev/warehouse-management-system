import { useQuery } from '@tanstack/react-query'
import { Alert, DatePicker, Select, Space, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import { fetchMovements } from '../../api/stock'
import type { Movement, MovementType } from '../../api/types'
import { ProductSelect } from '../../components/ProductSelect'
import {
  MOVEMENT_TYPES,
  REASON_LABELS,
  formatDateTime,
  formatQuantity,
} from '../../shared'

const PAGE_SIZE = 20
const DATE_FORMAT = 'YYYY-MM-DD'

/** Изменение показываем со знаком: количество на складе или (для резервов) количество в резерве. */
function renderChange(row: Movement) {
  const onHand = Number(row.quantity_delta)
  const value = onHand !== 0 ? row.quantity_delta : row.reserved_delta
  const number = Number(value)
  const text = `${number > 0 ? '+' : ''}${formatQuantity(value)}`
  const suffix = onHand === 0 ? ' (резерв)' : ''
  return (
    <span style={{ color: number > 0 ? '#389e0d' : number < 0 ? '#cf1322' : undefined }}>
      {text}
      {suffix}
    </span>
  )
}

export function MovementsPage() {
  const [productId, setProductId] = useState<number>()
  const [type, setType] = useState<MovementType>()
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const [page, setPage] = useState(1)

  const dateFrom = range?.[0]?.format(DATE_FORMAT)
  const dateTo = range?.[1]?.format(DATE_FORMAT)
  const movements = useQuery({
    queryKey: ['movements', productId, type, dateFrom, dateTo, page],
    queryFn: () => fetchMovements({ productId, type, dateFrom, dateTo, page, size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  })

  const columns: TableColumnsType<Movement> = [
    {
      title: 'Дата и время',
      dataIndex: 'created_at',
      width: 150,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: 'Тип',
      dataIndex: 'type',
      width: 140,
      render: (value: MovementType) => (
        <Tag color={MOVEMENT_TYPES[value].color}>{MOVEMENT_TYPES[value].label}</Tag>
      ),
    },
    {
      title: 'Товар',
      render: (_, row) => `${row.product_sku} · ${row.product_name}`,
    },
    { title: 'Партия', dataIndex: 'batch_no', render: (value: string | null) => value ?? '—' },
    { title: 'Изменение', align: 'right', render: (_, row) => renderChange(row) },
    {
      title: 'Причина',
      dataIndex: 'reason',
      render: (value: string | null) => (value ? (REASON_LABELS[value] ?? value) : '—'),
    },
    { title: 'Комментарий', dataIndex: 'comment', render: (value: string | null) => value ?? '—' },
    { title: 'Пользователь', dataIndex: 'user_email' },
  ]

  return (
    <>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Журнал движений
      </Typography.Title>
      <Space wrap size="middle" style={{ marginBottom: 16 }}>
        <div style={{ width: 320 }}>
          <ProductSelect
            allowClear
            placeholder="Все товары"
            value={productId}
            onChange={(id) => {
              setProductId(id)
              setPage(1)
            }}
          />
        </div>
        <Select
          allowClear
          placeholder="Все типы"
          style={{ width: 180 }}
          value={type}
          options={(Object.keys(MOVEMENT_TYPES) as MovementType[]).map((key) => ({
            value: key,
            label: MOVEMENT_TYPES[key].label,
          }))}
          onChange={(value) => {
            setType(value)
            setPage(1)
          }}
        />
        <DatePicker.RangePicker
          format="DD.MM.YYYY"
          value={range}
          onChange={(value) => {
            setRange(value)
            setPage(1)
          }}
        />
      </Space>
      {movements.isError && (
        <Alert type="error" showIcon message={movements.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<Movement>
        rowKey="id"
        columns={columns}
        dataSource={movements.data?.items}
        loading={movements.isFetching}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: movements.data?.total ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
        locale={{ emptyText: 'Движений не найдено' }}
      />
    </>
  )
}
