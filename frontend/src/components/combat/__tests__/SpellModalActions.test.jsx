import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import SpellModalActions from '../SpellModalActions'

describe('SpellModalActions', () => {
  it('casts the selected spell at the current level and exposes ready state', () => {
    const onCast = vi.fn()
    const spell = { name: 'Fireball' }

    render(
      <SpellModalActions
        canCast
        selectedSpell={spell}
        level={3}
        onCast={onCast}
        onClose={vi.fn()}
      />,
    )

    const group = screen.getByRole('group', { name: '施法操作' })
    const cast = within(group).getByRole('button', { name: '施放【Fireball】' })
    expect(cast).toHaveClass('spell-modal-cast')
    expect(cast).toHaveAttribute('data-ready', 'true')
    expect(cast).toHaveAttribute('title', '施放所选法术')
    expect(within(group).getByRole('status')).toHaveTextContent('准备施放 Fireball')

    fireEvent.click(cast)
    expect(onCast).toHaveBeenCalledWith(spell, 3)
  })

  it('falls back to cantrip level one for the cast callback contract', () => {
    const onCast = vi.fn()
    const spell = { name: 'Fire Bolt' }

    render(
      <SpellModalActions
        canCast
        selectedSpell={spell}
        level={0}
        onCast={onCast}
        onClose={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '施放【Fire Bolt】' }))
    expect(onCast).toHaveBeenCalledWith(spell, 1)
  })

  it('shows disabled reasons and does not cast while blocked', () => {
    const onCast = vi.fn()

    render(
      <SpellModalActions
        canCast={false}
        disabledReason="请先选择一个目标再施法"
        selectedSpell={{ name: 'Magic Missile' }}
        level={1}
        onCast={onCast}
        onClose={vi.fn()}
      />,
    )

    const cast = screen.getByRole('button', { name: '施放【Magic Missile】' })
    expect(cast).toBeDisabled()
    expect(cast).toHaveAttribute('data-ready', 'false')
    expect(cast).toHaveAttribute('title', '请先选择一个目标再施法')
    expect(screen.getByRole('status')).toHaveTextContent('请先选择一个目标再施法')

    fireEvent.click(cast)
    expect(onCast).not.toHaveBeenCalled()
  })

  it('keeps the cancel action contract', () => {
    const onClose = vi.fn()

    render(
      <SpellModalActions
        canCast={false}
        selectedSpell={null}
        onCast={vi.fn()}
        onClose={onClose}
      />,
    )

    const group = screen.getByRole('group', { name: '施法操作' })
    fireEvent.click(within(group).getByRole('button', { name: '取消' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
