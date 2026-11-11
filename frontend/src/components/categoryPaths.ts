import type { Category } from '../api/types'

/** «Продукты питания / Молочные продукты» — путь категории от корня. */
export function categoryPaths(categories: Category[]): Map<number, string> {
  const byId = new Map(categories.map((category) => [category.id, category]))
  const paths = new Map<number, string>()
  for (const category of categories) {
    const names = [category.name]
    let parent = category.parent_id === null ? undefined : byId.get(category.parent_id)
    while (parent) {
      names.unshift(parent.name)
      parent = parent.parent_id === null ? undefined : byId.get(parent.parent_id)
    }
    paths.set(category.id, names.join(' / '))
  }
  return paths
}
