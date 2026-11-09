import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, DatePicker, Form, Input, InputNumber, Modal, Space, message } from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import { createReservation } from '../../api/reservations'
import { ProductSelect } from '../../components/ProductSelect'
import { UNIT_LABELS } from '../../shared'

interface ItemValues {
  product_id?: number
  unit?: string
  quantity?: string
}

interface FormValues {
  reference: string
  expires_at?: Dayjs | null
  items: ItemValues[]
}

interface Props {
  open: boolean
  onClose: () => void
}

export function ReservationModal({ open, onClose }: Props) {
  const [form] = Form.useForm<FormValues>()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const items = Form.useWatch('items', form)

  const create = useMutation({
    mutationFn: (values: FormValues) =>
      createReservation({
        reference: values.reference.trim(),
        expires_at: values.expires_at ? values.expires_at.toISOString() : null,
        items: values.items.map((item) => ({
          product_id: item.product_id as number,
          quantity: item.quantity as string,
        })),
      }),
    onSuccess: (reservation) => {
      message.success(`Резерв по заказу ${reservation.reference} создан`)
      for (const key of ['reservations', 'stock', 'product-stock', 'movements']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
      close()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Не удалось создать резерв'),
  })

  function close() {
    form.resetFields()
    setError(null)
    onClose()
  }

  return (
    <Modal
      title="Новый резерв"
      open={open}
      onCancel={close}
      onOk={() => form.submit()}
      okText="Зарезервировать"
      cancelText="Отмена"
      confirmLoading={create.isPending}
      destroyOnHidden
      width={620}
    >
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
      <Form<FormValues>
        form={form}
        layout="vertical"
        requiredMark={false}
        initialValues={{ items: [{}] }}
        onFinish={(values) => {
          setError(null)
          create.mutate(values)
        }}
      >
        <Form.Item
          label="Номер заказа"
          name="reference"
          rules={[{ required: true, whitespace: true, message: 'Введите номер заказа' }]}
        >
          <Input maxLength={100} />
        </Form.Item>
        <Form.Item
          label="Действует до (по умолчанию 7 дней)"
          name="expires_at"
          rules={[
            {
              validator: (_, value: Dayjs | null | undefined) =>
                value && !value.isAfter(dayjs())
                  ? Promise.reject(new Error('Срок должен быть в будущем'))
                  : Promise.resolve(),
            },
          ]}
        >
          <DatePicker showTime={{ format: 'HH:mm' }} format="DD.MM.YYYY HH:mm" style={{ width: '100%' }} />
        </Form.Item>

        <Form.List name="items">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name }) => {
                const unit = items?.[name]?.unit
                return (
                  <Space key={key} align="start" style={{ display: 'flex', marginBottom: 8 }}>
                    <Form.Item
                      name={[name, 'product_id']}
                      label={name === 0 ? 'Товар' : undefined}
                      style={{ width: 340, marginBottom: 0 }}
                      rules={[
                        { required: true, message: 'Выберите товар' },
                        {
                          validator: (_, value: number | undefined) =>
                            value !== undefined &&
                            (items ?? []).filter((item) => item?.product_id === value).length > 1
                              ? Promise.reject(new Error('Товар уже добавлен'))
                              : Promise.resolve(),
                        },
                      ]}
                    >
                      <ProductSelect
                        onChange={(id, product) => {
                          form.setFieldValue(['items', name, 'product_id'], id)
                          form.setFieldValue(['items', name, 'unit'], product?.unit)
                        }}
                      />
                    </Form.Item>
                    <Form.Item name={[name, 'unit']} hidden>
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name={[name, 'quantity']}
                      label={name === 0 ? `Количество${unit ? `, ${UNIT_LABELS[unit] ?? unit}` : ''}` : undefined}
                      style={{ width: 150, marginBottom: 0 }}
                      rules={[
                        { required: true, message: 'Введите количество' },
                        {
                          validator: (_, value: string | null) =>
                            value && Number(value) <= 0
                              ? Promise.reject(new Error('Больше нуля'))
                              : Promise.resolve(),
                        },
                      ]}
                    >
                      <InputNumber
                        stringMode
                        min="0"
                        precision={unit === 'pcs' ? 0 : 3}
                        style={{ width: '100%' }}
                      />
                    </Form.Item>
                    <Button
                      type="text"
                      icon={<MinusCircleOutlined />}
                      disabled={fields.length === 1}
                      onClick={() => remove(name)}
                      style={{ marginTop: name === 0 ? 30 : 0 }}
                      aria-label="Убрать позицию"
                    />
                  </Space>
                )
              })}
              <Button type="dashed" icon={<PlusOutlined />} onClick={() => add({})} block>
                Добавить товар
              </Button>
            </>
          )}
        </Form.List>
      </Form>
    </Modal>
  )
}
