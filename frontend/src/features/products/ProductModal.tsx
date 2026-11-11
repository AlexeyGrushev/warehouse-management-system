import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Form, Input, InputNumber, Modal, Select, message } from 'antd'
import { useMemo, useState } from 'react'

import { createProduct, fetchCategories, updateProduct } from '../../api/catalog'
import { ApiError } from '../../api/client'
import type { Product } from '../../api/types'
import { categoryPaths } from '../../components/categoryPaths'
import { UNIT_LABELS } from '../../shared'

interface FormValues {
  sku: string
  name: string
  category_id: number
  unit: string
  min_stock: string
  target_stock?: string | null
}

interface Props {
  open: boolean
  onClose: () => void
  /** Если передан, форма работает как редактирование этого товара. */
  product?: Product | null
}

const UNITS = Object.entries(UNIT_LABELS).map(([value, label]) => ({ value, label }))

export function ProductModal({ open, onClose, product }: Props) {
  const [form] = Form.useForm<FormValues>()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const unit = Form.useWatch('unit', form) ?? product?.unit
  const editing = product != null

  const categories = useQuery({ queryKey: ['categories'], queryFn: fetchCategories, enabled: open })
  const options = useMemo(() => {
    const all = categories.data ?? []
    const paths = categoryPaths(all)
    return all
      .filter((category) => category.is_active || category.id === product?.category_id)
      .map((category) => ({ value: category.id, label: paths.get(category.id) ?? category.name }))
      .sort((a, b) => a.label.localeCompare(b.label, 'ru'))
  }, [categories.data, product?.category_id])

  const save = useMutation({
    mutationFn: (values: FormValues) => {
      const data = {
        sku: values.sku.trim(),
        name: values.name.trim(),
        category_id: values.category_id,
        unit: values.unit,
        min_stock: values.min_stock,
        target_stock: values.target_stock ? values.target_stock : null,
      }
      return editing ? updateProduct(product.id, data) : createProduct(data)
    },
    onSuccess: (saved) => {
      message.success(editing ? `Товар ${saved.sku} сохранён` : `Товар ${saved.sku} создан`)
      for (const key of ['products', 'product-options', 'stock', 'product']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
      close()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Не удалось сохранить товар'),
  })

  function close() {
    form.resetFields()
    setError(null)
    onClose()
  }

  return (
    <Modal
      title={editing ? `Товар ${product.sku}` : 'Новый товар'}
      open={open}
      onCancel={close}
      onOk={() => form.submit()}
      okText={editing ? 'Сохранить' : 'Создать'}
      cancelText="Отмена"
      confirmLoading={save.isPending}
      destroyOnHidden
      width={520}
    >
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
      <Form<FormValues>
        form={form}
        layout="vertical"
        requiredMark={false}
        // не хранить значения после закрытия, иначе при правке они перекроют данные товара
        preserve={false}
        initialValues={
          product
            ? {
                sku: product.sku,
                name: product.name,
                category_id: product.category_id,
                unit: product.unit,
                min_stock: product.min_stock,
                target_stock: product.target_stock,
              }
            : { unit: 'pcs', min_stock: '0' }
        }
        onFinish={(values) => {
          setError(null)
          save.mutate(values)
        }}
      >
        <Form.Item
          label="Артикул"
          name="sku"
          extra="Уникальный код товара"
          rules={[{ required: true, whitespace: true, message: 'Введите артикул' }]}
        >
          <Input maxLength={64} autoFocus />
        </Form.Item>
        <Form.Item
          label="Название"
          name="name"
          rules={[{ required: true, whitespace: true, message: 'Введите название' }]}
        >
          <Input maxLength={200} />
        </Form.Item>
        <Form.Item
          label="Категория"
          name="category_id"
          rules={[{ required: true, message: 'Выберите категорию' }]}
        >
          <Select
            showSearch
            optionFilterProp="label"
            placeholder="Выберите категорию"
            loading={categories.isFetching}
            options={options}
            notFoundContent="Категория не найдена. Её можно создать на странице «Категории»"
          />
        </Form.Item>
        <Form.Item label="Единица измерения" name="unit" rules={[{ required: true }]}>
          <Select options={UNITS} />
        </Form.Item>
        <Form.Item
          label="Минимальный остаток"
          name="min_stock"
          extra="Ниже этого значения товар попадёт в список нехватки"
          rules={[{ required: true, message: 'Введите минимальный остаток' }]}
        >
          <InputNumber stringMode min="0" precision={unit === 'pcs' ? 0 : 3} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item
          label="Целевой остаток (необязательно)"
          name="target_stock"
          dependencies={['min_stock']}
          extra="До какого количества пополняем; не меньше минимального"
          rules={[
            ({ getFieldValue }) => ({
              validator: (_, value: string | null | undefined) =>
                value && Number(value) < Number(getFieldValue('min_stock'))
                  ? Promise.reject(new Error('Целевой остаток не может быть меньше минимального'))
                  : Promise.resolve(),
            }),
          ]}
        >
          <InputNumber stringMode min="0" precision={unit === 'pcs' ? 0 : 3} style={{ width: '100%' }} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
