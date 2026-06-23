import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(__dirname, '..', '..')
const sourceExtensions = new Set(['.js', '.jsx', '.ts', '.tsx'])

const unsafeDomPatterns = [
  /(?<![\w$])dangerouslySetInnerHTML\s*=/,
  /\.\s*style\s*\.\s*cssText\s*=/,
  /\.\s*innerHTML\s*=/,
  /\.\s*outerHTML\s*=/,
  /\.\s*insertAdjacentHTML\s*\(/,
  /(?<![\w$])document\s*\.\s*write(?:ln)?\s*\(/,
  /(?<![\w$])eval\s*\(/,
  /(?<![\w$])new\s+Function\s*\(/,
]

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

function hasUnsafeDomApiUsage(line) {
  return unsafeDomPatterns.some((pattern) => pattern.test(line))
}

describe('unsafe DOM API policy', () => {
  it('detects unsafe HTML and script execution sinks', () => {
    expect(hasUnsafeDomApiUsage('<div dangerouslySetInnerHTML={{ __html: html }} />')).toBe(true)
    expect(hasUnsafeDomApiUsage('node.style.cssText = "position:absolute"')).toBe(true)
    expect(hasUnsafeDomApiUsage('target.innerHTML = html')).toBe(true)
    expect(hasUnsafeDomApiUsage('target.insertAdjacentHTML("beforeend", html)')).toBe(true)
    expect(hasUnsafeDomApiUsage('document.write(html)')).toBe(true)
    expect(hasUnsafeDomApiUsage('eval(source)')).toBe(true)
    expect(hasUnsafeDomApiUsage('const safeHtmlLabel = "innerHTML is blocked"')).toBe(false)
  })

  it('keeps production source free of unsafe DOM sinks', () => {
    const offenders = []

    for (const filePath of collectSourceFiles(srcRoot)) {
      const relativePath = path.relative(srcRoot, filePath).split(path.sep).join('/')
      const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/)

      lines.forEach((line, index) => {
        if (hasUnsafeDomApiUsage(line)) {
          offenders.push(`${relativePath}:${index + 1}: ${line.trim()}`)
        }
      })
    }

    expect(offenders).toEqual([])
  })
})
