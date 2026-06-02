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

  it('shows selected target fit before choosing a spell', () => {
    render(
      <SpellModalList
        level={1}
        shownSpells={[
          {
            name: 'Cure Wounds',
            level: 1,
            type: 'heal',
            target_type: 'ally',
            heal: '1d8',
          },
          {
            name: 'Guiding Bolt',
            level: 1,
            type: 'damage',
            target_type: 'enemy',
            desc: 'Make a ranged spell attack.',
          },
          {
            name: 'Sacred Flame',
            level: 0,
            type: 'damage',
            target_type: 'enemy',
            damage: '1d8',
            save: 'dex',
          },
          {
            name: 'Fireball',
            level: 3,
            type: 'damage',
            aoe: true,
            damage: '8d6',
          },
        ]}
        cantrips={[]}
        combat={{
          entities: {
            'hero-1': {
              id: 'hero-1',
              name: 'Cleric',
              derived: { spell_attack_bonus: 6, spell_save_dc: 14 },
            },
            'enemy-1': {
              id: 'enemy-1',
              name: 'Cultist',
              is_enemy: true,
              ac: 15,
              derived: { saving_throws: { dex: 5 } },
              conditions: ['restrained'],
              condition_durations: { restrained: 2 },
            },
          },
        }}
        selectedTarget="enemy-1"
        playerId="hero-1"
        selectedSpell={null}
        setSelectedSpell={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    expect(within(screen.getByLabelText('目标适配 Cure Wounds')).getByText('目标不匹配')).toHaveAttribute(
      'title',
      '当前选中敌方；治疗或友方法术需要队友或自己。',
    )
    const guidingFit = screen.getByLabelText('目标适配 Guiding Bolt')
    expect(within(guidingFit).getByText('目标 Cultist')).toHaveAttribute(
      'title',
      '当前目标可用于此法术。',
    )
    expect(within(guidingFit).getByText('AC 15 · 9+ · 60%')).toHaveAttribute(
      'title',
      '法术攻击基础估算：AC 15 · d20 需 9+ · 约 60%。未包含临时掩护、优势/劣势或反应修正。',
    )
    expect(within(guidingFit).getByText('速度 0')).toHaveAttribute(
      'title',
      '移动速度降为 0。 来源：束缚 (2轮)。',
    )
    expect(within(guidingFit).getByText('受击优势')).toBeInTheDocument()
    expect(within(guidingFit).getByText('攻击劣势')).toBeInTheDocument()
    const sacredFit = screen.getByLabelText('目标适配 Sacred Flame')
    expect(within(sacredFit).getByText('9+ · 60%通过')).toHaveAttribute(
      'title',
      '目标豁免预估：敏捷豁免 +5 · d20 需 9+ · 约 60%通过。实际结算仍以后端骰子、条件和临时修正为准。',
    )
    expect(within(screen.getByLabelText('目标适配 Fireball')).getByText('选落点')).toHaveAttribute(
      'title',
      '范围法术通过战场落点决定目标。',
    )
  })
})
