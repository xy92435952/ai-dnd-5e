import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CharacterCreateStepPartyPartySize from '../CharacterCreateStepPartyPartySize'

describe('CharacterCreateStepPartyPartySize', () => {
  it('renders stable party-size controls and keeps the selected size projected', () => {
    const setPartySize = vi.fn()
    render(
      <CharacterCreateStepPartyPartySize
        partySize={3}
        setPartySize={setPartySize}
      />,
    )

    const section = screen.getByRole('region', { name: 'Party size' })
    expect(section).toHaveClass('companions-party-size')
    expect(section.querySelector('.companions-party-size-label')).not.toBeNull()

    const options = within(section).getByRole('group', { name: 'Party size options' })
    expect(options).toHaveClass('companions-party-size-options')

    const two = within(options).getByRole('button', { name: '2 人' })
    const three = within(options).getByRole('button', { name: '3 人' })
    const four = within(options).getByRole('button', { name: '4 人' })
    expect(two).toHaveClass('btn-ghost', 'companions-party-size-button')
    expect(two).toHaveAttribute('data-selected', 'false')
    expect(three).toHaveClass('btn-gold', 'companions-party-size-button')
    expect(three).toHaveAttribute('data-selected', 'true')
    expect(three).toHaveAttribute('aria-pressed', 'true')
    expect(four).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(four)
    expect(setPartySize).toHaveBeenCalledWith(4)
  })
})
