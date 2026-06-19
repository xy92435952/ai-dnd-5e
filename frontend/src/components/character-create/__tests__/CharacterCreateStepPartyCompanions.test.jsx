import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CharacterCreateStepPartyCompanions from '../CharacterCreateStepPartyCompanions'

function makeCompanion(overrides = {}) {
  return {
    id: 'companion-1',
    name: 'Mara',
    race: 'Elf',
    char_class: 'Wizard',
    level: 4,
    personality: '谨慎、爱记笔记，遇事先观察再出手。',
    speech_style: '语速平稳，常用短句。',
    combat_preference: '保持距离，优先控制与爆发。',
    catchphrase: '先别急，让我看一眼局势。',
    backstory: '曾在古代图书馆做过抄录员，因此对遗迹格外敏感。',
    hp_current: 18,
    hp_max: 24,
    ac: 15,
    ability_scores: {
      str: 8,
      dex: 14,
      con: 12,
      int: 18,
      wis: 13,
      cha: 10,
    },
    derived: {
      hp_max: 24,
      ac: 15,
      speed: 30,
      proficiency_bonus: 3,
    },
    proficient_skills: ['Arcana', 'History'],
    cantrips: ['Mage Hand', 'Fire Bolt'],
    known_spells: ['Shield'],
    prepared_spells: ['Detect Magic'],
    equipment: {
      weapon: [{ name: 'Quarterstaff' }],
      gear: [{ zh: '法术书' }, 'Spellbook'],
    },
    ...overrides,
  }
}

describe('CharacterCreateStepPartyCompanions', () => {
  it('restores an expandable detail panel for each generated companion', () => {
    render(
      <CharacterCreateStepPartyCompanions
        companions={[makeCompanion()]}
        generatingParty={false}
        handleGenerateParty={vi.fn()}
        error=""
      />,
    )

    const details = screen.getByLabelText('Mara 明细')
    expect(details).not.toHaveAttribute('open')
    const roleLine = document.querySelector('.cc-role-clamp')
    expect(roleLine).toHaveClass('cc-role', 'cc-role-clamp')
    expect(roleLine).toHaveTextContent('谨慎、爱记笔记，遇事先观察再出手。')
    expect(screen.getByRole('button', { name: /重新生成队伍/ })).toHaveClass(
      'companions-regenerate-button',
    )

    const summary = within(details).getByText('展开明细')
    fireEvent.click(summary)

    expect(details).toHaveAttribute('open')
    expect(within(details).getByText('战斗数据')).toBeInTheDocument()
    expect(within(details).getByText('HP 18/24、AC 15、速度 30、熟练 +3')).toBeInTheDocument()
    expect(within(details).getByText('属性')).toBeInTheDocument()
    expect(within(details).getByText('力量 8、敏捷 14、体质 12、智力 18、感知 13、魅力 10')).toBeInTheDocument()
    expect(within(details).getByText('技能')).toBeInTheDocument()
    expect(within(details).getByText('Arcana、History')).toBeInTheDocument()
    expect(within(details).getByText('法术')).toBeInTheDocument()
    expect(within(details).getByText('Mage Hand、Fire Bolt、Detect Magic、Shield')).toBeInTheDocument()
    expect(within(details).getByText('装备')).toBeInTheDocument()
    expect(within(details).getByText('武器: Quarterstaff、物品: 法术书、物品: Spellbook')).toBeInTheDocument()
    expect(within(details).getByText('性格')).toBeInTheDocument()
    expect(within(details).getByText('谨慎、爱记笔记，遇事先观察再出手。')).toBeInTheDocument()
    expect(within(details).getByText('说话风格')).toBeInTheDocument()
    expect(within(details).getByText('战斗偏好')).toBeInTheDocument()
    expect(within(details).getByText('口头禅')).toBeInTheDocument()
    expect(within(details).getByText('背景')).toBeInTheDocument()
  })

  it('renders generating and error states with stable companion chrome', () => {
    const handleGenerateParty = vi.fn()
    const { rerender } = render(
      <CharacterCreateStepPartyCompanions
        companions={[]}
        generatingParty
        handleGenerateParty={handleGenerateParty}
        error=""
      />,
    )

    const status = screen.getByRole('status')
    expect(status).toHaveClass('companions-generating')
    expect(within(status).getByText(/AI/)).toHaveClass('companions-generating-title')
    expect(within(status).getByText('根据你的职业分析队伍需求')).toHaveClass(
      'companions-generating-copy',
    )

    rerender(
      <CharacterCreateStepPartyCompanions
        companions={[makeCompanion()]}
        generatingParty={false}
        handleGenerateParty={handleGenerateParty}
        error="队伍生成失败"
      />,
    )

    const retry = screen.getByRole('button', { name: /重新生成队伍/ })
    expect(retry.closest('.companions-regenerate-row')).toBeInTheDocument()
    fireEvent.click(retry)
    expect(handleGenerateParty).toHaveBeenCalledTimes(1)

    const alert = screen.getByRole('alert')
    expect(alert).toHaveClass('companions-error')
    expect(alert).toHaveTextContent('队伍生成失败')
  })
})
