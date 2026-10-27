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
