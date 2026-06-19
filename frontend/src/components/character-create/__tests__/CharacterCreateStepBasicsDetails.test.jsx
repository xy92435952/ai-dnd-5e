import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CharacterCreateStepBasicsDetails from '../CharacterCreateStepBasicsDetails'

function makeCtx(overrides = {}) {
  return {
    form: {
      level: 3,
      alignment: '中立善良',
      background: 'Sage',
      race: 'Human',
    },
    setForm: vi.fn(),
    module: {
      level_min: 1,
      level_max: 5,
    },
    options: {
      alignments: ['守序善良', '中立善良'],
      backgrounds: ['Sage', 'Soldier'],
      background_features: {
        Sage: {
          feature: '研究者',
          feature_desc: '你知道在哪里寻找知识。',
          skills: ['奥秘', '历史'],
          tools: ['书法工具'],
          languages: 1,
        },
      },
      racial_languages: {
        Human: { fixed: ['Common'], bonus: 0 },
      },
      all_languages: ['Common', 'Elvish', 'Dwarvish'],
    },
    narrative: {
      personality: '',
      backstory: '',
      speech_style: '',
      combat_preference: '',
      catchphrase: '',
    },
    setNarrative: vi.fn(),
    openModal: vi.fn(),
    bonusLanguages: [],
    setBonusLanguages: vi.fn(),
    ...overrides,
  }
}

describe('CharacterCreateStepBasicsDetails', () => {
  it('projects level controls through stable classes and preserves the level updater', () => {
    const ctx = makeCtx()
    const { container } = render(<CharacterCreateStepBasicsDetails ctx={ctx} />)

    const topGrid = container.querySelector('.create-details-top-grid')
    expect(topGrid).toBeInTheDocument()

    const levelRow = container.querySelector('.create-details-level-row')
    expect(levelRow).toBeInTheDocument()

    const slider = container.querySelector('.create-details-level-slider')
    expect(slider).toHaveAttribute('type', 'range')
    expect(slider).toHaveValue('3')

    const levelValue = container.querySelector('.create-details-level-value')
    expect(levelValue).toHaveTextContent('3')

    const rangeNote = container.querySelector('.create-details-level-range')
    expect(rangeNote).toHaveAttribute('data-in-range', 'true')
    expect(rangeNote).toHaveTextContent('推荐范围 1--5')

    fireEvent.change(slider, { target: { value: '7' } })
    const updater = ctx.setForm.mock.calls[0][0]
    expect(updater({ level: 3, keep: true })).toEqual({ level: 7, keep: true })
  })

  it('marks out-of-range levels and preserves alignment/background callbacks', () => {
    const ctx = makeCtx({
      form: {
        level: 7,
        alignment: '',
        background: 'Sage',
        race: 'Human',
      },
    })
    const { container } = render(<CharacterCreateStepBasicsDetails ctx={ctx} />)

    expect(container.querySelector('.create-details-level-range')).toHaveAttribute('data-in-range', 'false')
    expect(container.querySelector('.create-details-level-range')).toHaveTextContent('推荐 Lv1--5')

    const alignmentSelect = screen.getByDisplayValue('选择阵营')
    fireEvent.change(alignmentSelect, { target: { value: '守序善良' } })
    const alignmentUpdater = ctx.setForm.mock.calls[0][0]
    expect(alignmentUpdater({ alignment: '', keep: true })).toEqual({ alignment: '守序善良', keep: true })

    const backgroundRow = container.querySelector('.create-details-background-row')
    expect(backgroundRow).toBeInTheDocument()

    const backgroundSelect = within(backgroundRow).getByDisplayValue('Sage')
    fireEvent.change(backgroundSelect, { target: { value: 'Soldier' } })
    const backgroundUpdater = ctx.setForm.mock.calls[1][0]
    expect(backgroundUpdater({ background: 'Sage', keep: true })).toEqual({ background: 'Soldier', keep: true })

    const backgroundInfo = within(backgroundRow).getByRole('button')
    fireEvent.click(backgroundInfo)
    expect(ctx.openModal).toHaveBeenCalledWith('background', 'Sage')
  })
})
