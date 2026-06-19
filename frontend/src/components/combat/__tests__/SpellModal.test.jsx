import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import SpellModal from '../SpellModal'

describe('SpellModal', () => {
  it('preselects a quick-picked cantrip by localized name and casts it as a cantrip', async () => {
    const onCast = vi.fn()
    const onSpellHover = vi.fn()
    const fireBolt = {
      name: '火焰射线',
      name_en: 'Fire Bolt',
      level: 0,
      type: 'damage',
      damage: '1d10',
      desc: 'Make a ranged spell attack.',
    }

    render(
      <SpellModal
        spells={[fireBolt]}
        cantrips={['Fire Bolt']}
        slots={{}}
        quickPick="火焰射线"
        selectedTarget="enemy-1"
        playerId="hero-1"
        combat={{
          entities: {
            'hero-1': {
              id: 'hero-1',
              name: '法师',
              derived: { spell_attack_bonus: 5 },
            },
            'enemy-1': {
              id: 'enemy-1',
              name: '训练假人',
              hp_current: 7,
              ac: 13,
              conditions: ['restrained'],
              condition_durations: { restrained: 2 },
            },
          },
        }}
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={onSpellHover}
      />
    )

    const dialog = screen.getByRole('dialog', { name: '选择法术' })
    expect(dialog).toHaveClass('spell-modal-dialog')
    expect(screen.getByRole('button', { name: '关闭施法面板' })).toHaveClass('spell-modal-close')

    await waitFor(() => {
      expect(onSpellHover).toHaveBeenCalledWith(fireBolt)
    })
    expect(screen.getByRole('region', { name: '施法计划' })).toBeInTheDocument()
    const preflight = screen.getByLabelText('施法预检')
    expect(within(preflight).getByText('消耗')).toBeInTheDocument()
    expect(within(preflight).getByText('戏法')).toBeInTheDocument()
    expect(within(preflight).getByText('法攻 +5 · AC 13 · 8+ · 65%')).toBeInTheDocument()
    expect(within(preflight).getByText('训练假人')).toBeInTheDocument()
    expect(screen.getByText('戏法，无需法术位')).toBeInTheDocument()
    expect(screen.getAllByText('训练假人').length).toBeGreaterThan(0)
    expect(screen.getByText('AC 13 · d20 需 8+ · 约 65%')).toBeInTheDocument()
    const impacts = screen.getByLabelText('目标状态影响')
    expect(within(impacts).getByText('速度 0')).toHaveAttribute(
      'title',
      '移动速度降为 0。 来源：束缚 (2轮)。',
    )
    expect(within(impacts).getByText('受击优势')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /施放/ }))

    expect(onCast).toHaveBeenCalledWith(fireBolt, 1)
  })

  it('preselects a leveled quick pick by English name and keeps its spell level', async () => {
    const onCast = vi.fn()
    const cureWounds = {
      name: '治愈创伤',
      name_en: 'Cure Wounds',
      level: 1,
      type: 'heal',
      heal: '1d8',
    }

    render(
      <SpellModal
        spells={[cureWounds]}
        cantrips={[]}
        slots={{ '1st': 1 }}
        quickPick="cure-wounds"
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={vi.fn()}
      />
    )

    await screen.findByText('治愈创伤')
    fireEvent.click(screen.getByRole('button', { name: /施放/ }))

    expect(onCast).toHaveBeenCalledWith(cureWounds, 1)
  })

  it('explains why the cast button is disabled before selecting a spell', () => {
    const onCast = vi.fn()

    render(
      <SpellModal
        spells={[{
          name: '魔法飞弹',
          name_en: 'Magic Missile',
          level: 1,
          type: 'damage',
          damage: '1d4+1',
        }]}
        cantrips={[]}
        slots={{ '1st': 1 }}
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    const cast = screen.getByRole('button', { name: /^施放$/ })
    expect(cast).toBeDisabled()
    expect(cast).toHaveAttribute('title', '请选择法术')
    expect(screen.getByText('请选择法术')).toBeInTheDocument()

    fireEvent.click(cast)
    expect(onCast).not.toHaveBeenCalled()
  })

  it('explains unavailable spell slots and keeps those tabs disabled', () => {
    const onCast = vi.fn()

    render(
      <SpellModal
        spells={[{
          name: '魔法飞弹',
          name_en: 'Magic Missile',
          level: 1,
          type: 'damage',
          damage: '1d4+1',
        }]}
        cantrips={[]}
        slots={{ '1st': 0 }}
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    const firstLevelTab = screen.getByRole('button', { name: '1环 (0)' })
    expect(firstLevelTab).toBeDisabled()
    expect(firstLevelTab).toHaveAttribute('title', '没有可用的 1 环法术位')
  })

  it('blocks target-based damage spells before a target is selected', () => {
    const onCast = vi.fn()

    render(
      <SpellModal
        spells={[{
          name: '魔法飞弹',
          name_en: 'Magic Missile',
          level: 1,
          type: 'damage',
          damage: '1d4+1',
        }]}
        cantrips={[]}
        slots={{ '1st': 1 }}
        selectedTarget={null}
        aoeHover={null}
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '1环 (1)' }))
    fireEvent.click(screen.getByText('魔法飞弹'))
    const cast = screen.getByRole('button', { name: /^施放/ })
    expect(cast).toBeDisabled()
    expect(cast).toHaveAttribute('title', '请先选择一个目标再施法')
    expect(screen.getAllByText('请先选择一个目标再施法').length).toBeGreaterThan(0)

    fireEvent.click(cast)
    expect(onCast).not.toHaveBeenCalled()
  })

  it('blocks aoe spells until the battlefield has a hovered center point', () => {
    const onCast = vi.fn()

    render(
      <SpellModal
        spells={[{
          name: '火球术',
          name_en: 'Fireball',
          level: 3,
          type: 'damage',
          aoe: true,
          damage: '8d6',
        }]}
        cantrips={[]}
        slots={{ '3rd': 1 }}
        selectedTarget="enemy-1"
        aoeHover={null}
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '3环 (1)' }))
    fireEvent.click(screen.getByText('火球术'))
    const cast = screen.getByRole('button', { name: /^施放/ })
    expect(cast).toBeDisabled()
    expect(cast).toHaveAttribute('title', '请先在战场上确认法术中心点')
    expect(screen.getAllByText('请先在战场上确认法术中心点').length).toBeGreaterThan(0)

    fireEvent.click(cast)
    expect(onCast).not.toHaveBeenCalled()
  })

  it('shows an AoE target breakdown and friendly-fire risk before casting', () => {
    const onResetAoeCenter = vi.fn()
    render(
      <SpellModal
        spells={[{
          name: 'Fireball',
          level: 3,
          type: 'damage',
          aoe: true,
          damage: '8d6',
          save: 'dex',
          half_on_save: true,
          desc: '20ft radius sphere',
        }]}
        cantrips={[]}
        slots={{ '3rd': 1 }}
        playerId="hero-1"
        selectedTarget="enemy-1"
        aoeHover="5_5"
        aoeLockedCenter="5_5"
        combat={{
          entities: {
            'hero-1': { id: 'hero-1', name: 'Wizard', is_enemy: false, hp_current: 20, derived: { spell_save_dc: 15 } },
            'enemy-1': { id: 'enemy-1', name: 'Goblin', is_enemy: true, hp_current: 7 },
            'ally-1': { id: 'ally-1', name: 'Companion', is_enemy: false, hp_current: 10 },
          },
          entity_positions: {
            'hero-1': { x: 5, y: 5 },
            'enemy-1': { x: 6, y: 5 },
            'ally-1': { x: 4, y: 5 },
          },
        }}
        onCast={vi.fn()}
        onClose={vi.fn()}
        onSpellHover={vi.fn()}
        onResetAoeCenter={onResetAoeCenter}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /^3\u73af/ }))
    fireEvent.click(screen.getByText('Fireball'))

    const plan = screen.getByLabelText('施法计划')
    const preflight = screen.getByLabelText('施法预检')
    expect(within(preflight).getByText('3 环 · 1 -> 0')).toBeInTheDocument()
    expect(within(preflight).getByText('已锁定 · 中心 5, 5')).toBeInTheDocument()
    expect(within(preflight).getByText('影响 3 个：敌方 1 / 友方 1 / 自身')).toBeInTheDocument()
    expect(within(preflight).getByText('敏捷豁免 · DC 15 · 成功减半')).toBeInTheDocument()
    expect(within(plan).getAllByText('敏捷豁免 · DC 15 · 成功减半').length).toBeGreaterThanOrEqual(2)
    expect(within(plan).getAllByText('已锁定 · 中心 5, 5').length).toBeGreaterThanOrEqual(2)
    expect(within(plan).getByText('敌方')).toBeInTheDocument()
    expect(within(plan).getByText('Goblin')).toBeInTheDocument()
    expect(within(plan).getByText('友方')).toBeInTheDocument()
    expect(within(plan).getByText('Companion')).toBeInTheDocument()
    expect(within(plan).getAllByText('自身').length).toBeGreaterThanOrEqual(1)
    expect(within(plan).getByText('Wizard')).toBeInTheDocument()
    const breakdown = screen.getByLabelText('范围目标统计')
    expect(within(breakdown).getByText('敌方 1')).toBeInTheDocument()
    expect(within(breakdown).getByText('友方 1')).toBeInTheDocument()
    expect(within(breakdown).getByText('自身')).toBeInTheDocument()
    expect(within(breakdown).getByText('误伤风险')).toBeInTheDocument()
    const warnings = screen.getByLabelText('范围战术提醒')
    expect(within(warnings).getByText('误伤')).toBeInTheDocument()
    expect(within(warnings).getByText('伤害范围包含友方或施法者：Companion、Wizard')).toBeInTheDocument()

    const placementActions = screen.getByLabelText('范围落点操作')
    fireEvent.click(within(placementActions).getByRole('button', { name: '重新选择落点' }))
    expect(onResetAoeCenter).toHaveBeenCalled()
  })

  it('shows selected target saving throw odds before confirming a save spell', async () => {
    const onSpellHover = vi.fn()
    const sacredFlame = {
      name: 'Sacred Flame',
      level: 0,
      type: 'damage',
      target_type: 'enemy',
      damage: '1d8',
      save: 'dex',
    }

    render(
      <SpellModal
        spells={[sacredFlame]}
        cantrips={['Sacred Flame']}
        slots={{}}
        quickPick="Sacred Flame"
        selectedTarget="enemy-1"
        playerId="hero-1"
        combat={{
          entities: {
            'hero-1': { id: 'hero-1', name: 'Cleric', derived: { spell_save_dc: 14 } },
            'enemy-1': {
              id: 'enemy-1',
              name: 'Cultist',
              is_enemy: true,
              hp_current: 7,
              derived: { saving_throws: { dex: 5 } },
            },
          },
        }}
        onCast={vi.fn()}
        onClose={vi.fn()}
        onSpellHover={onSpellHover}
      />,
    )

    await waitFor(() => {
      expect(onSpellHover).toHaveBeenCalledWith(sacredFlame)
    })

    const plan = screen.getByLabelText('施法计划')
    const preflight = screen.getByLabelText('施法预检')
    expect(within(preflight).getByText('敏捷豁免 · DC 14 · 9+ · 60%通过 · 成功规避/减轻')).toBeInTheDocument()
    expect(within(plan).getByText('目标豁免')).toBeInTheDocument()
    expect(within(plan).getByText('敏捷豁免 +5 · d20 需 9+ · 约 60%通过')).toBeInTheDocument()
  })

  it('shows a Bardic spell-save toggle for selected save targets with an unused die', async () => {
    const onToggleBardicSpellSave = vi.fn()
    const sacredFlame = {
      name: 'Sacred Flame',
      level: 0,
      type: 'damage',
      target_type: 'enemy',
      damage: '1d8',
      save: 'dex',
    }

    render(
      <SpellModal
        spells={[sacredFlame]}
        cantrips={['Sacred Flame']}
        slots={{}}
        quickPick="Sacred Flame"
        selectedTarget="ally-1"
        playerId="hero-1"
        combat={{
          entities: {
            'hero-1': { id: 'hero-1', name: 'Cleric', derived: { spell_save_dc: 14 } },
            'ally-1': {
              id: 'ally-1',
              name: 'Bardic Target',
              is_enemy: false,
              hp_current: 12,
              derived: { saving_throws: { dex: 0 } },
              class_resources: {
                bardic_inspiration: { die: 'd8', uses_remaining: 1 },
              },
            },
          },
        }}
        useBardicSpellSave
        onToggleBardicSpellSave={onToggleBardicSpellSave}
        onCast={vi.fn()}
        onClose={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    const bardic = await screen.findByRole('button', { name: 'Bardic ON · d8' })
    expect(bardic).toHaveAttribute('aria-pressed', 'true')
    expect(bardic).toHaveClass('spell-modal-bardic-toggle')
    expect(bardic).toHaveAttribute('data-active', 'true')
    fireEvent.click(bardic)
    expect(onToggleBardicSpellSave).toHaveBeenCalledTimes(1)
  })

  it('closes when the backdrop or close button is used', () => {
    const onClose = vi.fn()

    render(
      <SpellModal
        spells={[]}
        cantrips={[]}
        slots={{}}
        onCast={vi.fn()}
        onClose={onClose}
        onSpellHover={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '选择法术' })
    fireEvent.click(screen.getByRole('button', { name: '关闭施法面板' }))
    expect(onClose).toHaveBeenCalledTimes(1)

    fireEvent.click(dialog.parentElement)
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('blocks healing spells when an enemy is selected', () => {
    const onCast = vi.fn()

    render(
      <SpellModal
        spells={[{
          name: 'Cure Wounds',
          level: 1,
          type: 'heal',
          target_type: 'ally',
          heal: '1d8',
        }]}
        cantrips={[]}
        slots={{ '1st': 1 }}
        selectedTarget="enemy-1"
        playerId="hero-1"
        combat={{
          entities: {
            'hero-1': { id: 'hero-1', is_enemy: false, hp_current: 8 },
            'enemy-1': { id: 'enemy-1', is_enemy: true, hp_current: 7 },
          },
        }}
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByTitle('1 环法术'))
    fireEvent.click(screen.getByText('Cure Wounds'))

    const cast = screen.getByRole('button', { name: /施放/ })
    expect(cast).toBeDisabled()
    expect(cast).toHaveAttribute('title', '请选择队友或自己作为法术目标')
    expect(screen.getAllByText('请选择队友或自己作为法术目标').length).toBeGreaterThan(0)
    fireEvent.click(cast)
    expect(onCast).not.toHaveBeenCalled()
  })

  it('enables a Magic Initiate spell without ordinary spell slots', () => {
    const onCast = vi.fn()
    const shield = {
      name: 'Shield',
      level: 1,
      type: 'utility',
    }

    render(
      <SpellModal
        spells={[shield]}
        cantrips={[]}
        slots={{ '1st': 0 }}
        playerId="hero-1"
        combat={{
          entities: {
            'hero-1': {
              id: 'hero-1',
              feats: [{ name: 'Magic Initiate', spell: 'Shield' }],
              class_resources: { magic_initiate_spell_uses_remaining: 1 },
            },
          },
        }}
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    const firstLevelTab = screen.getByRole('button', { name: /1\s*环\s*\(1\)/ })
    expect(firstLevelTab).not.toBeDisabled()
    fireEvent.click(firstLevelTab)
    fireEvent.click(screen.getByText('Shield'))
    fireEvent.click(screen.getByRole('button', { name: /施放/ }))

    expect(onCast).toHaveBeenCalledWith(shield, 1)
  })
})
