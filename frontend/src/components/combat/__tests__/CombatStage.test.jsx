import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CombatStage from '../CombatStage'

vi.mock('../../Sprite', () => ({
  default: () => <div data-testid="sprite" />,
}))

describe('CombatStage', () => {
  it('derives and displays the selected target cover path from prediction metadata', () => {
    const { container } = render(
      <CombatStage
        viewWidth={4}
        viewHeight={1}
        cam={{ x0: 0, y0: 0 }}
        walls={new Set(['2_0'])}
        hazards={new Set()}
        objectives={new Set()}
        terrainDetails={{
          '2_0': { terrain: 'cover', label: 'Low barricade', coverLevel: 'half' },
        }}
        tacticalContext={{ hasContext: false }}
        entityPositions={{ enemy: { x: 3, y: 0 } }}
        entities={{
          enemy: {
            id: 'enemy',
            name: 'Guard',
            is_enemy: true,
            hp_current: 18,
            hp_max: 18,
            ac: 14,
          },
        }}
        selectedTarget="enemy"
        selectedTargetEntity={{
          id: 'enemy',
          name: 'Guard',
          is_enemy: true,
          hp_current: 18,
          hp_max: 18,
          ac: 14,
        }}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode={false}
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        aoeLockedCenter={null}
        playerId="player"
        prediction={{
          hit_rate: 0.55,
          target_ac: 14,
          effective_target_ac: 16,
          cover_bonus: 2,
          cover_detail: {
            bonus: 2,
            raw_bonus: 2,
            cells: [{ cell: '2_0', terrain: 'cover', weight: 1 }],
          },
        }}
        canInspectTarget={false}
        inspectBusy={false}
        floats={[]}
        combatOver={false}
        onSelectTarget={vi.fn()}
        onInspectTarget={vi.fn()}
        onHelpTarget={vi.fn()}
        onMoveTo={vi.fn()}
        onAoeHover={vi.fn()}
        onAoeLockCenter={vi.fn()}
        onReturn={vi.fn()}
      />,
    )

    const coverPathCell = container.querySelector('[data-grid-key="2_0"]')
    const stageWash = container.querySelector('.combat-stage-wash')
    expect(stageWash).toBeInTheDocument()
    expect(stageWash).not.toHaveAttribute('style')
    expect(coverPathCell).toHaveClass('cover-path')
    expect(coverPathCell).toHaveAttribute(
      'title',
      '掩体: Low barricade阻挡，无法选择或移动 · 掩护路径 cover：半掩护 +2 AC',
    )

    const legend = screen.getByLabelText('战场图例')
    expect(legend).toHaveTextContent('半掩护 +2 AC 路径')
    expect(within(legend).getByTitle('掩护使本次攻击的 AC 从 14 提升到 16。路径经过 2_0 cover。')).toBeInTheDocument()

    const targetRules = screen.getByLabelText('攻击规则标签 Guard')
    expect(targetRules).toHaveTextContent('半掩护 +2 AC')
    expect(targetRules).toHaveTextContent('有效 AC 16')
  })

  it('derives speed-zero movement blocking from the player entity', () => {
    const onMoveTo = vi.fn()
    const { container } = render(
      <CombatStage
        viewWidth={1}
        viewHeight={1}
        cam={{ x0: 4, y0: 7 }}
        walls={new Set()}
        hazards={new Set()}
        objectives={new Set()}
        terrainDetails={{}}
        tacticalContext={{ hasContext: false }}
        entityPositions={{}}
        entities={{
          player: {
            id: 'player',
            name: 'Hero',
            is_enemy: false,
            hp_current: 12,
            conditions: ['grappled'],
            condition_durations: { grappled: 1 },
          },
        }}
        selectedTarget={null}
        selectedTargetEntity={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        aoeLockedCenter={null}
        playerId="player"
        prediction={null}
        canInspectTarget={false}
        inspectBusy={false}
        floats={[]}
        combatOver={false}
        onSelectTarget={vi.fn()}
        onInspectTarget={vi.fn()}
        onHelpTarget={vi.fn()}
        onMoveTo={onMoveTo}
        onAoeHover={vi.fn()}
        onAoeLockCenter={vi.fn()}
        onReturn={vi.fn()}
      />,
    )

    const cell = container.querySelector('[data-grid-key="4_7"]')
    expect(cell).toHaveAttribute('aria-disabled', 'true')
    expect(cell).toHaveAttribute('title', '被擒抱 (1轮) · 移动速度为 0')

    fireEvent.click(cell)
    expect(onMoveTo).not.toHaveBeenCalled()
  })

  it('derives frightened source movement blocking per target cell', () => {
    const onMoveTo = vi.fn()
    const { container } = render(
      <CombatStage
        viewWidth={2}
        viewHeight={1}
        cam={{ x0: 5, y0: 5 }}
        walls={new Set()}
        hazards={new Set()}
        objectives={new Set()}
        terrainDetails={{}}
        tacticalContext={{ hasContext: false }}
        entityPositions={{
          player: { x: 5, y: 5 },
          'enemy-1': { x: 8, y: 5 },
        }}
        entities={{
          player: {
            id: 'player',
            name: 'Hero',
            is_enemy: false,
            hp_current: 12,
            conditions: ['frightened'],
            condition_durations: { frightened: { duration: 2, source_id: 'enemy-1' } },
          },
          'enemy-1': {
            id: 'enemy-1',
            name: 'Fear Source',
            is_enemy: true,
            hp_current: 12,
          },
        }}
        selectedTarget={null}
        selectedTargetEntity={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        aoeLockedCenter={null}
        playerId="player"
        prediction={null}
        canInspectTarget={false}
        inspectBusy={false}
        floats={[]}
        combatOver={false}
        onSelectTarget={vi.fn()}
        onInspectTarget={vi.fn()}
        onHelpTarget={vi.fn()}
        onMoveTo={onMoveTo}
        onAoeHover={vi.fn()}
        onAoeLockCenter={vi.fn()}
        onReturn={vi.fn()}
      />,
    )

    const closerCell = container.querySelector('[data-grid-key="6_5"]')
    expect(closerCell).toHaveAttribute('aria-disabled', 'true')
    expect(closerCell).toHaveAttribute('title', '恐慌 · 不能主动靠近恐惧来源')

    fireEvent.click(closerCell)
    expect(onMoveTo).not.toHaveBeenCalled()
  })

  it('derives grapple drag movement notices and blocks over-budget drag cells', () => {
    const onMoveTo = vi.fn()
    const { container } = render(
      <CombatStage
        viewWidth={3}
        viewHeight={1}
        cam={{ x0: 7, y0: 5 }}
        walls={new Set()}
        hazards={new Set()}
        objectives={new Set()}
        terrainDetails={{}}
        tacticalContext={{ hasContext: false }}
        entityPositions={{
          player: { x: 5, y: 5 },
          'enemy-1': { x: 6, y: 5 },
        }}
        entities={{
          player: {
            id: 'player',
            name: 'Hero',
            is_enemy: false,
            hp_current: 12,
          },
          'enemy-1': {
            id: 'enemy-1',
            name: 'Dragged Duelist',
            is_enemy: true,
            hp_current: 12,
            conditions: ['grappled'],
            condition_durations: { grappled: { source_id: 'player' } },
          },
        }}
        selectedTarget={null}
        selectedTargetEntity={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        aoeLockedCenter={null}
        playerId="player"
        turnState={{ movement_used: 0, movement_max: 6, base_movement_max: 6 }}
        prediction={null}
        canInspectTarget={false}
        inspectBusy={false}
        floats={[]}
        combatOver={false}
        onSelectTarget={vi.fn()}
        onInspectTarget={vi.fn()}
        onHelpTarget={vi.fn()}
        onMoveTo={onMoveTo}
        onAoeHover={vi.fn()}
        onAoeLockCenter={vi.fn()}
        onReturn={vi.fn()}
      />,
    )

    const legalCell = container.querySelector('[data-grid-key="7_5"]')
    expect(legalCell).not.toHaveAttribute('aria-disabled')
    expect(legalCell).toHaveAttribute(
      'title',
      '移动到 7, 5 · 拖拽 Dragged Duelist：移动消耗翻倍，此移动消耗 4 格（剩余 6 格）',
    )

    const blockedCell = container.querySelector('[data-grid-key="9_5"]')
    expect(blockedCell).toHaveAttribute('aria-disabled', 'true')
    expect(blockedCell).toHaveAttribute(
      'title',
      '拖拽 Dragged Duelist 需要 8 格移动力，当前剩余 6 格',
    )

    fireEvent.click(legalCell)
    expect(onMoveTo).toHaveBeenCalledWith(7, 5)
    fireEvent.click(blockedCell)
    expect(onMoveTo).toHaveBeenCalledTimes(1)
  })

  it('derives prone stand-up movement notices from the player entity and turn state', () => {
    const onMoveTo = vi.fn()
    const { container } = render(
      <CombatStage
        viewWidth={1}
        viewHeight={1}
        cam={{ x0: 4, y0: 7 }}
        walls={new Set()}
        hazards={new Set()}
        objectives={new Set()}
        terrainDetails={{}}
        tacticalContext={{ hasContext: false }}
        entityPositions={{}}
        entities={{
          player: {
            id: 'player',
            name: 'Hero',
            is_enemy: false,
            hp_current: 12,
            conditions: ['prone'],
            condition_durations: { prone: 1 },
          },
        }}
        selectedTarget={null}
        selectedTargetEntity={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        aoeLockedCenter={null}
        playerId="player"
        turnState={{ movement_used: 0, movement_max: 6, base_movement_max: 6 }}
        prediction={null}
        canInspectTarget={false}
        inspectBusy={false}
        floats={[]}
        combatOver={false}
        onSelectTarget={vi.fn()}
        onInspectTarget={vi.fn()}
        onHelpTarget={vi.fn()}
        onMoveTo={onMoveTo}
        onAoeHover={vi.fn()}
        onAoeLockCenter={vi.fn()}
        onReturn={vi.fn()}
      />,
    )

    const cell = container.querySelector('[data-grid-key="4_7"]')
    expect(cell).not.toHaveAttribute('aria-disabled')
    expect(cell).toHaveAttribute('title', '移动到 4, 7 · 倒地 (1轮) · 移动前会先起身，消耗 3 格')

    fireEvent.click(cell)
    expect(onMoveTo).toHaveBeenCalledWith(4, 7)
  })

  it('derives prone stand-up blocking when remaining movement is insufficient', () => {
    const onMoveTo = vi.fn()
    const { container } = render(
      <CombatStage
        viewWidth={1}
        viewHeight={1}
        cam={{ x0: 4, y0: 7 }}
        walls={new Set()}
        hazards={new Set()}
        objectives={new Set()}
        terrainDetails={{}}
        tacticalContext={{ hasContext: false }}
        entityPositions={{}}
        entities={{
          player: {
            id: 'player',
            name: 'Hero',
            is_enemy: false,
            hp_current: 12,
            conditions: ['prone'],
          },
        }}
        selectedTarget={null}
        selectedTargetEntity={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        aoeLockedCenter={null}
        playerId="player"
        turnState={{ movement_used: 4, movement_max: 6, base_movement_max: 6 }}
        prediction={null}
        canInspectTarget={false}
        inspectBusy={false}
        floats={[]}
        combatOver={false}
        onSelectTarget={vi.fn()}
        onInspectTarget={vi.fn()}
        onHelpTarget={vi.fn()}
        onMoveTo={onMoveTo}
        onAoeHover={vi.fn()}
        onAoeLockCenter={vi.fn()}
        onReturn={vi.fn()}
      />,
    )

    const cell = container.querySelector('[data-grid-key="4_7"]')
    expect(cell).toHaveAttribute('aria-disabled', 'true')
    expect(cell).toHaveAttribute('title', '倒地 · 起身需要 3 格移动力，当前剩余 2 格')

    fireEvent.click(cell)
    expect(onMoveTo).not.toHaveBeenCalled()
  })

  it('explains difficult terrain movement cost and blocks over-budget destinations', () => {
    const onMoveTo = vi.fn()
    const { container } = render(
      <CombatStage
        viewWidth={2}
        viewHeight={1}
        cam={{ x0: 6, y0: 5 }}
        walls={new Set()}
        hazards={new Set(['6_5'])}
        objectives={new Set()}
        terrainDetails={{
          '6_5': { terrain: 'difficult', label: 'Mud slick' },
        }}
        tacticalContext={{ hasContext: false }}
        entityPositions={{
          player: { x: 5, y: 5 },
          'enemy-1': { x: 9, y: 5 },
        }}
        entities={{
          player: {
            id: 'player',
            name: 'Hero',
            is_enemy: false,
            hp_current: 12,
          },
          'enemy-1': {
            id: 'enemy-1',
            name: 'Guard',
            is_enemy: true,
            hp_current: 12,
          },
        }}
        selectedTarget={null}
        selectedTargetEntity={null}
        currentTurnCharacterId="player"
        threatCells={new Set()}
        aoeCells={{ center: null, ring: new Set() }}
        moveMode
        helpMode={false}
        aoePreview={null}
        aoeHover={null}
        aoeLockedCenter={null}
        playerId="player"
        turnState={{ movement_used: 4, movement_max: 6, base_movement_max: 6 }}
        prediction={null}
        canInspectTarget={false}
        inspectBusy={false}
        floats={[]}
        combatOver={false}
        onSelectTarget={vi.fn()}
        onInspectTarget={vi.fn()}
        onHelpTarget={vi.fn()}
        onMoveTo={onMoveTo}
        onAoeHover={vi.fn()}
        onAoeLockCenter={vi.fn()}
        onReturn={vi.fn()}
      />,
    )

    const difficultCell = container.querySelector('[data-grid-key="6_5"]')
    expect(difficultCell).not.toHaveAttribute('aria-disabled')
    expect(difficultCell).toHaveAttribute('title', expect.stringContaining('困难地形 Mud slick'))
    expect(difficultCell).toHaveAttribute('title', expect.stringContaining('此移动消耗 2 格'))

    const farCell = container.querySelector('[data-grid-key="7_5"]')
    expect(farCell).toHaveAttribute('aria-disabled', 'true')
    expect(farCell).toHaveAttribute('title', '困难地形需要 3 格移动力，当前剩余 2 格')

    fireEvent.click(difficultCell)
    expect(onMoveTo).toHaveBeenCalledWith(6, 5)
    fireEvent.click(farCell)
    expect(onMoveTo).toHaveBeenCalledTimes(1)
  })
})
