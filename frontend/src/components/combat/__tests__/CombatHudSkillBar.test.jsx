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

  it('shows why a skill is unavailable and blocks the click', () => {
    const onSkillClick = vi.fn()

    const { container } = render(
      <CombatHudSkillBar
        skillBar={[
          { k: 'atk', label: '攻击', glyph: 'A', cost: '动作', key: '1', kind: 'attack', available: true },
        ]}
        session={{ player: { derived: {} } }}
        entities={{}}
        selectedTarget={null}
        turnState={{ action_used: false }}
        onSkillClick={onSkillClick}
        isPlayerTurn
      />,
    )

    const attack = container.querySelector('.slot-key.attack')
    expect(attack).toHaveAttribute('aria-disabled', 'true')
    expect(attack).toHaveAttribute('title', '需要先选择目标')
    expect(screen.getAllByText('需要先选择目标').length).toBeGreaterThan(0)

    fireEvent.click(attack)
    expect(onSkillClick).not.toHaveBeenCalled()
  })

  it('uses turn economy to explain spent actions', () => {
    const onSkillClick = vi.fn()

    const { container } = render(
      <CombatHudSkillBar
        skillBar={[
          { k: 'dodge', label: '闪避', glyph: 'D', cost: '动作', key: '7', kind: 'action', available: true },
        ]}
        session={{ player: { derived: {} } }}
        entities={{}}
        selectedTarget={null}
        turnState={{ action_used: true }}
        onSkillClick={onSkillClick}
        isPlayerTurn
      />,
    )

    const dodge = container.querySelector('.slot-key.action')
    expect(dodge).toHaveAttribute('title', '本回合动作已使用')
    fireEvent.click(dodge)
    expect(onSkillClick).not.toHaveBeenCalled()
  })
})
