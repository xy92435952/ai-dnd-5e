import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CharacterCreateStepAbilities from '../CharacterCreateStepAbilities'

function makeCtx(overrides = {}) {
  const baseScores = {
    str: 12,
    dex: 14,
    con: 13,
    int: 10,
    wis: 10,
    cha: 8,
  }
  return {
    form: {
      char_class: 'Fighter',
      level: 1,
      multiclassEnabled: false,
      multiclass_class: '',
    },
    setScoreMethod: vi.fn(),
    setStandardAssigned: vi.fn(),
    scoreMethod: 'pointbuy',
    pointsLeft: 2,
    baseScores,
    racialBonuses: { str: 1 },
    finalScores: { ...baseScores, str: 13 },
    adjustScore: vi.fn(),
    assignStandard: vi.fn(),
    standardAssigned: {},
    multiReqs: {},
    multiReqMet: false,
    multiclassEnKey: '',
    classEnKey: 'Fighter',
    ...overrides,
  }
}

describe('CharacterCreateStepAbilities', () => {
  it('projects point-buy progress state and preserves score adjustment callbacks', () => {
    const ctx = makeCtx({ pointsLeft: 0 })
    render(<CharacterCreateStepAbilities ctx={ctx} />)

    const pointsBar = screen.getByText('剩余点数').closest('.points-bar')
    expect(pointsBar).toHaveAttribute('data-complete', 'true')
    expect(pointsBar).toHaveStyle({ '--ability-points-fill-width': '100%' })
    expect(within(pointsBar).getByText('0')).toHaveClass('points-big')
    expect(within(pointsBar).getByText('✓ 已分配完毕')).toHaveClass('label')
    expect(pointsBar.querySelector('.fill')).toHaveClass('fill')

    const strengthPlaque = screen.getByText('STR').closest('.ability-plaque')
    expect(strengthPlaque).toHaveTextContent('基础 12')
    fireEvent.click(within(strengthPlaque).getByRole('button', { name: '−' }))
    expect(ctx.adjustScore).toHaveBeenCalledWith('str', -1)
  })

  it('projects in-progress point-buy fill and enables valid score increases', () => {
    const ctx = makeCtx()
    render(<CharacterCreateStepAbilities ctx={ctx} />)

    const pointsBar = screen.getByText('剩余点数').closest('.points-bar')
    expect(pointsBar).toHaveAttribute('data-complete', 'false')
    expect(pointsBar).toHaveStyle({ '--ability-points-fill-width': '92.5925925925926%' })

    const strengthPlaque = screen.getByText('STR').closest('.ability-plaque')
    fireEvent.click(within(strengthPlaque).getByRole('button', { name: '+' }))
    expect(ctx.adjustScore).toHaveBeenCalledWith('str', 1)
  })

  it('renders multiclass requirements with stable met and unmet state', () => {
    render(
      <CharacterCreateStepAbilities
        ctx={makeCtx({
          form: {
            char_class: 'Fighter',
            level: 1,
            multiclassEnabled: true,
            multiclass_class: 'Rogue',
          },
          finalScores: {
            str: 12,
            dex: 14,
            con: 13,
            int: 10,
            wis: 10,
            cha: 8,
          },
          multiReqs: { dex: 13, cha: 13 },
          multiReqMet: false,
          multiclassEnKey: 'Rogue',
        })}
      />,
    )

    const requirements = document.querySelector('.ability-multiclass-requirements')
    expect(requirements).toHaveAttribute('data-met', 'false')
    expect(requirements.querySelector('.ability-multiclass-title')).toHaveTextContent('游荡者')

    const requirementRows = requirements.querySelectorAll('.ability-multiclass-requirement')
    expect(requirementRows).toHaveLength(2)
    expect(requirementRows[0]).toHaveAttribute('data-met', 'true')
    expect(requirementRows[0]).toHaveTextContent('敏捷>=13')
    expect(requirementRows[1]).toHaveAttribute('data-met', 'false')
    expect(requirementRows[1]).toHaveTextContent('魅力>=13')
  })
})
