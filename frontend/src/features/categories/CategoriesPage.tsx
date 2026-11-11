import { EditOutlined, InboxOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Popconfirm, Space, Switch, Table, Tag, Typography, message } from 'antd'
import type { TableColumnsType } from 'antd'
import { useMemo, useState } from 'react'

import { archiveCategory, fetchCategoryTree } from '../../api/catalog'
import { ApiError } from '../../api/client'
import type { CategoryNode } from '../../api/types'
import { useAuth } from '../auth/auth-state'
import { CategoryModal } from './CategoryModal'
import type { CategoryDialog } from './CategoryModal'

/** Строка таблицы: у листьев нет children, иначе таблица рисует значок раскрытия. */
interface CategoryRow {
  id: number
  name: string
  is_active: boolean
  children?: CategoryRow[]
}

function toRows(nodes: CategoryNode[], showArchived: boolean): CategoryRow[] {
  return nodes
    .filter((node) => showArchived || node.is_active)
    .map((node) => {
      const children = toRows(node.children, showArchived)
      return {
        id: node.id,
        name: node.name,
        is_active: node.is_active,
        children: children.length ? children : undefined,
      }
    })
}

function indexNodes(nodes: CategoryNode[], into = new Map<number, CategoryNode>()) {
  for (const node of nodes) {
    into.set(node.id, node)
    indexNodes(node.children, into)
  }
  return into
}

export function CategoriesPage() {
  const [showArchived, setShowArchived] = useState(false)
  const [dialog, setDialog] = useState<CategoryDialog | null>(null)
  const { user } = useAuth()
  const canWrite = user !== null && user.role !== 'viewer'
  const queryClient = useQueryClient()

  const tree = useQuery({ queryKey: ['categories-tree'], queryFn: fetchCategoryTree })
  const rows = useMemo(() => toRows(tree.data ?? [], showArchived), [tree.data, showArchived])
  const nodes = useMemo(() => indexNodes(tree.data ?? []), [tree.data])

  const archive = useMutation({
    mutationFn: archiveCategory,
    onSuccess: () => {
      message.success('Категория перенесена в архив')
      for (const key of ['categories', 'categories-tree']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : 'Не удалось архивировать'),
  })

  const columns: TableColumnsType<CategoryRow> = [
    { title: 'Название', dataIndex: 'name' },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      width: 120,
      render: (active: boolean) =>
        active ? <Tag color="green">активна</Tag> : <Tag>в архиве</Tag>,
    },
  ]

  if (canWrite) {
    columns.push({
      title: '',
      width: 340,
      render: (_, row) => (
        <Space>
          {row.is_active && (
            <Button
              size="small"
              icon={<PlusOutlined />}
              onClick={() => setDialog({ kind: 'create', parentId: row.id })}
            >
              Подкатегория
            </Button>
          )}
          <Button size="small" icon={<EditOutlined />} onClick={() => {
              const node = nodes.get(row.id)
              if (node) {
                setDialog({ kind: 'edit', category: node })
              }
            }}>
            Изменить
          </Button>
          {row.is_active && (
            <Popconfirm
              title="Архивировать категорию?"
              description="Нельзя, если в ней есть активные товары или подкатегории."
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
          Категории
        </Typography.Title>
        {canWrite && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setDialog({ kind: 'create', parentId: null })}>
            Новая категория
          </Button>
        )}
      </div>
      <Space style={{ marginBottom: 16 }}>
        <Switch checked={showArchived} onChange={setShowArchived} />
        Показывать архивные
      </Space>
      {tree.isError && (
        <Alert type="error" showIcon message={tree.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<CategoryRow>
        // таблица создаётся заново, когда данные загрузились, чтобы все ветки были раскрыты
        key={tree.isSuccess ? 'ready' : 'loading'}
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={tree.isFetching}
        pagination={false}
        expandable={{ defaultExpandAllRows: true }}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: 'Категорий пока нет' }}
      />
      <CategoryModal dialog={dialog} tree={tree.data ?? []} onClose={() => setDialog(null)} />
    </>
  )
}
