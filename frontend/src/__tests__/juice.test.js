import { afterEach, describe, expect, it, vi } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { flash } from '../juice'

const srcRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

afterEach(() => {
  vi.useRealTimers()
  document.body.replaceChildren()
})

function readJuiceCss() {
  return fs.readFileSync(path.join(srcRoot, 'styles', 'juice.css'), 'utf8')
}

describe('juice flash feedback', () => {
  it('projects runtime flash values through stable CSS variables', () => {
    vi.useFakeTimers()
    const target = document.createElement('section')
    document.body.appendChild(target)

    flash(target, 'rgba(12, 34, 56, 0.7)', 480)

    const overlay = target.querySelector('.jc-flash')
    expect(overlay).not.toBeNull()
    expect(overlay.style.getPropertyValue('--jc-flash-color')).toBe('rgba(12, 34, 56, 0.7)')
    expect(overlay.style.getPropertyValue('--jc-flash-duration')).toBe('480ms')
    expect(overlay.style.position).toBe('')
    expect(overlay.style.background).toBe('')
    expect(overlay.style.animation).toBe('')
    expect(target.style.position).toBe('relative')

    vi.advanceTimersByTime(500)
    expect(target.querySelector('.jc-flash')).toBeNull()
  })

  it('keeps fixed flash chrome on the stylesheet class', () => {
    const css = readJuiceCss()

    expect(css).toMatch(/\.jc-flash\s*\{[\s\S]*position:\s*absolute;/)
    expect(css).toContain('background: var(--jc-flash-color, rgba(255, 240, 200, .6));')
    expect(css).toContain('animation: jcFlash var(--jc-flash-duration, 260ms) ease-out forwards;')
    expect(css).toContain('mix-blend-mode: screen;')
  })
})
