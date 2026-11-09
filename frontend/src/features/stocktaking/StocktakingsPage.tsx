import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Form, Modal, Select, Space, Table, Tag, Typography, message } from 'antd'
import type { TableColumnsType } from 'antd'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { fetchCategories } from '../../api/catalog'
import { ApiError } from '../../api/client'
import { createStocktaking, fetchStocktakings } from '../../api/stocktaking'
import type { StocktakingStatus, StocktakingSummary } from '../../api/types'
import { STOCKTAKING_STATUSES, formatDateTime } from '../../shared'
import { useAuth } from '../auth/auth-state'

const PAGE_SIZE = 20

export function StocktakingsPage() {
  const [status, setStatus] = useState<StocktakingStatus>()
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [categoryId, setCategoryId] = useState<number>()
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const canWrite = user !== null && user.role !== 'viewer'

  const sessions = useQuery({
    queryKey: ['stocktakings', status, page],
    queryFn: () => fetchStocktakings({ status, page, size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  })
  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
    enabled: createOpen,
  })

  const create = useMutation({
    mutationFn: () => createStocktaking(categoryId),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ['stocktakings'] })
      closeCreate()
      message.success(`Инвентаризация №${created.id} создана: ${created.lines_total} позиций`)
      navigate(`/stocktakings/${created.id}`)
    },
    onError: (e) =>
      setError(e instanceof ApiError ? e.message : 'Не удалось создать инвентаризацию'),
  })

  function closeCreate() {
    setCreateOpen(false)
    setCategoryId(undefined)
    setError(null)
  }

  const columns: TableColumnsType<StocktakingSummary> = [
    {
      title: '№',
      dataIndex: 'id',
      width: 80,
      render: (id: number) => <Link to={`/stocktakings/${id}`}>{id}</Link>,
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      width: 120,
      render: (value: StocktakingStatus) => (
        <Tag color={STOCKTAKING_STATUSES[value].color}>{STOCKTAKING_STATUSES[value].label}</Tag>
      ),
    },
    {
      title: 'Введено / всего',
      align: 'right',
      render: (_, row) => `${row.lines_counted} / ${row.lines_total}`,
    },
    {
      title: 'Создана',
      dataIndex: 'created_at',
      render: (value: string) => formatDateTime(value),
    },
    {
      title: 'Начата',
      dataIndex: 'started_at',
      render: (value: string | null) => (value ? formatDateTime(value) : '—'),
    },
    {
      title: 'Завершена',
      dataIndex: 'closed_at',
      render: (value: string | null) => (value ? formatDateTime(value) : '—'),
    },
  ]

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography.Title level={3} style={{ marginTop: 0 }}>
          Инвентаризация
        </Typography.Title>
        {canWrite && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            Новая инвентаризация
          </Button>
        )}
      </div>
      <Space style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="Все статусы"
          style={{ width: 180 }}
          value={status}
          options={(Object.keys(STOCKTAKING_STATUSES) as StocktakingStatus[]).map((key) => ({
            value: key,
            label: STOCKTAKING_STATUSES[key].label,
          }))}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
      </Space>
      {sessions.isError && (
        <Alert type="error" showIcon message={sessions.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<StocktakingSummary>
        rowKey="id"
        columns={columns}
        dataSource={sessions.data?.items}
        loading={sessions.isFetching}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: sessions.data?.total ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
        locale={{ emptyText: 'Инвентаризаций пока нет' }}
      />
      <Modal
        title="Новая инвентаризация"
        open={createOpen}
        onCancel={closeCreate}
        onOk={() => {
          setError(null)
          create.mutate()
        }}
        okText="Создать"
        cancelText="Отмена"
        confirmLoading={create.isPending}
        destroyOnHidden
      >
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
        <Form layout="vertical">
          <Form.Item
            label="Что пересчитываем"
            extra="Подкатегории входят в выбранную категорию. Архивные товары не включаются."
          >
            <Select
              allowClear
              placeholder="Все активные товары"
              loading={categories.isFetching}
              value={categoryId}
              onChange={setCategoryId}
              options={categories.data
                ?.filter((category) => category.is_active)
                .map((category) => ({ value: category.id, label: category.name }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
