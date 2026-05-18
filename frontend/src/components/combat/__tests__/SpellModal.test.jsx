import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import SpellModal from '../SpellModal'

describe('SpellModal', () => {
  it('shows selected target and AoE target guidance before casting', () => {
    const onCast = vi.fn()
    render(
      <SpellModal
        spells={[
          { name: '火球术', level: 3, type: 'damage', damage: '8d6', aoe: { type: 'sphere', radius: 20 }, desc: '爆炸火焰' },
        ]}
        cantrips={[]}
        slots={{ '3rd': 1 }}
        selectedTargetName="哥布林"
        selectedTargetCount={3}
        onCast={onCast}
        onClose={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /3环/ }))
    fireEvent.click(screen.getByText('火球术'))

    expect(screen.getByText(/范围：20ft/)).toBeInTheDocument()
    expect(screen.getAllByText(/哥布林/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/预计影响 3 个目标/).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: /施放/ }))
    expect(onCast).toHaveBeenCalledWith(expect.objectContaining({ name: '火球术' }), 3)
  })

  it('disables damage spell casting until a target is selected', () => {
    render(
      <SpellModal
        spells={[{ name: '魔法飞弹', level: 1, type: 'damage', damage: '3d4+3' }]}
        cantrips={[]}
        slots={{ '1st': 1 }}
        selectedTargetName=""
        selectedTargetCount={0}
        onCast={vi.fn()}
        onClose={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /1环/ }))
    fireEvent.click(screen.getByText('魔法飞弹'))

    expect(screen.getByRole('button', { name: /施放/ })).toBeDisabled()
    expect(screen.getByText('请选择目标')).toBeInTheDocument()
  })
})
