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
        aoeCells={{ center: '5_5', ring: new Set(['5_5', '5_6']) }}
        moveMode
      />,
    )

    const legend = screen.getByLabelText('Battlefield legend')
    expect(legend).toHaveTextContent('Cover')
    expect(legend).toHaveTextContent('2')
    expect(legend).toHaveTextContent('Hazard')
    expect(legend).toHaveTextContent('Objective')
    expect(legend).toHaveTextContent('Threat')
    expect(legend).toHaveTextContent('AoE')
    expect(legend).toHaveTextContent('Move')
    expect(legend).not.toHaveTextContent('Help')
  })

  it('stays hidden when no battlefield context is active', () => {
    const { container } = render(<BattlefieldLegend />)

    expect(container.firstChild).toBeNull()
  })
})
