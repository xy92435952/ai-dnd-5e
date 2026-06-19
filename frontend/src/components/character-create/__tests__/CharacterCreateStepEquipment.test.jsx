import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CharacterCreateStepEquipment from '../CharacterCreateStepEquipment'

function makeCtx(overrides = {}) {
  return {
    form: { background: '', race: '' },
    classEnKey: 'Fighter',
    options: {
      starting_equipment: {
        Fighter: [
          {
            label: '重甲战士',
            items: [
              { slot: 'armor', name: 'Chain Mail' },
              { slot: 'weapon', name: 'Longsword' },
              { slot: 'gear', name: "Explorer's Pack" },
            ],
          },
          {
            label: '轻装弓手',
            items: [
              { slot: 'armor', name: 'Leather' },
              { slot: 'weapon', name: 'Longbow' },
              { slot: 'gear', name: "Explorer's Pack" },
            ],
          },
        ],
      },
      starting_gear_packs: {
        "Explorer's Pack": [
          { name: 'Backpack', zh: '背包', quantity: 1 },
          { name: 'Torch', zh: '火把', quantity: 10 },
          { name: 'Rations (1 day)', zh: '干粮(1天)', quantity: 10 },
        ],
      },
      background_features: {},
      background_equipment: {},
      racial_languages: {},
      all_languages: [],
      weapons: {
        Longsword: { zh: '长剑' },
        Longbow: { zh: '长弓' },
      },
      armor: {
        'Chain Mail': { zh: '锁甲' },
        Leather: { zh: '皮甲' },
      },
    },
    equipChoice: 0,
    setEquipChoice: vi.fn(),
    getItemZh: name => ({
      "Explorer's Pack": '探险者背包',
      Longsword: '长剑',
      Longbow: '长弓',
      'Chain Mail': '锁甲',
      Leather: '皮甲',
    }[name] || name),
    bonusLanguages: [],
    setBonusLanguages: vi.fn(),
    ...overrides,
  }
}

describe('CharacterCreateStepEquipment', () => {
  it('previews expanded pack contents for starting equipment choices', () => {
    render(<CharacterCreateStepEquipment ctx={makeCtx()} />)

    const selectedCard = screen.getByText('重甲战士').closest('.equip-card')
    expect(selectedCard).toHaveClass('sel')
    expect(within(selectedCard).getByText('◇ 探险者背包')).toBeInTheDocument()
    expect(within(selectedCard).getByLabelText('探险者背包内容')).toHaveTextContent('背包')
    expect(within(selectedCard).getByLabelText('探险者背包内容')).toHaveTextContent('火把 ×10')
    expect(within(selectedCard).getByLabelText('探险者背包内容')).toHaveTextContent('干粮(1天) ×10')
  })

  it('selects another equipment card through the existing equipment_choice flow', () => {
    const ctx = makeCtx()
    render(<CharacterCreateStepEquipment ctx={ctx} />)

    fireEvent.click(screen.getByText('轻装弓手').closest('.equip-card'))

    expect(ctx.setEquipChoice).toHaveBeenCalledWith(1)
  })

  it('previews background starting gear and gold when a background is selected', () => {
    render(<CharacterCreateStepEquipment ctx={makeCtx({
      form: { background: '士兵', race: '' },
      options: {
        ...makeCtx().options,
        background_features: {
          士兵: {
            feature: '军衔',
            feature_desc: '军事组织承认你的军衔。',
            skills: ['运动', '威吓'],
            tools: ['赌具'],
            languages: 0,
          },
        },
        background_equipment: {
          士兵: {
            gold: 10,
            items: [
              { name: 'Insignia of Rank', zh: '军衔徽记', quantity: 1 },
              { name: 'Gaming Set', zh: '赌具', quantity: 1 },
            ],
          },
        },
      },
    })} />)

    const backgroundGear = screen.getByLabelText('背景起始物品')
    expect(backgroundGear).toHaveTextContent('金币 +10 gp')
    expect(backgroundGear).toHaveTextContent('军衔徽记')
    expect(backgroundGear).toHaveTextContent('赌具')
  })

  it('renders bonus language choices with stable equipment-language chrome', () => {
    const setBonusLanguages = vi.fn(updater => updater(['Elvish']))
    render(<CharacterCreateStepEquipment ctx={makeCtx({
      form: { background: 'Sage', race: 'Half-Elf' },
      options: {
        ...makeCtx().options,
        background_features: {
          Sage: { languages: 1 },
        },
        racial_languages: {
          'Half-Elf': { fixed: ['Common'], bonus: 1 },
        },
        all_languages: ['Common', 'Elvish', 'Dwarvish', 'Draconic'],
      },
      bonusLanguages: ['Elvish'],
      setBonusLanguages,
    })} />)

    const section = screen.getByRole('region', { name: 'Bonus language choices' })
    expect(section).toHaveClass('equipment-language-section')
    expect(section.querySelector('.equipment-language-title')).toHaveAttribute('data-complete', 'false')
    expect(section.querySelector('.equipment-language-fixed')).toHaveTextContent('Common')

    const list = within(section).getByRole('list', { name: 'Available bonus languages' })
    expect(list).toHaveClass('equipment-language-options')
    const option = within(list).getAllByRole('listitem')[0]
    expect(option).toHaveClass('equipment-language-option')
    const dwarvish = within(option).getByRole('button', { name: 'Dwarvish' })
    expect(dwarvish).toHaveClass('skill-btn', 'equipment-language-button')
    expect(dwarvish).toHaveAttribute('data-selected', 'false')

    fireEvent.click(dwarvish)

    expect(setBonusLanguages).toHaveBeenCalledTimes(1)
    expect(setBonusLanguages.mock.results[0].value).toEqual(['Elvish', 'Dwarvish'])
  })
})
