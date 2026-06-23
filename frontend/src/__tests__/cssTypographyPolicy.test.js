import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const srcRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const stylesRoot = path.join(srcRoot, 'styles')

const negativeLetterSpacingPattern = /letter-spacing\s*:\s*-\s*(?:\d|\.\d)/i
const viewportFontSizePattern = /font-size\s*:[^;]*(?:vw|vh|vmin|vmax)/i

function collectCssFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  return entries.flatMap((entry) => {
    const filePath = path.join(dir, entry.name)
    if (entry.isDirectory()) return collectCssFiles(filePath)
    return path.extname(filePath) === '.css' ? [filePath] : []
  })
}

function findTypographyPolicyOffenders() {
  const offenders = []

  for (const filePath of collectCssFiles(stylesRoot)) {
    const relativePath = path.relative(srcRoot, filePath).split(path.sep).join('/')
    const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/)

    lines.forEach((line, index) => {
      if (negativeLetterSpacingPattern.test(line)) {
        offenders.push(`${relativePath}:${index + 1}: negative letter-spacing: ${line.trim()}`)
      }
      if (viewportFontSizePattern.test(line)) {
        offenders.push(`${relativePath}:${index + 1}: viewport font-size: ${line.trim()}`)
      }
    })
  }

  return offenders
}

describe('CSS typography policy', () => {
  it('detects compact typography that can destabilize responsive layouts', () => {
    expect(negativeLetterSpacingPattern.test('letter-spacing: -.02em;')).toBe(true)
    expect(negativeLetterSpacingPattern.test('letter-spacing: -0.03em;')).toBe(true)
    expect(viewportFontSizePattern.test('font-size: clamp(18px, 4vw, 32px);')).toBe(true)
    expect(viewportFontSizePattern.test('padding: clamp(12px, 3vw, 24px);')).toBe(false)
    expect(negativeLetterSpacingPattern.test('letter-spacing: 0;')).toBe(false)
  })

  it('keeps production styles free of negative tracking and viewport-sized fonts', () => {
    expect(findTypographyPolicyOffenders()).toEqual([])
  })
})
