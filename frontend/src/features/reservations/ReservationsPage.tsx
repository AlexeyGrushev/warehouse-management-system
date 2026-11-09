import { PlusOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Alert, Button, Input, Select, Space, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { useState } from 'react'

import { fetchReservations } from '../../api/reservations'
import type { Reservation, ReservationStatus } from '../../api/types'
import { RESERVATION_STATUSES, formatDateTime } from '../../shared'
import { useAuth } from '../auth/auth-state'
import { ReservationItemsList } from './ReservationItemsList'
import { ReservationModal } from './ReservationModal'

const PAGE_SIZE = 20

export function ReservationsPage() {
  const [reference, setReference] = useState('')
  const [status, setStatus] = useState<ReservationStatus>()
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const { user } = useAuth()
  const canWrite = user !== null && user.role !== 'viewer'

  const reservations = useQuery({
    queryKey: ['reservations', reference, status, page],
    queryFn: () => fetchReservations({ reference, status, page, size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  })

  const columns: TableColumnsType<Reservation> = [
    { title: '№', dataIndex: 'id', width: 70 },
    { title: 'Заказ', dataIndex: 'reference' },
    {
      title: 'Статус',
      dataIndex: 'status',
      width: 120,
      render: (value: ReservationStatus) => (
        <Tag color={RESERVATION_STATUSES[value].color}>{RESERVATION_STATUSES[value].label}</Tag>
      ),
    },
    {
      title: 'Позиций',
      dataIndex: 'items',
      width: 90,
      align: 'right',
      render: (items: Reservation['items']) => items.length,
    },
    {
      title: 'Создан',
      dataIndex: 'created_at',
      width: 150,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: 'Действует до',
      dataIndex: 'expires_at',
      width: 150,
      render: (value: string) => formatDateTime(value),
    },
  ]

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography.Title level={3} style={{ marginTop: 0 }}>
          Резервы
        </Typography.Title>
        {canWrite && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            Новый резерв
          </Button>
        )}
      </div>
      <Space wrap size="middle" style={{ marginBottom: 16 }}>
        <Input.Search
          allowClear
          placeholder="Поиск по номеру заказа"
          style={{ width: 300 }}
          onSearch={(value) => {
            setReference(value.trim())
            setPage(1)
          }}
        />
        <Select
          allowClear
          placeholder="Все статусы"
          style={{ width: 180 }}
          value={status}
          options={(Object.keys(RESERVATION_STATUSES) as ReservationStatus[]).map((key) => ({
            value: key,
            label: RESERVATION_STATUSES[key].label,
          }))}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
      </Space>
      {reservations.isError && (
        <Alert type="error" showIcon message={reservations.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<Reservation>
        rowKey="id"
        columns={columns}
        dataSource={reservations.data?.items}
        loading={reservations.isFetching}
        expandable={{ expandedRowRender: (row) => <ReservationItemsList items={row.items} /> }}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: reservations.data?.total ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
        locale={{ emptyText: 'Резервов нет' }}
      />
      <ReservationModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </>
  )
}
