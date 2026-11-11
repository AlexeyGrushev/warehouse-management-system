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
import { useMemo, useState } from 'react'

import { archiveProduct, fetchCategories, fetchProducts } from '../../api/catalog'
import { ApiError } from '../../api/client'
import type { Product } from '../../api/types'
import { UNIT_LABELS } from '../../shared'
import { useAuth } from '../auth/auth-state'
import { ProductModal } from './ProductModal'

const PAGE_SIZE = 20

export function ProductsPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [showArchived, setShowArchived] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Product | null>(null)
  const { user } = useAuth()
  const canWrite = user !== null && user.role !== 'viewer'
  const queryClient = useQueryClient()

  const products = useQuery({
    queryKey: ['products', search, showArchived, page],
    queryFn: () =>
      fetchProducts({ q: search, isActive: showArchived ? undefined : true, page, size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  })
  const categories = useQuery({ queryKey: ['categories'], queryFn: fetchCategories })

  const categoryNames = useMemo(
    () => new Map(categories.data?.map((category) => [category.id, category.name])),
    [categories.data],
  )

  const archive = useMutation({
    mutationFn: archiveProduct,
    onSuccess: () => {
      message.success('Товар перенесён в архив')
      for (const key of ['products', 'product-options', 'stock']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : 'Не удалось архивировать'),
  })

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
              title="Архивировать товар?"
              description="Архивировать можно, только когда на складе нет остатка и резервов."
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
          Товары
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
            Новый товар
          </Button>
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
            checked={showArchived}
            onChange={(checked) => {
              setShowArchived(checked)
              setPage(1)
            }}
          />
          Показывать архивные
        </Space>
      </Space>
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
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: 'Товары не найдены' }}
      />
      <ProductModal open={modalOpen} product={editing} onClose={() => setModalOpen(false)} />
    </>
  )
}
