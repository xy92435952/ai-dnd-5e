import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import DialogueChoices from '../DialogueChoices'

function makePlayer() {
  return {
    id: 'player-1',
    derived: {
      proficiency_bonus: 2,
      ability_modifiers: { str: 3, dex: 2, con: 1, int: 0, wis: 1, cha: -1 },
    },
    proficient_skills: ['运动'],
  }
}

describe('DialogueChoices', () => {
  it('shows skill, ability, DC, and risk before clicking a skill-check choice', () => {
    const setPendingCheck = vi.fn()
    const onAction = vi.fn()

    render(
      <DialogueChoices
        choices={[{
          text: '撬开铁门',
          skill_check: true,
          tags: [{ kind: 'athletic', label: '运动', dc: 12 }],
        }]}
        player={makePlayer()}
        setPendingCheck={setPendingCheck}
        onAction={onAction}
        disabled={false}
      />,
    )

    const choice = screen.getByRole('button', { name: /撬开铁门/ })
    const preview = within(choice).getByLabelText('技能检定预览')

    expect(within(preview).getByText('技能')).toBeInTheDocument()
    expect(within(preview).getByText('运动')).toBeInTheDocument()
    expect(within(preview).getByText('属性')).toBeInTheDocument()
    expect(within(preview).getByText('STR')).toBeInTheDocument()
    expect(within(preview).getByText('难度')).toBeInTheDocument()
    expect(within(preview).getByText((_, node) => node?.textContent === 'DC 12')).toBeInTheDocument()
    expect(within(preview).getByText('风险')).toBeInTheDocument()
    expect(within(preview).getByText('中风险 · 70%').closest('.choice-check-pill')).toHaveClass('risk', 'medium')

    fireEvent.click(choice)

    expect(setPendingCheck).toHaveBeenCalledWith({
      check_type: '运动',
      dc: 12,
      character_id: 'player-1',
      context: '撬开铁门',
    })
    expect(onAction).not.toHaveBeenCalled()
  })

  it('supports top-level check metadata in the click path', () => {
    const setPendingCheck = vi.fn()

    render(
      <DialogueChoices
        choices={[{
          text: '辨认符文',
          skill_check: true,
          check_type: '奥秘',
          dc: 15,
        }]}
        player={makePlayer()}
        setPendingCheck={setPendingCheck}
        onAction={vi.fn()}
        disabled={false}
      />,
    )

    const choice = screen.getByRole('button', { name: /辨认符文/ })
    const preview = within(choice).getByLabelText('技能检定预览')

    expect(within(preview).getByText('奥秘')).toBeInTheDocument()
    expect(within(preview).getByText('INT')).toBeInTheDocument()
    expect(within(preview).getByText('高风险 · 30%').closest('.choice-check-pill')).toHaveClass('risk', 'high')

    fireEvent.click(choice)

    expect(setPendingCheck).toHaveBeenCalledWith({
      check_type: '奥秘',
      dc: 15,
      character_id: 'player-1',
      context: '辨认符文',
    })
  })
})
