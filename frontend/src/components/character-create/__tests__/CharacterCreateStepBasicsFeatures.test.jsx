import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CharacterCreateStepBasicsFeatures from '../CharacterCreateStepBasicsFeatures'

function makeCtx(overrides = {}) {
  return {
    form: {
      char_class: 'Fighter',
      level: 3,
      subclass: '',
      multiclassEnabled: false,
      multiclass_class: '',
      multiclass_level: 1,
    },
    setForm: vi.fn(),
    classEnKey: 'Fighter',
    classInfo: {
      subclass_label: 'Martial Archetype',
      subclass_unlock: 3,
    },
    showSubclass: false,
    subclassOptions: [],
    hasFightingStyle: false,
    multiReqs: {},
    multiReqMet: false,
    finalScores: {
      str: 13,
      dex: 14,
      con: 12,
      int: 10,
      wis: 10,
      cha: 8,
    },
    multiclassEnKey: '',
    options: {
      classes: ['Fighter', 'Rogue', 'Wizard'],
      fighting_style_classes: {},
      fighting_styles: {},
    },
    openModal: vi.fn(),
    fightingStyle: '',
    setFightingStyle: vi.fn(),
    ...overrides,
  }
}

describe('CharacterCreateStepBasicsFeatures', () => {
  it('renders the multiclass toggle and preserves the enable callback', () => {
    const ctx = makeCtx()
    render(<CharacterCreateStepBasicsFeatures ctx={ctx} />)

    const toggle = screen.getByText('启用双职业').closest('.create-multiclass-toggle')
    expect(toggle).toHaveAttribute('data-enabled', 'false')
    expect(toggle.querySelector('.create-multiclass-checkbox')).toBeInTheDocument()
    expect(within(toggle).getByText('启用双职业')).toHaveClass('create-multiclass-label')
    expect(within(toggle).getByText('（可选）')).toHaveClass('create-multiclass-optional')

    fireEvent.click(toggle)

    const updater = ctx.setForm.mock.calls[0][0]
    expect(updater({ multiclassEnabled: false })).toEqual({ multiclassEnabled: true })
  })

  it('renders enabled multiclass fields, empty guidance, and class modal handoff', () => {
    const ctx = makeCtx({
      form: {
        char_class: 'Fighter',
        level: 3,
        subclass: '',
        multiclassEnabled: true,
        multiclass_class: '',
        multiclass_level: 1,
      },
      multiclassEnKey: 'Rogue',
    })
    render(<CharacterCreateStepBasicsFeatures ctx={ctx} />)

    const toggle = screen.getByText('启用双职业').closest('.create-multiclass-toggle')
    expect(toggle).toHaveAttribute('data-enabled', 'true')

    const panel = document.querySelector('.create-multiclass-panel')
    expect(panel).toBeInTheDocument()
    expect(panel.querySelector('.create-multiclass-fields')).toBeInTheDocument()
    expect(panel.querySelector('.create-multiclass-class-row')).toBeInTheDocument()
    expect(panel.querySelector('.create-multiclass-empty')).toHaveTextContent(
      '选择第二职业后将显示入门属性要求',
    )

    const select = within(panel).getByDisplayValue('选择职业')
    expect(select).toHaveClass('create-multiclass-select')
    expect(select).toHaveAttribute('data-selected', 'false')
    fireEvent.change(select, { target: { value: 'Rogue' } })
    expect(ctx.setForm).toHaveBeenCalledTimes(1)

    const levelInput = within(panel).getByDisplayValue('1')
    expect(levelInput).toHaveClass('create-multiclass-level-input')
    fireEvent.change(levelInput, { target: { value: '2' } })
    expect(ctx.setForm).toHaveBeenCalledTimes(2)

    fireEvent.click(within(panel).getByRole('button'))
    expect(ctx.openModal).toHaveBeenCalledWith('class', 'Rogue')
  })

  it('projects multiclass requirement status through stable metadata', () => {
    render(
      <CharacterCreateStepBasicsFeatures
        ctx={makeCtx({
          form: {
            char_class: 'Fighter',
            level: 3,
            subclass: '',
            multiclassEnabled: true,
            multiclass_class: 'Rogue',
            multiclass_level: 1,
          },
          multiReqs: { dex: 13, cha: 13 },
          multiReqMet: false,
          finalScores: {
            str: 13,
            dex: 14,
            con: 12,
            int: 10,
            wis: 10,
            cha: 8,
          },
          multiclassEnKey: 'Rogue',
        })}
      />,
    )

    const requirements = document.querySelector('.create-multiclass-requirements')
    expect(requirements).toHaveAttribute('data-met', 'false')
    expect(requirements.querySelector('.create-multiclass-requirements-title')).toHaveTextContent(
      '未满足',
    )

    const requirementRows = requirements.querySelectorAll('.create-multiclass-requirement')
    expect(requirementRows).toHaveLength(2)
    expect(requirementRows[0]).toHaveAttribute('data-met', 'true')
    expect(requirementRows[0]).toHaveTextContent('敏捷>=13')
    expect(requirementRows[1]).toHaveAttribute('data-met', 'false')
    expect(requirementRows[1]).toHaveTextContent('魅力>=13')
  })
})
