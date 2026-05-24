import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import IsoBattlefield from '../IsoBattlefield'

vi.mock('../../Sprite', () => ({
  default: () => <div data-testid="sprite" />,
}))

describe('IsoBattlefield', () => {
  it('keeps battlefield interactions wired through a unit cell', () => {
    const onSelectTarget = vi.fn()
    const onMoveTo = vi.fn()
    const onAoeHover = vi.fn()

    const { container } = render(
      <IsoBattlefield
        viewWidth={1}
        viewHeight={1}
        cam={{ x0: 2, y0: 3 }}
        walls={new Set()}
        hazards={new Set()}
        entityPositions={{ enemy: { x: 2, y: 3 } }}
        entities={{
          enemy: {
            id: 'enemy',
            name: 'Target',
            is_enemy: true,
            hp_current: 3,
            hp_max: 6,
          },
        }}
        selectedTarget="enemy"
        currentTurnCharacterId="enemy"
        threatCells={new Set(['2_3'])}
        aoeCells={{ center: '2_3', ring: new Set(['2_3']) }}
        moveMode
        aoePreview={{ radius: 1 }}
        aoeHover={null}
        playerId="player"
        onSelectTarget={onSelectTarget}
        onMoveTo={onMoveTo}
        onAoeHover={onAoeHover}
      />
    )

    const cell = container.querySelector('.iso-cell')
    expect(cell).toBeTruthy()
    expect(cell.className).toContain('target')
    expect(cell.className).toContain('aoe-center')

    fireEvent.click(cell)
    expect(onSelectTarget).toHaveBeenCalledWith('enemy')
    expect(onMoveTo).not.toHaveBeenCalled()

    fireEvent.mouseEnter(cell)
    expect(onAoeHover).toHaveBeenCalledWith('2_3')

  })
})
