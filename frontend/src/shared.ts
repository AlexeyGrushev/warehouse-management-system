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

/** Подпись и цвет для «сколько дней до конца срока годности»; отрицательное — уже просрочено. */
export function expiryLabel(daysLeft: number): { text: string; color: string } {
  if (daysLeft < 0) {
    return { text: `просрочена на ${-daysLeft} дн.`, color: 'red' }
  }
  if (daysLeft === 0) {
    return { text: 'истекает сегодня', color: 'red' }
  }
  return { text: `${daysLeft} дн.`, color: daysLeft <= 7 ? 'orange' : 'gold' }
}

export const RESERVATION_STATUSES = {
  ACTIVE: { label: 'Активен', color: 'blue' },
  FULFILLED: { label: 'Исполнен', color: 'green' },
  CANCELLED: { label: 'Отменён', color: 'default' },
  EXPIRED: { label: 'Истёк', color: 'orange' },
} as const

export const STOCKTAKING_STATUSES = {
  DRAFT: { label: 'Черновик', color: 'default' },
  IN_PROGRESS: { label: 'Идёт', color: 'processing' },
  CLOSED: { label: 'Закрыта', color: 'green' },
  CANCELLED: { label: 'Отменена', color: 'default' },
} as const

export const SEVERITIES = {
  CRITICAL: { label: 'Критично', color: 'red', rowBackground: '#fff1f0' },
  WARNING: { label: 'Заканчивается', color: 'orange', rowBackground: undefined },
} as const
