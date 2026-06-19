import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import SpellModalTabs from '../SpellModalTabs'

describe('SpellModalTabs', () => {
  it('renders a tablist with active cantrip and leveled spell tabs', () => {
    const setLevel = vi.fn()
    const setSelectedSpell = vi.fn()

    render(
      <SpellModalTabs
        level={0}
        setLevel={setLevel}
        setSelectedSpell={setSelectedSpell}
        cantripCount={2}
        spellList={[{ name: 'Magic Missile', level: 1 }]}
        available={(lvl) => (lvl === 1 ? 1 : 0)}
      />,
    )

    const tablist = screen.getByRole('tablist', { name: '施法环级选择' })
    const cantrip = within(tablist).getByRole('tab', { name: '戏法，可用 2' })
    expect(cantrip).toHaveClass('spell-modal-tab', 'spell-modal-tab-cantrip', 'active')
    expect(cantrip).toHaveAttribute('aria-selected', 'true')

    const first = within(tablist).getByRole('tab', { name: '1 环法术，可用 1' })
    expect(first).toHaveClass('spell-modal-tab')
    expect(first).toHaveAttribute('aria-selected', 'false')

    fireEvent.click(first)
    expect(setLevel).toHaveBeenCalledWith(1)
    expect(setSelectedSpell).toHaveBeenCalledWith(null)
  })

  it('marks unavailable spell levels as disabled and keeps their tooltip reason', () => {
    render(
      <SpellModalTabs
        level={1}
        setLevel={vi.fn()}
        setSelectedSpell={vi.fn()}
        cantripCount={0}
        spellList={[{ name: 'Magic Missile', level: 1 }]}
        available={() => 0}
      />,
    )

    const tablist = screen.getByRole('tablist', { name: '施法环级选择' })
    const cantrip = within(tablist).getByRole('tab', { name: '戏法，可用 0' })
    expect(cantrip).toHaveClass('empty')

    const first = within(tablist).getByRole('tab', { name: '1 环法术，可用 0' })
    expect(first).toBeDisabled()
    expect(first).toHaveClass('disabled')
    expect(first).toHaveAttribute('title', '没有可用的 1 环法术位')
  })

  it('disables levels that have slots but no spells to show', () => {
    render(
      <SpellModalTabs
        level={1}
        setLevel={vi.fn()}
        setSelectedSpell={vi.fn()}
        cantripCount={1}
        spellList={[]}
        available={() => 2}
      />,
    )

    const second = screen.getByRole('tab', { name: '2 环法术，可用 2' })
    expect(second).toBeDisabled()
    expect(second).toHaveAttribute('title', '没有可用的 2 环法术')
  })
})
