import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Form, Input, InputNumber, Modal, Select, Typography, notification } from 'antd'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import { createWriteOff, fetchProductStock } from '../../api/stock'
import type { Product, WriteOffReason } from '../../api/types'
import { ProductSelect } from '../../components/ProductSelect'
import { REASON_LABELS, UNIT_LABELS, formatQuantity } from '../../shared'

interface FormValues {
  product_id: number
  quantity: string
  reason: WriteOffReason
  comment?: string
}

export interface WriteOffPreset {
  id: number
  label: string
  unit: string
}

interface Props {
  open: boolean
  onClose: () => void
  /** Если товар известен заранее (кнопка в строке таблицы), выбирать его не нужно. */
  preset?: WriteOffPreset | null
}

const REASONS = Object.entries(REASON_LABELS).map(([value, label]) => ({ value, label }))

export function WriteOffModal({ open, onClose, preset }: Props) {
  const [form] = Form.useForm<FormValues>()
  const queryClient = useQueryClient()
  const [picked, setPicked] = useState<Product>()
  const [error, setError] = useState<string | null>(null)

  const productId = preset?.id ?? picked?.id
  const unit = preset?.unit ?? picked?.unit
  const stock = useQuery({
    queryKey: ['product-stock', productId],
    queryFn: () => fetchProductStock(productId as number),
    enabled: open && productId !== undefined,
  })

  const writeOff = useMutation({
    mutationFn: (values: FormValues) =>
      createWriteOff({
        product_id: preset?.id ?? values.product_id,
        quantity: values.quantity,
        reason: values.reason,
        comment: values.comment?.trim() ? values.comment.trim() : null,
      }),
    onSuccess: (result) => {
      const unitLabel = UNIT_LABELS[unit ?? ''] ?? ''
      notification.success({
        message: `Списано ${formatQuantity(result.quantity)} ${unitLabel}`.trim(),
        description: result.lines
          .map((line) => `партия ${line.batch_no}: ${formatQuantity(line.quantity)}`)
          .join('; '),
      })
      for (const key of ['stock', 'movements', 'product-stock']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
      close()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Не удалось выполнить списание'),
  })

  function close() {
    form.resetFields()
    setPicked(undefined)
    setError(null)
    onClose()
  }

  return (
    <Modal
      title="Списание"
      open={open}
      onCancel={close}
      onOk={() => form.submit()}
      okText="Списать"
      okButtonProps={{ danger: true }}
      cancelText="Отмена"
      confirmLoading={writeOff.isPending}
      destroyOnHidden
      width={480}
    >
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
      <Form<FormValues>
        form={form}
        layout="vertical"
        requiredMark={false}
        initialValues={{ reason: 'SALE' }}
        onFinish={(values) => {
          setError(null)
          writeOff.mutate(values)
        }}
      >
        {preset ? (
          <Form.Item label="Товар">
            <Input value={preset.label} disabled />
          </Form.Item>
        ) : (
          <Form.Item
            label="Товар"
            name="product_id"
            rules={[{ required: true, message: 'Выберите товар' }]}
          >
            <ProductSelect
              onChange={(id, selected) => {
                setPicked(selected)
                form.setFieldValue('product_id', id)
              }}
            />
          </Form.Item>
        )}
        {stock.data && (
          <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
            На складе: {formatQuantity(stock.data.on_hand)}, в резерве:{' '}
            {formatQuantity(stock.data.reserved)}, доступно: {formatQuantity(stock.data.available)}
          </Typography.Paragraph>
        )}
        <Form.Item
          label={`Количество${unit ? `, ${UNIT_LABELS[unit] ?? unit}` : ''}`}
          name="quantity"
          rules={[
            { required: true, message: 'Введите количество' },
            {
              validator: (_, value: string | null) =>
                value && Number(value) <= 0
                  ? Promise.reject(new Error('Количество должно быть больше нуля'))
                  : Promise.resolve(),
            },
          ]}
        >
          <InputNumber stringMode min="0" precision={unit === 'pcs' ? 0 : 3} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="Причина" name="reason" rules={[{ required: true }]}>
          <Select options={REASONS} />
        </Form.Item>
        <Form.Item label="Комментарий (необязательно)" name="comment">
          <Input.TextArea rows={2} maxLength={500} showCount />
        </Form.Item>
      </Form>
    </Modal>
  )
}
