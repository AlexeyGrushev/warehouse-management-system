import { EditOutlined, InboxOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Input,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import { archiveSupplier, fetchSupplierPage } from '../../api/suppliers'
import type { Supplier } from '../../api/types'
import { useAuth } from '../auth/auth-state'
import { SupplierModal } from './SupplierModal'

const PAGE_SIZE = 20

export function SuppliersPage() {
  const [search, setSearch] = useState('')
  const [showArchived, setShowArchived] = useState(false)
  const [page, setPage] = useState(1)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Supplier | null>(null)
  const { user } = useAuth()
  const canWrite = user !== null && user.role !== 'viewer'
  const queryClient = useQueryClient()

  const suppliers = useQuery({
    queryKey: ['suppliers', search, showArchived, page],
    queryFn: () =>
      fetchSupplierPage({
        q: search,
        isActive: showArchived ? undefined : true,
        page,
        size: PAGE_SIZE,
      }),
    placeholderData: (previous) => previous,
  })

  const archive = useMutation({
    mutationFn: archiveSupplier,
    onSuccess: () => {
      message.success('Поставщик перенесён в архив')
      for (const key of ['suppliers', 'supplier-options']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : 'Не удалось архивировать'),
  })

  const columns: TableColumnsType<Supplier> = [
    { title: 'Название', dataIndex: 'name' },
    {
      title: 'Контакты',
      dataIndex: 'contact',
      render: (value: string | null) => value ?? '—',
    },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      width: 120,
      render: (active: boolean) =>
        active ? <Tag color="green">активен</Tag> : <Tag>в архиве</Tag>,
    },
  ]

  if (canWrite) {
    columns.push({
      title: '',
      width: 210,
      render: (_, row) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditing(row)
              setModalOpen(true)
            }}
          >
            Изменить
          </Button>
          {row.is_active && (
            <Popconfirm
              title="Архивировать поставщика?"
              description="Нельзя, пока у него есть партии с остатком на складе."
              okText="В архив"
              cancelText="Нет"
              onConfirm={() => archive.mutate(row.id)}
            >
              <Button
                size="small"
                icon={<InboxOutlined />}
                loading={archive.isPending && archive.variables === row.id}
              >
                В архив
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    })
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography.Title level={3} style={{ marginTop: 0 }}>
          Поставщики
        </Typography.Title>
        {canWrite && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditing(null)
              setModalOpen(true)
            }}
          >
            Новый поставщик
          </Button>
        )}
      </div>
      <Space wrap size="large" style={{ marginBottom: 16 }}>
        <Input.Search
          allowClear
          placeholder="Поиск по названию и контактам"
          style={{ width: 360 }}
          onSearch={(value) => {
            setSearch(value.trim())
            setPage(1)
          }}
        />
        <Space>
          <Switch
            checked={showArchived}
            onChange={(checked) => {
              setShowArchived(checked)
              setPage(1)
            }}
          />
          Показывать архивные
        </Space>
      </Space>
      {suppliers.isError && (
        <Alert type="error" showIcon message={suppliers.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<Supplier>
        rowKey="id"
        columns={columns}
        dataSource={suppliers.data?.items}
        loading={suppliers.isFetching}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: suppliers.data?.total ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
        locale={{ emptyText: 'Поставщики не найдены' }}
      />
      <SupplierModal open={modalOpen} supplier={editing} onClose={() => setModalOpen(false)} />
    </>
  )
}
