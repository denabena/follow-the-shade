export type ClassValue =
  | string
  | number
  | null
  | undefined
  | false
  | ClassValue[]

export const cn = (...values: ClassValue[]): string => {
  const out: string[] = []
  const walk = (v: ClassValue) => {
    if (!v && v !== 0) return
    if (Array.isArray(v)) {
      v.forEach(walk)
      return
    }
    out.push(String(v))
  }
  values.forEach(walk)
  return out.join(" ")
}
