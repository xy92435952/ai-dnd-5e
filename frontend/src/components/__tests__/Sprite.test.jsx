import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, waitFor } from '@testing-library/react'
import Sprite from '../Sprite'

const spriteIndex = {
  sprites: {
    paladin: { size: 'M', fallback: 'wizard' },
    goblin: { size: 'S', fallback: 'rogue' },
  },
  fallbacks: {
    default: 'paladin',
  },
  sizes: {
    S: 0.75,
    M: 1,
    L: 1.5,
    H: 2,
    G: 3,
  },
}

describe('Sprite', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(spriteIndex),
    })))
  })

  it('renders PNG sprite chrome through classes without inline style', async () => {
    const { container } = render(<Sprite kind="goblin" size={40} dim />)

    await waitFor(() => expect(container.querySelector('img')).toBeInTheDocument())
    const sprite = container.querySelector('img')
    expect(sprite).toHaveClass('sprite-image')
    expect(sprite).toHaveAttribute('data-tone', 'dim')
    expect(sprite).toHaveAttribute('src', '/sprites/goblin.png')
    expect(sprite).toHaveAttribute('width', '30')
    expect(sprite).toHaveAttribute('height', '45')
    expect(sprite).not.toHaveAttribute('style')
  })

  it('projects dead tone and falls back to inline PixelSprite when the PNG fails', async () => {
    const { container } = render(<Sprite kind="paladin" size={44} dead />)

    await waitFor(() => expect(container.querySelector('img')).toBeInTheDocument())
    const sprite = container.querySelector('img')
    expect(sprite).toHaveAttribute('data-tone', 'dead')

    fireEvent.error(sprite)

    await waitFor(() => {
      expect(container.querySelector('svg')).toBeInTheDocument()
    })
    expect(container.querySelector('img')).not.toBeInTheDocument()
  })
})
