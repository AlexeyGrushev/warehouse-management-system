import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Descriptions,
  Popconfirm,
  Progress,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import {
  cancelStocktaking,
  closeStocktaking,
  fetchStocktaking,
  setCountedQuantity,
  startStocktaking,
} from '../../api/stocktaking'
import type { StocktakingDetail, StocktakingLine } from '../../api/types'
import { STOCKTAKING_STATUSES, UNIT_LABELS, formatDateTime, formatQuantity } from '../../shared'
import { useAuth } from '../auth/auth-state'
import { CountedInput } from './CountedInput'

function diffColor(diff: string): string | undefined {
  const value = Number(diff)
  return value > 0 ? '#389e0d' : value < 0 ? '#cf1322' : undefined
}

export function StocktakingPage() {
  const id = Number(useParams().id)
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const canWrite = user !== null && user.role !== 'viewer'
  const [onlyDifferences, setOnlyDifferences] = useState(false)
  const [savingProduct, setSavingProduct] = useState<number>()

  const query = useQuery({ queryKey: ['stocktaking', id], queryFn: () => fetchStocktaking(id) })
  const data = query.data

  const update = (result: StocktakingDetail) => {
    queryClient.setQueryData(['stocktaking', id], result)
    void queryClient.invalidateQueries({ queryKey: ['stocktakings'] })
  }
  const onError = (e: Error) =>
    message.error(e instanceof ApiError ? e.message : 'Не удалось выполнить действие')

  const start = useMutation({
    mutationFn: () => startStocktaking(id),
    onSuccess: (result) => {
      update(result)
      message.success('Инвентаризация начата: движения по этим товарам временно запрещены')
    },
    onError,
  })
  const cancel = useMutation({
    mutationFn: () => cancelStocktaking(id),
    onSuccess: (result) => {
      update(result)
      message.success('Инвентаризация отменена')
    },
    onError,
  })
  const close = useMutation({
    mutationFn: () => closeStocktaking(id),
    onSuccess: (result) => {
      update(result)
      for (const key of ['stock', 'product-stock', 'movements']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
      message.success('Инвентаризация закрыта, расхождения проведены корректировками')
    },
    onError,
  })
  const count = useMutation({
    mutationFn: ({ productId, value }: { productId: number; value: string }) => {
      setSavingProduct(productId)
      return setCountedQuantity(id, productId, value)
    },
    onSuccess: update,
    onError,
    onSettled: () => setSavingProduct(undefined),
  })

  if (query.isError) {
    return <Alert type="error" showIcon message={query.error.message} />
  }
  if (!data) {
    return null
  }

  const inProgress = data.status === 'IN_PROGRESS'
  const allCounted = data.lines_counted === data.lines_total
  const differences = data.lines.filter((line) => line.diff !== null && Number(line.diff) !== 0)
  const shortage = differences.filter((line) => Number(line.diff) < 0).length
  const surplus = differences.length - shortage
  const rows = onlyDifferences ? differences : data.lines

  const columns: TableColumnsType<StocktakingLine> = [
    { title: 'Артикул', dataIndex: 'sku', width: 120 },
    { title: 'Название', dataIndex: 'name' },
    {
      title: 'Ед.',
      dataIndex: 'unit',
      width: 70,
      render: (unit: string) => UNIT_LABELS[unit] ?? unit,
    },
    {
      title: 'Ожидали',
      dataIndex: 'expected_qty',
      align: 'right',
      render: (value: string | null) => (value === null ? '—' : formatQuantity(value)),
    },
    {
      title: 'Насчитали',
      dataIndex: 'counted_qty',
      align: 'right',
      width: 160,
      render: (value: string | null, row) =>
        canWrite && inProgress ? (
          <CountedInput
            // при обновлении данных с сервера поле перерисовывается с актуальным значением
            key={`${row.product_id}-${value}`}
            value={value}
            unit={row.unit}
            saving={savingProduct === row.product_id}
            onCommit={(next) => count.mutate({ productId: row.product_id, value: next })}
          />
        ) : value === null ? (
          '—'
        ) : (
          formatQuantity(value)
        ),
    },
    {
      title: 'Расхождение',
      dataIndex: 'diff',
      align: 'right',
      width: 130,
      render: (value: string | null) =>
        value === null ? (
          '—'
        ) : (
          <strong style={{ color: diffColor(value) }}>
            {Number(value) > 0 ? '+' : ''}
            {formatQuantity(value)}
          </strong>
        ),
    },
  ]

  return (
    <>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div>
          <Link to="/stocktakings">← Все инвентаризации</Link>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography.Title level={3} style={{ margin: '8px 0' }}>
              Инвентаризация №{data.id}{' '}
              <Tag color={STOCKTAKING_STATUSES[data.status].color}>
                {STOCKTAKING_STATUSES[data.status].label}
              </Tag>
            </Typography.Title>
            {canWrite && (
              <Space>
                {data.status === 'DRAFT' && (
                  <Popconfirm
                    title="Начать инвентаризацию?"
                    description="Ожидаемые остатки будут зафиксированы, а приход, списание и новые резервы по этим товарам — запрещены, пока вы не закроете или не отмените сессию."
                    okText="Начать"
                    cancelText="Нет"
                    onConfirm={() => start.mutate()}
                  >
                    <Button type="primary" loading={start.isPending}>
                      Начать
                    </Button>
                  </Popconfirm>
                )}
                {(data.status === 'DRAFT' || inProgress) && (
                  <Popconfirm
                    title="Отменить инвентаризацию?"
                    okText="Отменить"
                    okButtonProps={{ danger: true }}
                    cancelText="Нет"
                    onConfirm={() => cancel.mutate()}
                  >
                    <Button danger loading={cancel.isPending}>
                      Отменить
                    </Button>
                  </Popconfirm>
                )}
                {inProgress && (
                  <Popconfirm
                    title="Закрыть инвентаризацию?"
                    description={`Расхождений: ${differences.length}. Они будут проведены корректировками склада, это действие нельзя отменить.`}
                    okText="Закрыть"
                    cancelText="Нет"
                    disabled={!allCounted}
                    onConfirm={() => close.mutate()}
                  >
                    <Button type="primary" disabled={!allCounted} loading={close.isPending}>
                      Закрыть и провести
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            )}
          </div>
        </div>

        <Descriptions size="small" column={{ xs: 1, sm: 2, md: 4 }}>
          <Descriptions.Item label="Создана">{formatDateTime(data.created_at)}</Descriptions.Item>
          <Descriptions.Item label="Начата">
            {data.started_at ? formatDateTime(data.started_at) : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Завершена">
            {data.closed_at ? formatDateTime(data.closed_at) : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Позиций">{data.lines_total}</Descriptions.Item>
        </Descriptions>

        {inProgress && (
          <>
            <Progress
              percent={Math.round((data.lines_counted / Math.max(data.lines_total, 1)) * 100)}
              format={() => `${data.lines_counted} из ${data.lines_total}`}
            />
            {!allCounted && (
              <Alert
                type="info"
                showIcon
                message="Введите «насчитали» по всем позициям: значение сохраняется при выходе из поля или по Enter. Закрыть инвентаризацию можно, когда заполнено всё."
              />
            )}
          </>
        )}
        {data.lines_counted > 0 && (
          <Space>
            <Tag color={shortage ? 'red' : 'default'}>Недостач: {shortage}</Tag>
            <Tag color={surplus ? 'green' : 'default'}>Излишков: {surplus}</Tag>
            <Space>
              <Switch checked={onlyDifferences} onChange={setOnlyDifferences} />
              Только расхождения
            </Space>
          </Space>
        )}
        <Table<StocktakingLine>
          rowKey="product_id"
          columns={columns}
          dataSource={rows}
          scroll={{ x: 'max-content' }}
          pagination={{ pageSize: 50, showSizeChanger: false, hideOnSinglePage: true }}
          locale={{ emptyText: onlyDifferences ? 'Расхождений нет' : 'Позиций нет' }}
        />
      </Space>
    </>
  )
}
