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

    expect(screen.getByRole('list', { name: '可选行动' })).toBeInTheDocument()
    const choice = screen.getByRole('button', { name: /撬开铁门/ })
    const preview = within(choice).getByLabelText('技能检定预览')

    expect(choice).toHaveAttribute('aria-describedby', 'dialogue-choice-1-preview')
    expect(choice).toHaveAttribute('title', '运动 · DC 12 · 中风险 · 70%')
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
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

  it('renders visible intent badges for different choice types', () => {
    render(
      <DialogueChoices
        choices={[
          '向陌生人点头致意',
          { text: '询问酒馆老板', action_type: 'dialogue', tags: [] },
          { text: '进入东侧走廊', choice_type: 'movement', tags: [] },
          { text: '检查墙上的符文', choice_type: 'investigation', tags: [] },
          { text: '扎营休息', choice_type: 'rest', tags: [] },
          { text: '回忆古老传说', choice_type: 'lore', tags: [] },
          { text: '拔剑威胁守卫', action: true, tags: [] },
        ]}
        player={makePlayer()}
        setPendingCheck={vi.fn()}
        onAction={vi.fn()}
        disabled={false}
      />,
    )

    expect(screen.getByRole('button', { name: /向陌生人点头致意/ })).toHaveClass('choice-intent-roleplay')
    expect(screen.getByText('扮演')).toHaveClass('choice-intent-badge', 'roleplay')
    expect(screen.getByRole('button', { name: /询问酒馆老板/ })).toHaveClass('choice-intent-dialogue')
    expect(screen.getByText('对话')).toHaveClass('choice-intent-badge', 'dialogue')
    expect(screen.getByRole('button', { name: /进入东侧走廊/ })).toHaveClass('choice-intent-movement')
    expect(screen.getByText('移动')).toHaveClass('choice-intent-badge', 'movement')
    expect(screen.getByRole('button', { name: /检查墙上的符文/ })).toHaveClass('choice-intent-investigation')
    expect(screen.getByText('调查')).toHaveClass('choice-intent-badge', 'investigation')
    expect(screen.getByRole('button', { name: /扎营休息/ })).toHaveClass('choice-intent-rest')
    expect(screen.getByText('休整')).toHaveClass('choice-intent-badge', 'rest')
    expect(screen.getByRole('button', { name: /回忆古老传说/ })).toHaveClass('choice-intent-lore')
    expect(screen.getByText('知识')).toHaveClass('choice-intent-badge', 'lore')
    expect(screen.getByRole('button', { name: /拔剑威胁守卫/ })).toHaveClass('choice-intent-danger')
    expect(screen.getByText('危险')).toHaveClass('choice-intent-badge', 'danger')
  })

  it('surfaces location-exit metadata on movement choices', () => {
    render(
      <DialogueChoices
        choices={[{
          text: '穿过青铜门进入军械库',
          location_exit: {
            target_location_id: 'armory',
            target_location_name: '军械库',
            route_type: 'locked',
            locked: true,
            one_way: true,
            requires_key: '青铜钥匙',
            check_type: 'thieves_tools',
            dc: 15,
          },
          tags: [{ label: 'Exit', kind: 'location_exit' }],
        }]}
        player={makePlayer()}
        setPendingCheck={vi.fn()}
        onAction={vi.fn()}
        disabled={false}
      />,
    )

    const choice = screen.getByRole('button', { name: /穿过青铜门/ })
    expect(choice).toHaveClass('choice-intent-movement')
    expect(choice).toHaveAttribute('aria-describedby', 'dialogue-choice-1-exit')
    expect(within(choice).getByText('移动')).toHaveClass('choice-intent-badge', 'movement')

    const exit = within(choice).getByLabelText('地图出口')
    expect(within(exit).getByText('出口')).toBeInTheDocument()
    expect(within(exit).getByText('军械库')).toBeInTheDocument()
    expect(within(exit).getByText('锁定')).toBeInTheDocument()
    expect(within(exit).getByText('单向')).toBeInTheDocument()
    expect(within(exit).getByText('钥匙: 青铜钥匙')).toBeInTheDocument()
    expect(within(exit).getByText('thieves_tools DC 15')).toBeInTheDocument()
  })
})
