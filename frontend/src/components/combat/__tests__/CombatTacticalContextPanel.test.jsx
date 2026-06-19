import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
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
          roleSummary: '防卫 x1 / 控制 x2',
          detailGroups: [
            { key: 'roles', label: '敌职', value: '防卫 x1 / 控制 x2', title: '防卫 x1 / 控制 x2' },
            { key: 'objective', label: '目标', value: 'Seal the rift · 1 格', title: 'Seal the rift' },
            { key: 'cover', label: '掩护', value: 'altar · 1 格', title: 'altar' },
            { key: 'terrain', label: '地形', value: 'oil slick · 1 格', title: 'oil slick' },
            { key: 'hazard', label: '危险', value: 'fire jet · 1 格', title: 'fire jet' },
          ],
          counts: { cover: 1, difficult: 1, hazard: 1, objective: 1 },
        }}
      />,
    )

    const panel = screen.getByLabelText('战术上下文')
    expect(panel).toHaveTextContent('Rune Hall Encounter')

    const metrics = within(panel).getByRole('list', { name: '战术核心指标' })
    expect(within(metrics).getByRole('listitem', { name: '目标：Seal the rift' })).toBeInTheDocument()
    expect(within(metrics).getByRole('listitem', { name: '地形：altar / oil slick' })).toBeInTheDocument()
    expect(within(metrics).getByRole('listitem', { name: '风险：fire jet' })).toBeInTheDocument()
    expect(within(metrics).getByRole('listitem', {
      name: '强度：困难 / 目标 中等 / 环境 致命',
    })).toBeInTheDocument()

    const details = within(panel).getByRole('list', { name: '战术要素明细' })
    expect(within(details).getByRole('listitem', { name: '敌职：防卫 x1 / 控制 x2' })).toHaveAttribute(
      'title',
      '防卫 x1 / 控制 x2',
    )
    expect(within(details).getByRole('listitem', { name: '目标：Seal the rift · 1 格' })).toHaveAttribute('title', 'Seal the rift')
    expect(within(details).getByRole('listitem', { name: '掩护：altar · 1 格' })).toBeInTheDocument()
    expect(within(details).getByRole('listitem', { name: '地形：oil slick · 1 格' })).toBeInTheDocument()
    expect(within(details).getByRole('listitem', { name: '危险：fire jet · 1 格' })).toBeInTheDocument()

    const counts = within(panel).getByRole('list', { name: '战术计数' })
    expect(within(counts).getByRole('listitem', { name: '掩护 1' })).toBeInTheDocument()
    expect(within(counts).getByRole('listitem', { name: '困难地形 1' })).toBeInTheDocument()
    expect(within(counts).getByRole('listitem', { name: '危险 1' })).toBeInTheDocument()
    expect(within(counts).getByRole('listitem', { name: '目标点 1' })).toBeInTheDocument()
    expect(within(counts).getByRole('listitem', { name: '防卫 x1 / 控制 x2' })).toBeInTheDocument()
    expect(within(counts).getByRole('listitem', { name: '环境 高压' })).toBeInTheDocument()
    expect(within(counts).getByRole('listitem', { name: '预置 2' })).toBeInTheDocument()
  })

  it('stays hidden when no context exists', () => {
    const { container } = render(<CombatTacticalContextPanel context={{ hasContext: false }} />)

    expect(container.firstChild).toBeNull()
  })
})
