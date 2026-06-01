import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatTacticalContextPanel from '../CombatTacticalContextPanel'

describe('CombatTacticalContextPanel', () => {
  it('renders compact encounter context', () => {
    render(
      <CombatTacticalContextPanel
        context={{
          hasContext: true,
          title: 'Rune Hall Encounter',
          difficulty: 'hard',
          targetDifficulty: 'medium',
          environmentPressure: 'heavy',
          environmentAdjustedDifficulty: 'deadly',
          stagedCount: 2,
          objectives: ['Seal the rift'],
          terrain: ['oil slick'],
          cover: ['altar'],
          hazards: ['fire jet'],
          detailGroups: [
            { key: 'objective', label: '目标', value: 'Seal the rift · 1 格', title: 'Seal the rift' },
            { key: 'cover', label: '掩护', value: 'altar · 1 格', title: 'altar' },
            { key: 'terrain', label: '地形', value: 'oil slick · 1 格', title: 'oil slick' },
            { key: 'hazard', label: '危险', value: 'fire jet · 1 格', title: 'fire jet' },
          ],
          counts: { cover: 1, difficult: 1, hazard: 1, objective: 1 },
        }}
      />,
    )

    expect(screen.getByLabelText('战术上下文')).toBeTruthy()
    expect(screen.getByText('Rune Hall Encounter')).toBeTruthy()
    expect(screen.getAllByText('目标').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('地形').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('风险')).toBeTruthy()
    expect(screen.getByText('强度')).toBeTruthy()
    expect(screen.getByText('Seal the rift')).toBeTruthy()
    expect(screen.getByText('altar / oil slick')).toBeTruthy()
    expect(screen.getByText('fire jet')).toBeTruthy()
    expect(screen.getByText('困难 / 目标 中等 / 环境 致命')).toBeTruthy()
    expect(screen.getByLabelText('战术要素明细')).toBeTruthy()
    expect(screen.getAllByText('掩护').length).toBeGreaterThan(0)
    expect(screen.getAllByText('危险').length).toBeGreaterThan(0)
    expect(screen.getByText('altar · 1 格')).toBeTruthy()
    expect(screen.getByText('oil slick · 1 格')).toBeTruthy()
    expect(screen.getByText('fire jet · 1 格')).toBeTruthy()
    expect(screen.getByText('困难地形 1')).toBeTruthy()
    expect(screen.getByText('环境 高压')).toBeTruthy()
    expect(screen.getByText('预置 2')).toBeTruthy()
  })

  it('stays hidden when no context exists', () => {
    const { container } = render(<CombatTacticalContextPanel context={{ hasContext: false }} />)

    expect(container.firstChild).toBeNull()
  })
})
