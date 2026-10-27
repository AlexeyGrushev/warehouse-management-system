import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, DatePicker, Form, InputNumber, Input, Modal, message } from 'antd'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import { createReceipt } from '../../api/stock'
import type { Product } from '../../api/types'
import { ProductSelect } from '../../components/ProductSelect'
import { SupplierSelect } from '../../components/SupplierSelect'
import { UNIT_LABELS } from '../../shared'

interface FormValues {
  product_id: number
  supplier_id: number
  batch_no: string
  quantity: string
  unit_cost: string
  received_at: Dayjs
  expires_at?: Dayjs | null
}

interface Props {
  open: boolean
  onClose: () => void
}

const DATE_FORMAT = 'YYYY-MM-DD'

export function ReceiptModal({ open, onClose }: Props) {
  const [form] = Form.useForm<FormValues>()
  const queryClient = useQueryClient()
  const [product, setProduct] = useState<Product>()
  const [error, setError] = useState<string | null>(null)

  const receipt = useMutation({
    mutationFn: (values: FormValues) =>
      createReceipt({
        product_id: values.product_id,
        supplier_id: values.supplier_id,
        batch_no: values.batch_no.trim(),
        quantity: values.quantity,
        unit_cost: values.unit_cost,
        received_at: values.received_at.format(DATE_FORMAT),
        expires_at: values.expires_at ? values.expires_at.format(DATE_FORMAT) : null,
      }),
    onSuccess: (batch) => {
      message.success(`Партия ${batch.batch_no} принята`)
      void queryClient.invalidateQueries({ queryKey: ['stock'] })
      void queryClient.invalidateQueries({ queryKey: ['movements'] })
      close()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Не удалось принять партию'),
  })

  function close() {
    form.resetFields()
    setProduct(undefined)
    setError(null)
    onClose()
  }

  const isPieces = product?.unit === 'pcs'

  return (
    <Modal
      title="Приход партии"
      open={open}
      onCancel={close}
      onOk={() => form.submit()}
      okText="Принять"
      cancelText="Отмена"
      confirmLoading={receipt.isPending}
      destroyOnHidden
      width={520}
    >
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
      <Form<FormValues>
        form={form}
        layout="vertical"
        requiredMark={false}
        initialValues={{ received_at: dayjs() }}
        onFinish={(values) => {
          setError(null)
          receipt.mutate(values)
        }}
      >
        <Form.Item label="Товар" name="product_id" rules={[{ required: true, message: 'Выберите товар' }]}>
          <ProductSelect
            onChange={(id, selected) => {
              setProduct(selected)
              form.setFieldValue('product_id', id)
            }}
          />
        </Form.Item>
        <Form.Item
          label="Поставщик"
          name="supplier_id"
          rules={[{ required: true, message: 'Выберите поставщика' }]}
        >
          <SupplierSelect />
        </Form.Item>
        <Form.Item
          label="Номер партии"
          name="batch_no"
          rules={[{ required: true, whitespace: true, message: 'Введите номер партии' }]}
        >
          <Input maxLength={64} />
        </Form.Item>
        <Form.Item
          label={`Количество${product ? `, ${UNIT_LABELS[product.unit] ?? product.unit}` : ''}`}
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
          <InputNumber stringMode min="0" precision={isPieces ? 0 : 3} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item
          label="Закупочная цена за единицу, ₽"
          name="unit_cost"
          rules={[{ required: true, message: 'Введите цену' }]}
        >
          <InputNumber stringMode min="0" precision={2} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item
          label="Дата прихода"
          name="received_at"
          rules={[{ required: true, message: 'Укажите дату' }]}
        >
          <DatePicker format="DD.MM.YYYY" style={{ width: '100%' }} allowClear={false} />
        </Form.Item>
        <Form.Item
          label="Срок годности (необязательно)"
          name="expires_at"
          dependencies={['received_at']}
          rules={[
            ({ getFieldValue }) => ({
              validator: (_, value: Dayjs | null | undefined) =>
                value && value.isBefore(getFieldValue('received_at'), 'day')
                  ? Promise.reject(new Error('Срок годности раньше даты прихода'))
                  : Promise.resolve(),
            }),
          ]}
        >
          <DatePicker format="DD.MM.YYYY" style={{ width: '100%' }} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
