import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent, screen } from '@testing-library/react'
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
    expect(cell).toHaveAttribute('role', 'button')
    expect(cell).toHaveAttribute('title', '选择 Target')

    fireEvent.click(cell)
    expect(onSelectTarget).toHaveBeenCalledWith('enemy')
    expect(onMoveTo).not.toHaveBeenCalled()

    fireEvent.mouseEnter(cell)
    expect(onAoeHover).toHaveBeenCalledWith('2_3')

  })

  it('supports keyboard selection for interactive battlefield cells', () => {
    const onSelectTarget = vi.fn()

    render(
      <IsoBattlefield
        viewWidth={1}
        viewHeight={1}
        cam={{ x0: 0, y0: 0 }}
        walls={new Set()}
        hazards={new Set()}
        entityPositions={{ enemy: { x: 0, y: 0 } }}
        entities={{
          enemy: {
            id: 'enemy',
            name: 'Target',
            is_enemy: true,
            hp_current: 3,
            hp_max: 6,
          },
        }}
        selectedTarget={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode={false}
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        playerId="player"
        onSelectTarget={onSelectTarget}
        onMoveTo={vi.fn()}
        onAoeHover={vi.fn()}
      />,
    )

    const cell = screen.getByRole('button', { name: '选择 Target' })
    fireEvent.keyDown(cell, { key: 'Enter' })
    expect(onSelectTarget).toHaveBeenCalledWith('enemy')
  })

  it('routes allied unit clicks to Help while help mode is active', () => {
    const onSelectTarget = vi.fn()
    const onHelpTarget = vi.fn()
    const onMoveTo = vi.fn()

    const { container } = render(
      <IsoBattlefield
        viewWidth={2}
        viewHeight={1}
        cam={{ x0: 0, y0: 0 }}
        walls={new Set()}
        hazards={new Set()}
        entityPositions={{
          ally: { x: 0, y: 0 },
          enemy: { x: 1, y: 0 },
        }}
        entities={{
          ally: {
            id: 'ally',
            name: 'Ally',
            is_enemy: false,
            hp_current: 8,
            hp_max: 10,
          },
          enemy: {
            id: 'enemy',
            name: 'Enemy',
            is_enemy: true,
            hp_current: 8,
            hp_max: 10,
          },
        }}
        selectedTarget={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode={false}
        helpMode
        aoePreview={null}
        aoeHover={null}
        playerId="player"
        onSelectTarget={onSelectTarget}
        onHelpTarget={onHelpTarget}
        onMoveTo={onMoveTo}
        onAoeHover={vi.fn()}
      />
    )

    const cells = container.querySelectorAll('.iso-cell')
    fireEvent.click(cells[0])
    expect(onHelpTarget).toHaveBeenCalledWith('ally', expect.objectContaining({ name: 'Ally' }))
    expect(onSelectTarget).not.toHaveBeenCalled()
    expect(container.querySelector('.help-ring')).toBeTruthy()
    expect(cells[0]).toHaveAttribute('title', '协助 Ally')

    fireEvent.click(cells[1])
    expect(onSelectTarget).toHaveBeenCalledWith('enemy')
    expect(onHelpTarget).toHaveBeenCalledTimes(1)
  })

  it('keeps dying allies selectable for rescue spells instead of treating them as dead', () => {
    const onSelectTarget = vi.fn()

    const { container } = render(
      <IsoBattlefield
        viewWidth={1}
        viewHeight={1}
        cam={{ x0: 0, y0: 0 }}
        walls={new Set()}
        hazards={new Set()}
        entityPositions={{ ally: { x: 0, y: 0 } }}
        entities={{
          ally: {
            id: 'ally',
            name: 'Downed Ally',
            is_enemy: false,
            hp_current: 0,
            hp_max: 10,
            life_state: 'dying',
            death_saves: { successes: 0, failures: 1, stable: false },
          },
        }}
        selectedTarget={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode={false}
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        playerId="player"
        onSelectTarget={onSelectTarget}
        onMoveTo={vi.fn()}
        onAoeHover={vi.fn()}
      />
    )

    const cell = container.querySelector('.iso-cell')
    expect(container.querySelector('.iso-unit.life-dying')).toBeTruthy()
    fireEvent.click(cell)
    expect(onSelectTarget).toHaveBeenCalledWith('ally')
  })

  it('explains blocked wall cells and inert empty cells', () => {
    const onSelectTarget = vi.fn()
    const onMoveTo = vi.fn()

    const { container } = render(
      <IsoBattlefield
        viewWidth={2}
        viewHeight={1}
        cam={{ x0: 0, y0: 0 }}
        walls={new Set(['0_0'])}
        hazards={new Set()}
        entityPositions={{}}
        entities={{}}
        selectedTarget={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode={false}
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        playerId="player"
        onSelectTarget={onSelectTarget}
        onMoveTo={onMoveTo}
        onAoeHover={vi.fn()}
      />,
    )

    const cells = container.querySelectorAll('.iso-cell')
    expect(cells[0]).toHaveAttribute('aria-disabled', 'true')
    expect(cells[0]).toHaveAttribute('title', '墙体阻挡，无法选择或移动')
    expect(cells[1]).toHaveAttribute('aria-disabled', 'true')
    expect(cells[1]).toHaveAttribute('title', '开启移动模式后可选择空格移动')

    fireEvent.click(cells[0])
    fireEvent.click(cells[1])
    expect(onSelectTarget).not.toHaveBeenCalled()
    expect(onMoveTo).not.toHaveBeenCalled()
  })

  it('labels legal empty movement cells while move mode is active', () => {
    const onMoveTo = vi.fn()

    const { container } = render(
      <IsoBattlefield
        viewWidth={1}
        viewHeight={1}
        cam={{ x0: 4, y0: 7 }}
        walls={new Set()}
        hazards={new Set()}
        entityPositions={{}}
        entities={{}}
        selectedTarget={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        playerId="player"
        onSelectTarget={vi.fn()}
        onMoveTo={onMoveTo}
        onAoeHover={vi.fn()}
      />,
    )

    const cell = container.querySelector('.iso-cell')
    expect(cell).toHaveAttribute('role', 'button')
    expect(cell).not.toHaveAttribute('aria-disabled')
    expect(cell).toHaveAttribute('title', '移动到 4, 7')

    fireEvent.click(cell)
    expect(onMoveTo).toHaveBeenCalledWith(4, 7)
  })
})
