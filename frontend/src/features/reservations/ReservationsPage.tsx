import { CheckOutlined, CloseOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import { cancelReservation, fetchReservations, fulfillReservation } from '../../api/reservations'
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
  const queryClient = useQueryClient()

  const refresh = () => {
    for (const key of ['reservations', 'stock', 'product-stock', 'movements']) {
      void queryClient.invalidateQueries({ queryKey: [key] })
    }
  }
  const onError = (e: Error) =>
    message.error(e instanceof ApiError ? e.message : 'Не удалось выполнить действие')

  const cancel = useMutation({
    mutationFn: cancelReservation,
    onSuccess: (reservation) => {
      message.success(`Резерв по заказу ${reservation.reference} отменён`)
      refresh()
    },
    onError,
  })
  const fulfill = useMutation({
    mutationFn: fulfillReservation,
    onSuccess: (reservation) => {
      message.success(`Заказ ${reservation.reference} отгружен, товар списан со склада`)
      refresh()
    },
    onError,
  })

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

  if (canWrite) {
    columns.push({
      title: '',
      width: 230,
      render: (_, row) => {
        if (row.status !== 'ACTIVE') {
          return null
        }
        const overdue = new Date(row.expires_at).getTime() <= Date.now()
        return (
          <Space>
            <Tooltip title={overdue ? 'Срок действия истёк, резерв скоро освободится сам' : undefined}>
              <Popconfirm
                title="Исполнить резерв?"
                description="Товар будет списан со склада по FEFO."
                okText="Исполнить"
                cancelText="Нет"
                onConfirm={() => fulfill.mutate(row.id)}
                disabled={overdue}
              >
                <Button
                  size="small"
                  type="primary"
                  icon={<CheckOutlined />}
                  disabled={overdue}
                  loading={fulfill.isPending && fulfill.variables === row.id}
                >
                  Исполнить
                </Button>
              </Popconfirm>
            </Tooltip>
            <Popconfirm
              title="Отменить резерв?"
              description="Количество вернётся в «Доступно»."
              okText="Отменить резерв"
              okButtonProps={{ danger: true }}
              cancelText="Нет"
              onConfirm={() => cancel.mutate(row.id)}
            >
              <Button
                size="small"
                danger
                icon={<CloseOutlined />}
                loading={cancel.isPending && cancel.variables === row.id}
              >
                Отменить
              </Button>
            </Popconfirm>
          </Space>
        )
      },
    })
  }

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
        scroll={{ x: 'max-content' }}
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
