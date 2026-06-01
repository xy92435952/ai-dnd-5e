import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import SpellModalList from '../SpellModalList'

describe('SpellModalList', () => {
  it('surfaces spell rule tags before selection', () => {
    render(
      <SpellModalList
        level={3}
        shownSpells={[{
          name: 'Fireball',
          level: 3,
          type: 'damage',
          damage: '8d6',
          aoe: true,
          target_type: 'ground point',
          save: 'dex',
          half_on_save: true,
          casting_time: '1 action',
          range: '150 ft',
          desc: 'A bright streak flashes to a point you choose.',
        }]}
        cantrips={[]}
        selectedSpell={null}
        setSelectedSpell={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    const tags = screen.getByLabelText('法术规则 Fireball')
    expect(within(tags).getByText('3环')).toBeInTheDocument()
    expect(within(tags).getByText('伤害')).toBeInTheDocument()
    expect(within(tags).getByText('范围')).toBeInTheDocument()
    expect(within(tags).getByText('地点')).toBeInTheDocument()
    expect(within(tags).getByText('敏捷豁免')).toBeInTheDocument()
    const preview = screen.getByLabelText('法术预览 Fireball')
    expect(within(preview).getByText('效果')).toBeInTheDocument()
    expect(within(preview).getByText('伤害 8d6')).toBeInTheDocument()
    expect(within(preview).getByText('结算')).toBeInTheDocument()
    expect(within(preview).getByText('敏捷豁免 · 成功减半')).toBeInTheDocument()
    expect(within(preview).getByText('时机')).toBeInTheDocument()
    expect(within(preview).getByText('1 动作 · 射程 150 ft')).toBeInTheDocument()
  })

  it('shows caster DC and spell attack bonus in pre-selection previews', () => {
    render(
      <SpellModalList
        level={1}
        shownSpells={[
          {
            name: 'Hold Person',
            level: 2,
            type: 'control',
            save: 'wis',
            casting_time: '1 action',
          },
          {
            name: 'Guiding Bolt',
            level: 1,
            type: 'damage',
            desc: 'Make a ranged spell attack.',
            casting_time: '1 action',
          },
        ]}
        cantrips={[]}
        caster={{ derived: { spell_save_dc: 15, spell_attack_bonus: 6 } }}
        selectedSpell={null}
        setSelectedSpell={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    expect(within(screen.getByLabelText('法术预览 Hold Person')).getByText('感知豁免 · DC 15')).toBeInTheDocument()
    expect(within(screen.getByLabelText('法术预览 Guiding Bolt')).getByText('法术攻击检定 · +6')).toBeInTheDocument()
  })
})
