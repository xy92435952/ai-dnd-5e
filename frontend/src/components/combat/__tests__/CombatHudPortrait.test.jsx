import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import CombatHudPortrait from '../CombatHudPortrait'

describe('CombatHudPortrait', () => {
  it('renders effective top-level hp max when exhaustion reduces the max', () => {
    render(
      <CombatHudPortrait
        session={{
          player: {
            name: 'Tired Hero',
            hp_current: 6,
            hp_max: 6,
            derived: { hp_max: 12, ac: 16, initiative: 2 },
            conditions: [],
          },
        }}
        playerClass="Fighter"
        playerLevel={1}
        turnState={{ movement_max: 6, movement_used: 0 }}
      />,
    )

    const portrait = screen.getByRole('region', { name: '当前战斗角色 Tired Hero' })
    expect(portrait).toHaveClass('hud-portrait')
    expect(within(portrait).getByRole('meter', { name: '生命值 6/6' })).toHaveAttribute('aria-valuemax', '6')
    expect(within(portrait).getByText('/ 6', { exact: false })).toBeTruthy()
  })

  it('uses the controlled character over the session player for multiplayer HUD', () => {
    render(
      <CombatHudPortrait
        session={{
          player: {
            name: 'Host Hero',
            hp_current: 12,
            hp_max: 12,
            derived: { ac: 14, initiative: 1 },
            conditions: [],
          },
        }}
        character={{
          name: 'Guest Hero',
          hp_current: 3,
          hp_max: 10,
          derived: { ac: 17, initiative: 4 },
          conditions: ['unconscious'],
        }}
        playerClass="Cleric"
        playerLevel={2}
        turnState={{ movement_max: 6, movement_used: 0 }}
      />,
    )

    const portrait = screen.getByRole('region', { name: '当前战斗角色 Guest Hero' })
    expect(within(portrait).getByText('Guest Hero')).toBeTruthy()
    expect(screen.queryByText('Host Hero')).toBeNull()
    expect(within(portrait).getByRole('meter', { name: '生命值 3/10' })).toHaveAttribute('aria-valuenow', '3')
    expect(within(portrait).getByText('/ 10', { exact: false })).toBeTruthy()
    expect(within(portrait).getByText('17')).toBeTruthy()
  })

  it('shows readable movement and equipped weapon resource summary', () => {
    render(
      <CombatHudPortrait
        session={{
          player: {
            name: 'Archer',
            hp_current: 10,
            hp_max: 10,
            derived: { ac: 14, initiative: 1 },
            equipment: {
              weapons: [
                { name: 'Longbow', ammo: 19, equipped: true },
              ],
            },
            conditions: [],
          },
        }}
        playerClass="Fighter"
        playerLevel={1}
        turnState={{ movement_max: 6, movement_used: 2 }}
      />,
    )

    const portrait = screen.getByRole('region', { name: '当前战斗角色 Archer' })
    expect(within(portrait).getByText('移动')).toBeTruthy()
    expect(within(portrait).getByText('4/6')).toBeTruthy()
    expect(within(portrait).getByLabelText('武器资源 Longbow 弹药 19')).toHaveClass('hud-resource')
    expect(within(portrait).getByText('弹药 19', { exact: false })).toBeTruthy()
  })

  it('explains active condition rules in the HUD', () => {
    render(
      <CombatHudPortrait
        session={{
          player: {
            name: 'Poisoned Hero',
            hp_current: 8,
            hp_max: 10,
            derived: { ac: 14, initiative: 1 },
            conditions: ['poisoned', 'fire_resistance'],
            condition_durations: { poisoned: 2 },
          },
        }}
        playerClass="Fighter"
        playerLevel={1}
        turnState={{ movement_max: 6, movement_used: 0 }}
      />,
    )

    const rules = screen.getByRole('list', { name: '当前状态规则' })
    expect(within(rules).getByRole('listitem', { name: /中毒：攻击骰和属性检定处于劣势/ })).toBeInTheDocument()
    expect(within(rules).getByRole('listitem', { name: /火焰抗性：此防护持续期间，火焰伤害降低/ })).toHaveClass('buff')

    const impacts = screen.getByRole('list', { name: '当前状态影响' })
    expect(impacts).toHaveTextContent('攻击劣势')
    expect(impacts).toHaveTextContent('抗性')
    expect(within(impacts).getByRole('listitem', { name: /伤害抗性已生效/ })).toHaveClass('good')
  })
})
