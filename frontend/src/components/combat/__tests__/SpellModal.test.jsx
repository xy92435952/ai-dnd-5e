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
    }

    render(
      <SpellModal
        spells={[fireBolt]}
        cantrips={['Fire Bolt']}
        slots={{}}
        quickPick="火焰射线"
        selectedTarget="enemy-1"
        combat={{ entities: { 'enemy-1': { id: 'enemy-1', name: '训练假人', hp_current: 7 } } }}
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={onSpellHover}
      />
    )

    await waitFor(() => {
      expect(onSpellHover).toHaveBeenCalledWith(fireBolt)
    })
    expect(screen.getByRole('region', { name: '施法计划' })).toBeInTheDocument()
    expect(screen.getByText('戏法，无需法术位')).toBeInTheDocument()
    expect(screen.getByText('训练假人')).toBeInTheDocument()
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

    expect(screen.getByText('DEX save · DC 15 · success halves damage')).toBeInTheDocument()
    expect(screen.getByText('已锁定 · 中心 5, 5')).toBeInTheDocument()
    const plan = screen.getByLabelText('施法计划')
    expect(within(plan).getByText('敌方')).toBeInTheDocument()
    expect(within(plan).getByText('Goblin')).toBeInTheDocument()
    expect(within(plan).getByText('友方')).toBeInTheDocument()
    expect(within(plan).getByText('Companion')).toBeInTheDocument()
    expect(within(plan).getByText('自身')).toBeInTheDocument()
    expect(within(plan).getByText('Wizard')).toBeInTheDocument()
    const breakdown = screen.getByLabelText('AoE target breakdown')
    expect(within(breakdown).getByText('Enemies 1')).toBeInTheDocument()
    expect(within(breakdown).getByText('Allies 1')).toBeInTheDocument()
    expect(within(breakdown).getByText('Self')).toBeInTheDocument()
    expect(within(breakdown).getByText('Friendly fire')).toBeInTheDocument()

    const placementActions = screen.getByLabelText('AoE placement actions')
    fireEvent.click(within(placementActions).getByRole('button', { name: '重新选择落点' }))
    expect(onResetAoeCenter).toHaveBeenCalled()
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

    const cast = screen.getByTitle('请选择队友或自己作为法术目标')
    expect(cast).toBeDisabled()
    expect(cast).toHaveAttribute('title', '请选择队友或自己作为法术目标')
    expect(screen.getAllByText('请选择队友或自己作为法术目标').length).toBeGreaterThan(0)
    fireEvent.click(cast)
    expect(onCast).not.toHaveBeenCalled()
  })
})
