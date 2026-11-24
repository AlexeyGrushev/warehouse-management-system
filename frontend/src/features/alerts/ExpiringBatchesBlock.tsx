import { MinusCircleOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Alert, Button, Segmented, Space, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'

import { fetchExpiringBatches } from '../../api/alerts'
import type { ExpiringBatch } from '../../api/types'
import { UNIT_LABELS, expiryLabel, formatQuantity } from '../../shared'
import { useAuth } from '../auth/auth-state'
import { WriteOffModal } from '../stock/WriteOffModal'
import type { WriteOffPreset } from '../stock/WriteOffModal'

const PAGE_SIZE = 10
const HORIZONS = [7, 14, 30, 60]

export function ExpiringBatchesBlock() {
  const [days, setDays] = useState(14)
  const [page, setPage] = useState(1)
  const [preset, setPreset] = useState<WriteOffPreset | null>(null)
  const [writeOffOpen, setWriteOffOpen] = useState(false)
  const { user } = useAuth()
  const canWrite = user !== null && user.role !== 'viewer'

  const batches = useQuery({
    queryKey: ['alerts', 'expiring-batches', days, page],
    queryFn: () => fetchExpiringBatches({ days, page, size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  })

  const columns: TableColumnsType<ExpiringBatch> = [
    {
      title: 'Товар',
      dataIndex: 'product_name',
      render: (name: string, row) => `${row.product_sku} · ${name}`,
    },
    { title: 'Партия', dataIndex: 'batch_no', width: 150 },
    {
      title: 'Остаток',
      dataIndex: 'qty_remaining',
      align: 'right',
      render: (value: string, row) =>
        `${formatQuantity(value)} ${UNIT_LABELS[row.product_unit] ?? row.product_unit}`,
    },
    {
      title: 'Годен до',
      dataIndex: 'expires_at',
      width: 120,
      render: (value: string) => dayjs(value).format('DD.MM.YYYY'),
    },
    {
      title: 'Осталось',
      dataIndex: 'days_left',
      width: 190,
      render: (value: number) => {
        const label = expiryLabel(value)
        return <Tag color={label.color}>{label.text}</Tag>
      },
    },
    { title: 'Поставщик', dataIndex: 'supplier_name', render: (name: string | null) => name ?? '—' },
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
            setPreset({
              id: row.product_id,
              label: `${row.product_sku} · ${row.product_name}`,
              unit: row.product_unit,
              reason: row.is_expired ? 'EXPIRED' : 'SALE',
              quantity: row.qty_remaining,
            })
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
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 32,
        }}
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          Истекает срок годности
        </Typography.Title>
        <Space>
          Горизонт:
          <Segmented<number>
            value={days}
            options={HORIZONS.map((value) => ({ value, label: `${value} дн.` }))}
            onChange={(value) => {
              setDays(value)
              setPage(1)
            }}
          />
        </Space>
      </div>
      <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
        Партии с остатком, срок которых наступает в ближайшие {days} дн., и уже просроченные.
      </Typography.Paragraph>
      {batches.isError && (
        <Alert type="error" showIcon message={batches.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<ExpiringBatch>
        rowKey="id"
        columns={columns}
        dataSource={batches.data?.items}
        loading={batches.isFetching}
        onRow={(row) => ({ style: { background: row.is_expired ? '#fff1f0' : undefined } })}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: batches.data?.total ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
        locale={{ emptyText: 'Партий с истекающим сроком нет' }}
      />
      <WriteOffModal open={writeOffOpen} preset={preset} onClose={() => setWriteOffOpen(false)} />
    </>
  )
}
