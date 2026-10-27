import { useQuery } from '@tanstack/react-query'
import { Select } from 'antd'
import { useState } from 'react'

import { fetchSuppliers } from '../api/suppliers'
import { useDebounced } from '../hooks'

interface Props {
  value?: number
  onChange?: (id: number) => void
}

/** Выбор поставщика с поиском (только активные). */
export function SupplierSelect({ value, onChange }: Props) {
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search.trim())
  const suppliers = useQuery({
    queryKey: ['supplier-options', debounced],
    queryFn: () => fetchSuppliers(debounced),
  })

  return (
    <Select
      showSearch
      value={value}
      placeholder="Начните вводить название поставщика"
      filterOption={false}
      onSearch={setSearch}
      loading={suppliers.isFetching}
      notFoundContent="Ничего не найдено"
      options={suppliers.data?.items.map((supplier) => ({
        value: supplier.id,
        label: supplier.name,
      }))}
      onChange={onChange}
    />
  )
}
