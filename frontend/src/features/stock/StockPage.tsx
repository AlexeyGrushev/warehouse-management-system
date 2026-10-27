import { useQuery } from '@tanstack/react-query'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { Alert, Button, Input, Space, Switch, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { useState } from 'react'

import { fetchStock } from '../../api/stock'
import type { StockRow } from '../../api/types'
import { UNIT_LABELS, formatQuantity } from '../../shared'
import { useAuth } from '../auth/auth-state'
import { ReceiptModal } from './ReceiptModal'
import { WriteOffModal } from './WriteOffModal'
import type { WriteOffPreset } from './WriteOffModal'

const PAGE_SIZE = 20

export function StockPage() {
  const [search, setSearch] = useState('')
  const [lowOnly, setLowOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [receiptOpen, setReceiptOpen] = useState(false)
  const [writeOffOpen, setWriteOffOpen] = useState(false)
  const [writeOffPreset, setWriteOffPreset] = useState<WriteOffPreset | null>(null)
  const { user } = useAuth()
  const canWrite = user !== null && user.role !== 'viewer'

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

  if (canWrite) {
    columns.push({
      title: '',
      width: 110,
      render: (_, row) => (
        <Button
          size="small"
          icon={<MinusCircleOutlined />}
          onClick={() => {
            setWriteOffPreset({ id: row.product_id, label: `${row.sku} · ${row.name}`, unit: row.unit })
            setWriteOffOpen(true)
          }}
        >
          Списать
        </Button>
      ),
    })
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography.Title level={3} style={{ marginTop: 0 }}>
          Остатки
        </Typography.Title>
        {canWrite && (
          <Space>
            <Button
              danger
              icon={<MinusCircleOutlined />}
              onClick={() => {
                setWriteOffPreset(null)
                setWriteOffOpen(true)
              }}
            >
              Списать
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setReceiptOpen(true)}>
              Принять партию
            </Button>
          </Space>
        )}
      </div>
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
      <ReceiptModal open={receiptOpen} onClose={() => setReceiptOpen(false)} />
      <WriteOffModal
        open={writeOffOpen}
        preset={writeOffPreset}
        onClose={() => setWriteOffOpen(false)}
      />
    </>
  )
}
