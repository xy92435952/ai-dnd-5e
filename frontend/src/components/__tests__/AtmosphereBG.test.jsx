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

    const dustParticle = container.querySelector('.dust span')
    expect(dustParticle).toBeInTheDocument()
    expect(dustParticle).toHaveAttribute('style')

    const embers = container.querySelector('.embers')
    expect(embers).toHaveStyle({ display: 'none' })
  })
})
