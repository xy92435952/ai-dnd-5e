import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useCharacterCreateState } from '../useCharacterCreateState'

describe('useCharacterCreateState', () => {
  it('keeps CharacterCreate page state and helpers in one hook', () => {
    const { result } = renderHook(() => useCharacterCreateState({
      initialPointsLeft: 27,
      skillLimit: 2,
      cantripLimit: 1,
      spellLimit: 2,
    }))

    expect(result.current.form.level).toBe(1)
    expect(result.current.scoreMethod).toBe('pointbuy')
    expect(result.current.scores.str).toBe(8)
    expect(result.current.modal).toEqual({ type: '', itemKey: '' })
    expect(result.current.narrative.personality).toBe('')

    act(() => result.current.openModal('race', '人类'))
    expect(result.current.modal).toEqual({ type: 'race', itemKey: '人类' })

    act(() => result.current.closeModal())
    expect(result.current.modal).toEqual({ type: '', itemKey: '' })

    act(() => result.current.adjustScore('str', 1))
    expect(result.current.scores.str).toBe(9)

    act(() => result.current.assignStandard('str', 0))
    act(() => result.current.assignStandard('dex', 0))
    expect(result.current.standardAssigned).toEqual({ str: 0 })

    act(() => result.current.toggleSkill('运动'))
    act(() => result.current.toggleSkill('察觉'))
    act(() => result.current.toggleSkill('洞察'))
    expect(result.current.chosenSkills).toEqual(['运动', '察觉'])

    act(() => result.current.toggleCantrip('光亮术'))
    act(() => result.current.toggleCantrip('法师之手'))
    expect(result.current.chosenCantrips).toEqual(['光亮术'])

    act(() => result.current.toggleSpell('护盾术'))
    act(() => result.current.toggleSpell('魔法飞弹'))
    act(() => result.current.toggleSpell('睡眠术'))
    expect(result.current.chosenSpells).toEqual(['护盾术', '魔法飞弹'])
  })

  it('resets class-dependent choices when the class changes', () => {
    const { result } = renderHook(() => useCharacterCreateState({
      initialPointsLeft: 27,
      skillLimit: 2,
      cantripLimit: 2,
      spellLimit: 2,
    }))

    act(() => {
      result.current.toggleSkill('运动')
      result.current.toggleCantrip('光亮术')
      result.current.toggleSpell('护盾术')
      result.current.setForm((form) => ({
        ...form,
        char_class: '法师',
        subclass: '防护学派',
      }))
    })

    expect(result.current.chosenSkills).toEqual([])
    expect(result.current.chosenCantrips).toEqual([])
    expect(result.current.chosenSpells).toEqual([])
    expect(result.current.form.subclass).toBe('')
  })
})
