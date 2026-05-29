import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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
        onCast={onCast}
        onClose={vi.fn()}
        onSpellHover={onSpellHover}
      />
    )

    await waitFor(() => {
      expect(onSpellHover).toHaveBeenCalledWith(fireBolt)
    })
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
    expect(screen.getByText('请先选择一个目标再施法')).toBeInTheDocument()

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
    expect(screen.getByText('请先在战场上确认法术中心点')).toBeInTheDocument()

    fireEvent.click(cast)
    expect(onCast).not.toHaveBeenCalled()
  })
})
