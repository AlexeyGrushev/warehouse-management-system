import { useQuery } from '@tanstack/react-query'
import { Alert, Select, Space, Table, Tag, TreeSelect, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { useMemo, useState } from 'react'

import { fetchLowStock } from '../../api/alerts'
import { fetchCategoryTree } from '../../api/catalog'
import type { CategoryNode, LowStockItem, Severity } from '../../api/types'
import { SEVERITIES, UNIT_LABELS, formatQuantity } from '../../shared'
import { ExpiringBatchesBlock } from './ExpiringBatchesBlock'

const PAGE_SIZE = 20

interface TreeNode {
  value: number
  title: string
  children: TreeNode[]
}

function toTreeData(nodes: CategoryNode[]): TreeNode[] {
  return nodes
    .filter((node) => node.is_active)
    .map((node) => ({ value: node.id, title: node.name, children: toTreeData(node.children) }))
}

function withUnit(value: string, unit: string): string {
  return `${formatQuantity(value)} ${UNIT_LABELS[unit] ?? unit}`
}

const byNumber = (field: keyof LowStockItem) => (a: LowStockItem, b: LowStockItem) =>
  Number(a[field]) - Number(b[field])

export function LowStockPage() {
  const [categoryId, setCategoryId] = useState<number>()
  const [severity, setSeverity] = useState<Severity>()
  const [page, setPage] = useState(1)

  const categories = useQuery({ queryKey: ['category-tree'], queryFn: fetchCategoryTree })
  const treeData = useMemo(() => toTreeData(categories.data ?? []), [categories.data])

  const lowStock = useQuery({
    queryKey: ['alerts', 'low-stock', categoryId, severity, page],
    queryFn: () => fetchLowStock({ categoryId, severity, page, size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  })

  const columns: TableColumnsType<LowStockItem> = [
    { title: 'Артикул', dataIndex: 'sku', width: 120 },
    { title: 'Название', dataIndex: 'name' },
    { title: 'Категория', dataIndex: 'category_name' },
    {
      title: 'Доступно',
      dataIndex: 'available',
      align: 'right',
      sorter: byNumber('available'),
      render: (value: string, row) => (
        <strong style={{ color: '#cf1322' }}>{withUnit(value, row.unit)}</strong>
      ),
    },
    {
      title: 'Минимум',
      dataIndex: 'min_stock',
      align: 'right',
      render: (value: string, row) => withUnit(value, row.unit),
    },
    {
      title: 'Дефицит',
      dataIndex: 'deficit',
      align: 'right',
      sorter: byNumber('deficit'),
      render: (value: string, row) => withUnit(value, row.unit),
    },
    {
      title: 'Закупить',
      dataIndex: 'recommended_order_qty',
      align: 'right',
      sorter: byNumber('recommended_order_qty'),
      render: (value: string, row) => <strong>{withUnit(value, row.unit)}</strong>,
    },
    {
      title: 'Критичность',
      dataIndex: 'severity',
      width: 150,
      render: (value: Severity) => <Tag color={SEVERITIES[value].color}>{SEVERITIES[value].label}</Tag>,
    },
  ]

  return (
    <>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Заканчивается
      </Typography.Title>
      <Typography.Paragraph type="secondary">
        Товары, у которых доступно (на складе минус резервы) меньше минимального остатка. «Закупить» —
        сколько нужно до целевого остатка.
      </Typography.Paragraph>
      <Space wrap size="middle" style={{ marginBottom: 16 }}>
        <TreeSelect
          allowClear
          showSearch
          treeNodeFilterProp="title"
          treeDefaultExpandAll
          style={{ width: 280 }}
          placeholder="Все категории"
          treeData={treeData}
          value={categoryId}
          onChange={(value?: number) => {
            setCategoryId(value)
            setPage(1)
          }}
        />
        <Select<Severity>
          allowClear
          style={{ width: 200 }}
          placeholder="Любая критичность"
          value={severity}
          options={[
            { value: 'CRITICAL', label: SEVERITIES.CRITICAL.label },
            { value: 'WARNING', label: SEVERITIES.WARNING.label },
          ]}
          onChange={(value?: Severity) => {
            setSeverity(value)
            setPage(1)
          }}
        />
      </Space>
      {lowStock.isError && (
        <Alert type="error" showIcon message={lowStock.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<LowStockItem>
        rowKey="product_id"
        columns={columns}
        dataSource={lowStock.data?.items}
        loading={lowStock.isFetching}
        onRow={(row) => ({ style: { background: SEVERITIES[row.severity].rowBackground } })}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: lowStock.data?.total ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
        locale={{ emptyText: 'Всё в норме: товаров ниже минимума нет' }}
      />
      <ExpiringBatchesBlock />
    </>
  )
}
