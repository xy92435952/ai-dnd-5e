export const COMBAT_GRID = {
  width: 20,
  height: 12,
  viewWidth: 12,
  viewHeight: 8,
}

export function ignoreOptionalEffect(fn) {
  try {
    fn()
  } catch {
    // Optional audio / haptics may fail in tests or unsupported browsers.
  }
}
