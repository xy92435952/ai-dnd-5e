import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import AtmosphereBG from '../AtmosphereBG'

describe('AtmosphereBG', () => {
  it('renders fixed god-ray chrome through classes while keeping particles dynamic', () => {
    const { container } = render(<AtmosphereBG embers={false} />)

    const atmosphere = container.querySelector('.bg-atmosphere')
    expect(atmosphere).toBeInTheDocument()
    expect(atmosphere).toHaveAttribute('aria-hidden', 'true')

    const rays = Array.from(container.querySelectorAll('.god-rays .god-ray'))
    expect(rays).toHaveLength(5)
    rays.forEach((ray, index) => {
      expect(ray).toHaveClass('god-ray', `god-ray-${index + 1}`)
      expect(ray).not.toHaveAttribute('style')
    })

    const dustParticles = Array.from(container.querySelectorAll('.dust span'))
    expect(dustParticles).toHaveLength(60)
    expect(dustParticles[0]).toHaveAttribute('style')

    const embers = container.querySelector('.embers')
    expect(embers).toHaveStyle({ display: 'none' })
    expect(embers.children).toHaveLength(0)
  })

  it('clears and rebuilds ember particles when the ember layer toggles', () => {
    const { container, rerender } = render(<AtmosphereBG />)

    const embers = container.querySelector('.embers')
    expect(embers).toHaveStyle({ display: 'block' })
    expect(embers.querySelectorAll('.ember')).toHaveLength(40)

    rerender(<AtmosphereBG embers={false} />)

    expect(embers).toHaveStyle({ display: 'none' })
    expect(embers.children).toHaveLength(0)

    rerender(<AtmosphereBG />)

    expect(embers).toHaveStyle({ display: 'block' })
    expect(embers.querySelectorAll('.ember')).toHaveLength(40)
  })
})
