import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import TargetCard from '../TargetCard'

describe('TargetCard', () => {
  it('shows target vitals and detailed selection preview', () => {
    render(
      <TargetCard
        entity={{
          id: 'enemy-1',
          name: '训练假人',
          hp_current: 7,
          hp_max: 12,
          ac: 13,
        }}
        prediction={{
          hit_rate: 0.65,
          crit_rate: 0.05,
          expected_damage: 4.9,
          damage_min: 4,
          damage_max: 11,
          damage_dice: '1d8+3',
          damage_type: '钝击',
          target_ac: 13,
          effective_target_ac: 15,
          cover_bonus: 2,
          attack_bonus: 6,
          advantage: true,
          modifiers: ['优势', '半掩护'],
        }}
      />,
    )

    expect(screen.getByText(/训练假人/)).toBeInTheDocument()
    expect(screen.getByText(/HP/)).toHaveTextContent('HP 7/12 · AC 13')
    expect(screen.getByText('命中率')).toBeInTheDocument()
    expect(screen.getByText('65%')).toBeInTheDocument()
    expect(screen.getByText('暴击率')).toBeInTheDocument()
    expect(screen.getByText('5%')).toBeInTheDocument()
    expect(screen.getByText('1d8+3 · 期望 4.9 钝击')).toBeInTheDocument()
    expect(screen.getByText('伤害范围')).toBeInTheDocument()
    expect(screen.getByText('4-11 钝击')).toBeInTheDocument()
    expect(screen.getByText('13 -> 15')).toBeInTheDocument()
    expect(screen.getByText('+2 AC')).toBeInTheDocument()
    expect(screen.getByText('+6')).toBeInTheDocument()
    expect(screen.getByText('优势 / 半掩护')).toBeInTheDocument()
  })

  it('renders nothing without a selected entity', () => {
    const { container } = render(<TargetCard entity={null} prediction={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
