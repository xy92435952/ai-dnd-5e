import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
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
    const labels = container.querySelectorAll('.slot-label-bar span')
    expect(labels[0]).toHaveClass('ready')
    expect(labels[0]).toHaveAttribute('title', '协助 · 动作 · 可用')
    expect(labels[1]).toHaveAttribute('title', '治疗药剂 · 物品 · 动作 · 可用')
    expect(labels[2]).toHaveAttribute('aria-label', '再接再厉：可用')

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
    const attackLabel = container.querySelector('.slot-label-bar span')
    expect(attack).toHaveAttribute('aria-disabled', 'true')
    expect(attack).toHaveAttribute('title', '需要先选择目标')
    expect(attackLabel).toHaveClass('blocked')
    expect(attackLabel).toHaveAttribute('title', '攻击 · 攻击 · 动作 · 需要先选择目标')
    expect(attackLabel).toHaveAttribute('aria-label', '攻击：需要先选择目标')
    expect(screen.getAllByText('需要先选择目标').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('技能限制提示')).toHaveTextContent('需要先选择目标：攻击')

    fireEvent.click(attack)
    expect(onSkillClick).not.toHaveBeenCalled()
  })

  it('blocks metadata target-required skills before submit', () => {
    const onSkillClick = vi.fn()

    const { container } = render(
      <CombatHudSkillBar
        skillBar={[
          {
            k: 'acid_splash',
            label: '强酸飞溅',
            glyph: 'A',
            cost: '动作',
            key: '2',
            kind: 'spell',
            available: true,
            requires_target: true,
          },
        ]}
        session={{ player: { derived: {} } }}
        entities={{}}
        selectedTarget={null}
        turnState={{ action_used: false }}
        onSkillClick={onSkillClick}
        isPlayerTurn
      />,
    )

    const skill = container.querySelector('.slot-key.spell')
    expect(skill).toHaveAttribute('aria-disabled', 'true')
    expect(skill).toHaveAttribute('title', '需要先选择目标')
    expect(screen.getAllByText('需要先选择目标').length).toBeGreaterThan(0)

    fireEvent.click(skill)
    expect(onSkillClick).not.toHaveBeenCalled()
  })

  it('allows metadata target-required skills after selecting a target', () => {
    const onSkillClick = vi.fn()
    const skillEntry = {
      k: 'acid_splash',
      label: '强酸飞溅',
      glyph: 'A',
      cost: '动作',
      key: '2',
      kind: 'spell',
      available: true,
      target_type: 'enemy',
    }

    const { container } = render(
      <CombatHudSkillBar
        skillBar={[skillEntry]}
        session={{ player: { derived: {} } }}
        entities={{ 'enemy-1': { id: 'enemy-1', ac: 12 } }}
        selectedTarget="enemy-1"
        turnState={{ action_used: false }}
        onSkillClick={onSkillClick}
        isPlayerTurn
      />,
    )

    const skill = container.querySelector('.slot-key.spell')
    const skillLabel = container.querySelector('.slot-label-bar span')
    expect(skill).toHaveAttribute('aria-disabled', 'false')
    expect(skill).toHaveAttribute('title', '强酸飞溅')
    expect(skillLabel).toHaveClass('ready')
    expect(skillLabel).toHaveAttribute('aria-label', '强酸飞溅：可用')

    fireEvent.click(skill)
    expect(onSkillClick).toHaveBeenCalledWith(skillEntry)
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
    expect(screen.getByLabelText('技能限制提示')).toHaveTextContent('本回合动作已使用：闪避')
    fireEvent.click(dodge)
    expect(onSkillClick).not.toHaveBeenCalled()
  })

  it('shows selected-target prediction rows in attack tooltips', () => {
    render(
      <CombatHudSkillBar
        skillBar={[
          { k: 'atk', label: '攻击', glyph: 'A', cost: '动作', key: '1', kind: 'attack', available: true },
        ]}
        session={{ player: { derived: { attack_bonus: 5 } } }}
        entities={{
          'enemy-1': {
            id: 'enemy-1',
            ac: 13,
            conditions: ['restrained'],
            condition_durations: { restrained: 2 },
          },
        }}
        selectedTarget="enemy-1"
        prediction={{
          hit_rate: 0.7,
          crit_rate: 0.05,
          expected_damage: 5.8,
          damage_min: 4,
          damage_max: 11,
          damage_dice: '1d8+3',
          damage_type: '穿刺',
          target_ac: 13,
          effective_target_ac: 18,
          cover_bonus: 5,
          attack_bonus: 5,
          disadvantage: true,
          modifiers: ['劣势', '四分之三掩护'],
        }}
        turnState={{ action_used: false }}
        onSkillClick={vi.fn()}
        isPlayerTurn
      />,
    )

    expect(screen.getByText('命中率')).toBeInTheDocument()
    expect(screen.getByText('70%')).toBeInTheDocument()
    expect(screen.getByText('伤害')).toBeInTheDocument()
    expect(screen.getByText('1d8+3 · 期望 5.8 穿刺')).toBeInTheDocument()
    expect(screen.getByText('伤害范围')).toBeInTheDocument()
    expect(screen.getByText('4-11 穿刺')).toBeInTheDocument()
    expect(screen.getByText('目标AC')).toBeInTheDocument()
    expect(screen.getByText('13 -> 18')).toBeInTheDocument()
    expect(screen.getByText('掩护')).toBeInTheDocument()
    expect(screen.getByText('+5 AC')).toBeInTheDocument()
    expect(screen.getAllByText('劣势').length).toBeGreaterThan(0)
    expect(screen.getAllByText('3/4 掩护 +5 AC').length).toBeGreaterThan(0)
    expect(screen.getAllByText('有效 AC 18').length).toBeGreaterThan(0)
    expect(screen.getAllByTitle('掷两个 d20，取较低结果。').length).toBeGreaterThan(0)
    expect(screen.getByText('态势')).toBeInTheDocument()
    expect(screen.getByText('劣势 / 四分之三掩护')).toBeInTheDocument()
    expect(screen.getByText('资源')).toBeInTheDocument()
    expect(screen.getAllByText('动作').length).toBeGreaterThan(0)

    const preview = screen.getByLabelText('当前攻击预览')
    expect(preview).toHaveTextContent('目标')
    expect(preview).toHaveTextContent('命中 70%')
    expect(within(preview).getByText('劣势')).toHaveAttribute('title', '掷两个 d20，取较低结果。')
    expect(within(preview).getByText('3/4 掩护 +5 AC')).toBeInTheDocument()
    expect(within(preview).getByText('有效 AC 18')).toBeInTheDocument()
    expect(within(preview).getByText('速度 0')).toHaveAttribute(
      'title',
      '移动速度降为 0。 来源：束缚 (2轮)。',
    )
    expect(within(preview).getByText('受击优势')).toHaveAttribute(
      'title',
      '攻击此生物具有优势。 来源：束缚 (2轮)。',
    )
  })
})
