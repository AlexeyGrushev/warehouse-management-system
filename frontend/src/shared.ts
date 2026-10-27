// Подписи и форматирование, общие для нескольких страниц

export const UNIT_LABELS: Record<string, string> = {
  pcs: 'шт',
  kg: 'кг',
  l: 'л',
  m: 'м',
  box: 'упак',
}

/** Количества приходят строками с тремя знаками ("12.500"); показываем без лишних нулей. */
export function formatQuantity(value: string): string {
  return Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 3 })
}

export const MOVEMENT_TYPES = {
  RECEIPT: { label: 'Приход', color: 'green' },
  WRITE_OFF: { label: 'Списание', color: 'red' },
  RESERVE: { label: 'Резерв', color: 'blue' },
  RELEASE: { label: 'Снятие резерва', color: 'geekblue' },
  ADJUSTMENT: { label: 'Корректировка', color: 'orange' },
} as const

export const REASON_LABELS: Record<string, string> = {
  SALE: 'Продажа',
  DAMAGE: 'Брак',
  EXPIRED: 'Истёк срок',
  OTHER: 'Другое',
}

/** Время показываем по Москве, как и границы дат в фильтре журнала. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    timeZone: 'Europe/Moscow',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
