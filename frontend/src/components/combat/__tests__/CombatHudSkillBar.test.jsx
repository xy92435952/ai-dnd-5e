import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import CombatHudSkillBar from '../CombatHudSkillBar'

describe('CombatHudSkillBar', () => {
  it('labels action and item skills by their real action economy kind', () => {
    const onSkillClick = vi.fn()

    const { container } = render(
      <CombatHudSkillBar
        skillBar={[
          { k: 'help', label: '协助', glyph: '☉', cost: '动作', key: '4', kind: 'action', available: true },
          { k: 'pot_heal', label: '治疗药剂', glyph: '⚱', cost: '动作', key: '0', kind: 'item', available: true },
          { k: 'second_wind', label: '再接再厉', glyph: '✚', cost: '附赠', key: '5', kind: 'bonus', available: true },
        ]}
        session={{
          player: { derived: {} },
        }}
        entities={{}}
        selectedTarget={null}
        onSkillClick={onSkillClick}
        isPlayerTurn
      />,
    )

    expect(screen.getByText('动作 · 动作')).toBeInTheDocument()
    expect(screen.getByText('物品 · 动作')).toBeInTheDocument()
    expect(screen.getByText('附赠 · 附赠')).toBeInTheDocument()

    fireEvent.click(container.querySelector('.slot-key.item'))
    expect(onSkillClick).toHaveBeenCalledWith(expect.objectContaining({ k: 'pot_heal', kind: 'item' }))
  })
})
