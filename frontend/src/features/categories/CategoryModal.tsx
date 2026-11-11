import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, Form, Input, Modal, Select, message } from 'antd'
import { useMemo, useState } from 'react'

import { createCategory, updateCategory } from '../../api/catalog'
import { ApiError } from '../../api/client'
import type { Category, CategoryNode } from '../../api/types'

export type CategoryDialog =
  | { kind: 'create'; parentId: number | null }
  | { kind: 'edit'; category: CategoryNode }

interface Props {
  dialog: CategoryDialog | null
  /** Все категории деревом: нужны, чтобы предложить родителя и не дать выбрать потомка. */
  tree: CategoryNode[]
  onClose: () => void
}

interface FormValues {
  name: string
  parent_id?: number | null
}

function flatten(nodes: CategoryNode[], prefix = ''): { category: Category; path: string }[] {
  return nodes.flatMap((node) => {
    const path = prefix ? `${prefix} / ${node.name}` : node.name
    return [{ category: node, path }, ...flatten(node.children, path)]
  })
}

function subtreeIds(node: CategoryNode): number[] {
  return [node.id, ...node.children.flatMap(subtreeIds)]
}

export function CategoryModal({ dialog, tree, onClose }: Props) {
  const [form] = Form.useForm<FormValues>()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const editing = dialog?.kind === 'edit' ? dialog.category : null

  const parentOptions = useMemo(() => {
    const excluded = new Set(editing ? subtreeIds(editing) : [])
    return flatten(tree)
      .filter(({ category }) => category.is_active && !excluded.has(category.id))
      .map(({ category, path }) => ({ value: category.id, label: path }))
  }, [tree, editing])

  const save = useMutation({
    mutationFn: (values: FormValues) => {
      const data = { name: values.name.trim(), parent_id: values.parent_id ?? null }
      return editing ? updateCategory(editing.id, data) : createCategory(data)
    },
    onSuccess: (saved) => {
      message.success(editing ? `Категория «${saved.name}» сохранена` : `Категория «${saved.name}» создана`)
      for (const key of ['categories', 'categories-tree', 'products']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
      close()
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Не удалось сохранить категорию'),
  })

  function close() {
    setError(null)
    onClose()
  }

  let title = ''
  if (dialog?.kind === 'edit') {
    title = `Категория «${dialog.category.name}»`
  } else if (dialog?.kind === 'create') {
    title = dialog.parentId === null ? 'Новая категория' : 'Новая подкатегория'
  }

  return (
    <Modal
      title={title}
      open={dialog !== null}
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
        initialValues={{
          name: editing?.name ?? '',
          parent_id: editing ? editing.parent_id : dialog?.kind === 'create' ? dialog.parentId : null,
        }}
        onFinish={(values) => {
          setError(null)
          save.mutate(values)
        }}
      >
        <Form.Item
          label="Название"
          name="name"
          rules={[{ required: true, whitespace: true, message: 'Введите название' }]}
        >
          <Input maxLength={200} autoFocus />
        </Form.Item>
        <Form.Item
          label="Родительская категория"
          name="parent_id"
          extra="Если не выбрать, категория будет корневой"
        >
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="Нет (корневая категория)"
            options={parentOptions}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
