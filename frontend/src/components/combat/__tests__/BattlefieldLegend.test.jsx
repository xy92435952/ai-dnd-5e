import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import BattlefieldLegend from '../BattlefieldLegend'

describe('BattlefieldLegend', () => {
  it('renders only active battlefield marks and modes', () => {
    render(
      <BattlefieldLegend
        walls={new Set(['1_1', '1_2'])}
        hazards={new Set(['2_2'])}
        objectives={new Set(['3_3'])}
        threatCells={new Set(['4_4', '4_5'])}
        aoeCells={{ center: '5_5', ring: new Set(['5_5', '5_6']), template: 'cone' }}
        aoeLockedCenter="5_5"
        moveMode
      />,
    )

    const legend = screen.getByRole('list', { name: '战场图例' })
    expect(legend).toHaveTextContent('掩护')
    expect(legend).toHaveTextContent('2')
    expect(legend).toHaveTextContent('危险')
    expect(legend).toHaveTextContent('目标点')
    expect(legend).toHaveTextContent('威胁区')
    expect(legend).toHaveTextContent('范围 锥形 已锁定')
    expect(legend).toHaveTextContent('移动')
    expect(legend).not.toHaveTextContent('协助')
    expect(within(legend).getByRole('listitem', { name: '掩护：2 格' })).toBeInTheDocument()
    expect(within(legend).getByRole('listitem', { name: '危险：1 格' })).toBeInTheDocument()
    expect(within(legend).getByRole('listitem', { name: '目标点：1 格' })).toBeInTheDocument()
    expect(within(legend).getByRole('listitem', { name: '威胁区：2 格' })).toBeInTheDocument()
    expect(within(legend).getByRole('listitem', { name: '范围 锥形 已锁定：2 格' })).toBeInTheDocument()
    expect(within(legend).getByRole('listitem', { name: '移动' })).toBeInTheDocument()
  })

  it('names selected-target cover path context when prediction includes cover cells', () => {
    render(
      <BattlefieldLegend
        prediction={{
          target_ac: 14,
          effective_target_ac: 19,
          cover_bonus: 5,
          cover_detail: {
            bonus: 5,
            raw_bonus: 5,
            cells: [{ cell: '3_0', terrain: 'total_cover', weight: 2 }],
          },
        }}
      />,
    )

    const legend = screen.getByRole('list', { name: '战场图例' })
    const coverPath = within(legend).getByRole('listitem', {
      name: '3/4 掩护 +5 AC 路径：掩护使本次攻击的 AC 从 14 提升到 19。路径经过 3_0 total_cover。',
    })
    expect(coverPath).toHaveClass('cover-path')
    expect(coverPath).toHaveAttribute(
      'title',
      '掩护使本次攻击的 AC 从 14 提升到 19。路径经过 3_0 total_cover。',
    )
  })

  it('stays hidden when no battlefield context is active', () => {
    const { container } = render(<BattlefieldLegend />)

    expect(container.firstChild).toBeNull()
  })
})
