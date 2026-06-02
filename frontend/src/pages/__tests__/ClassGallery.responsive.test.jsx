import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../components/Portrait', () => ({
  default: ({ cls }) => <div data-testid={`portrait-${cls}`} />,
}))

import ClassGallery from '../ClassGallery'

describe('ClassGallery responsive shell', () => {
  it('renders the class gallery with responsive page, grid, cards, and footer hooks', () => {
    const { container } = render(
      <MemoryRouter>
        <ClassGallery />
      </MemoryRouter>
    )

    expect(container.querySelector('.class-gallery-page')).toBeInTheDocument()
    expect(container.querySelector('.class-gallery-header')).toBeInTheDocument()
    expect(container.querySelector('.class-gallery-title')).toBeInTheDocument()
    expect(container.querySelector('.class-gallery-copy')).toBeInTheDocument()
    expect(container.querySelector('.class-gallery-grid')).toBeInTheDocument()
    expect(container.querySelectorAll('.class-gallery-card')).toHaveLength(12)
    expect(container.querySelectorAll('.class-gallery-class-name')).toHaveLength(12)
    expect(container.querySelectorAll('.class-gallery-desc')).toHaveLength(12)
    expect(container.querySelector('.class-gallery-footer')).toBeInTheDocument()
    expect(container.querySelector('.class-gallery-back')).toBeInTheDocument()
  })
})
