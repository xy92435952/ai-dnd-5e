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

  it('renders basics bonus language choices with stable state and cap-preserving updates', () => {
    const setBonusLanguages = vi.fn(updater => updater(['Elvish']))
    const ctx = makeCtx({
      form: {
        level: 3,
        alignment: '中立善良',
        background: 'Sage',
        race: 'Half-Elf',
      },
      options: {
        ...makeCtx().options,
        racial_languages: {
          'Half-Elf': { fixed: ['Common'], bonus: 1 },
        },
        all_languages: ['Common', 'Elvish', 'Dwarvish', 'Draconic'],
      },
      bonusLanguages: ['Elvish'],
      setBonusLanguages,
    })
    render(<CharacterCreateStepBasicsDetails ctx={ctx} />)

    const section = screen.getByRole('region', { name: 'Basics bonus language choices' })
    expect(section).toHaveClass('create-details-language-section')

    const title = section.querySelector('.create-details-language-title')
    expect(title).toHaveAttribute('data-complete', 'false')
    expect(title).toHaveTextContent('1/2')

    expect(section.querySelector('.create-details-language-fixed')).toHaveTextContent('Common')

    const list = within(section).getByRole('list', { name: 'Available basics bonus languages' })
    expect(list).toHaveClass('create-details-language-options')

    const options = within(list).getAllByRole('listitem')
    expect(options).toHaveLength(2)
    expect(options[0]).toHaveClass('create-details-language-option')

    const dwarvish = within(options[0]).getByRole('button', { name: 'Dwarvish' })
    expect(dwarvish).toHaveClass('skill-btn', 'create-details-language-button')
    expect(dwarvish).toHaveAttribute('data-selected', 'false')

    fireEvent.click(dwarvish)
    expect(setBonusLanguages).toHaveBeenCalledTimes(1)
    expect(setBonusLanguages.mock.results[0].value).toEqual(['Elvish', 'Dwarvish'])

    const capUpdater = setBonusLanguages.mock.calls[0][0]
    expect(capUpdater(['Elvish', 'Draconic'])).toEqual(['Elvish', 'Draconic'])
  })

  it('renders narrative notes with stable classes and preserves field updates', () => {
    const setNarrative = vi.fn()
    const ctx = makeCtx({
      narrative: {
        personality: '沉默寡言',
        backstory: '来自北地边境。',
        speech_style: '',
        combat_preference: '',
        catchphrase: '',
      },
      setNarrative,
    })
    const { container } = render(<CharacterCreateStepBasicsDetails ctx={ctx} />)

    const details = screen.getByLabelText('Character narrative notes')
    expect(details).toHaveClass('create-details-narrative')

    const summary = within(details).getByText('❖ 角色叙事 · 选填').closest('summary')
    expect(summary).toHaveClass('create-details-narrative-summary')
    expect(within(summary).getByText('❖ 角色叙事 · 选填')).toHaveClass('create-details-narrative-title')
    expect(within(summary).getByText(/DM 在你掉线时/)).toHaveClass('create-details-narrative-note')

    const body = container.querySelector('.create-details-narrative-body')
    expect(body).toBeInTheDocument()

    const fields = body.querySelectorAll('.create-details-narrative-field')
    expect(fields).toHaveLength(5)
    expect(fields[0].querySelector('.create-details-narrative-label')).toHaveTextContent('性格')
    expect(fields[0].querySelector('.create-details-narrative-hint')).toHaveTextContent('沉默寡言')

    const personality = within(fields[0]).getByDisplayValue('沉默寡言')
    expect(personality).toHaveClass('create-details-narrative-input', 'create-details-narrative-textarea')
    expect(personality).toHaveAttribute('maxLength', '200')

    fireEvent.change(personality, { target: { value: '谨慎而寡言' } })
    const personalityUpdater = setNarrative.mock.calls[0][0]
    expect(personalityUpdater({ personality: '沉默寡言', keep: true })).toEqual({
      personality: '谨慎而寡言',
      keep: true,
    })

    const catchphrase = fields[4].querySelector('input')
    expect(catchphrase).toHaveClass('create-details-narrative-input')
    expect(catchphrase).toHaveAttribute('maxLength', '120')

    fireEvent.change(catchphrase, { target: { value: '天黑前必须到达。' } })
    const catchphraseUpdater = setNarrative.mock.calls[1][0]
    expect(catchphraseUpdater({ catchphrase: '', keep: true })).toEqual({
      catchphrase: '天黑前必须到达。',
      keep: true,
    })
  })
})
