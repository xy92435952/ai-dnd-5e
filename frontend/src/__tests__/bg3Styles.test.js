import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const srcRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function readBg3Css() {
  return fs.readFileSync(path.join(srcRoot, 'styles', 'bg3.css'), 'utf8')
}

describe('BG3 stylesheet chrome', () => {
  it('does not rely on inline-style attribute selectors', () => {
    const css = readBg3Css()

    expect(css).toContain('[data-theme="bg3"] .panel-ornate')
    expect(css).not.toMatch(/\[style(?:[*^$|~]?=|\])/)
  })
})
