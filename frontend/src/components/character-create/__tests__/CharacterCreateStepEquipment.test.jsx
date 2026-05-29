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
})
