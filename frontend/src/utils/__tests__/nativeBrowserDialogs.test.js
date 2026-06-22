import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(__dirname, '..', '..')
const sourceExtensions = new Set(['.js', '.jsx', '.ts', '.tsx'])
const nativeDialogCallPattern = /(?<![\w$])(?:(?:window|globalThis)\s*\.\s*)?(alert|confirm|prompt)\s*\(/g

function shouldScanFile(filePath) {
  const normalized = filePath.split(path.sep).join('/')
  if (normalized.includes('/__tests__/')) return false
  if (normalized.includes('/test/')) return false
  if (normalized.endsWith('.test.js') || normalized.endsWith('.test.jsx')) return false
  if (normalized.endsWith('.spec.js') || normalized.endsWith('.spec.jsx')) return false
  return sourceExtensions.has(path.extname(filePath))
}

function collectSourceFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  return entries.flatMap((entry) => {
    const filePath = path.join(dir, entry.name)
    if (entry.isDirectory()) return collectSourceFiles(filePath)
    return shouldScanFile(filePath) ? [filePath] : []
  })
}

describe('native browser dialog policy', () => {
  it('keeps production source free of blocking browser dialogs', () => {
    const offenders = []

    for (const filePath of collectSourceFiles(srcRoot)) {
      const relativePath = path.relative(srcRoot, filePath).split(path.sep).join('/')
      const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/)

      lines.forEach((line, index) => {
        nativeDialogCallPattern.lastIndex = 0
        if (nativeDialogCallPattern.test(line)) {
          offenders.push(`${relativePath}:${index + 1}: ${line.trim()}`)
        }
      })
    }

    expect(offenders).toEqual([])
  })
})
