import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
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

    const legend = screen.getByLabelText('战场图例')
    expect(legend).toHaveTextContent('掩护')
    expect(legend).toHaveTextContent('2')
    expect(legend).toHaveTextContent('危险')
    expect(legend).toHaveTextContent('目标点')
    expect(legend).toHaveTextContent('威胁区')
    expect(legend).toHaveTextContent('范围 锥形 已锁定')
    expect(legend).toHaveTextContent('移动')
    expect(legend).not.toHaveTextContent('协助')
  })

  it('stays hidden when no battlefield context is active', () => {
    const { container } = render(<BattlefieldLegend />)

    expect(container.firstChild).toBeNull()
  })
})
