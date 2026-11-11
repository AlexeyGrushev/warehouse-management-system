import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, Form, Input, Modal, message } from 'antd'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import { createSupplier, updateSupplier } from '../../api/suppliers'
import type { Supplier } from '../../api/types'

interface FormValues {
  name: string
  contact?: string
}

interface Props {
  open: boolean
  onClose: () => void
  /** Если передан, форма работает как редактирование этого поставщика. */
  supplier?: Supplier | null
}

export function SupplierModal({ open, onClose, supplier }: Props) {
  const [form] = Form.useForm<FormValues>()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const editing = supplier != null

  const save = useMutation({
    mutationFn: (values: FormValues) => {
      const data = { name: values.name.trim(), contact: values.contact?.trim() || null }
      return editing ? updateSupplier(supplier.id, data) : createSupplier(data)
    },
    onSuccess: (saved) => {
      message.success(editing ? `Поставщик «${saved.name}» сохранён` : `Поставщик «${saved.name}» создан`)
      for (const key of ['suppliers', 'supplier-options']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
      close()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Не удалось сохранить поставщика'),
  })

  function close() {
    setError(null)
    onClose()
  }

  return (
    <Modal
      title={editing ? `Поставщик «${supplier.name}»` : 'Новый поставщик'}
      open={open}
      onCancel={close}
      onOk={() => form.submit()}
      okText={editing ? 'Сохранить' : 'Создать'}
      cancelText="Отмена"
      confirmLoading={save.isPending}
      destroyOnHidden
    >
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
      <Form<FormValues>
        form={form}
        layout="vertical"
        requiredMark={false}
        preserve={false}
        initialValues={{ name: supplier?.name ?? '', contact: supplier?.contact ?? '' }}
        onFinish={(values) => {
          setError(null)
          save.mutate(values)
        }}
      >
        <Form.Item
          label="Название"
          name="name"
          extra="Должно быть уникальным"
          rules={[{ required: true, whitespace: true, message: 'Введите название' }]}
        >
          <Input maxLength={200} autoFocus />
        </Form.Item>
        <Form.Item label="Контакты (необязательно)" name="contact" extra="Телефон, почта, контактное лицо">
          <Input.TextArea rows={3} maxLength={500} showCount />
        </Form.Item>
      </Form>
    </Modal>
  )
}
