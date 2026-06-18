import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import DialogueResponseBox from '../DialogueResponseBox'

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

function renderResponseBox(props = {}) {
  const setPendingCheck = vi.fn()
  const setInput = vi.fn()
  const onAction = vi.fn()
  const onDiceRoll = vi.fn()
  const onExplorationReaction = vi.fn()
  const focus = vi.fn()
  render(
    <DialogueResponseBox
      pendingCheck={null}
      pendingExplorationReaction={null}
      checkRolling={false}
      onDiceRoll={onDiceRoll}
      onExplorationReaction={onExplorationReaction}
      choices={[
        { text: '观察石门', choice_type: 'investigation', tags: [] },
        {
          text: '撬开铁门',
          skill_check: true,
          tags: [{ kind: 'athletic', label: '运动', dc: 12 }],
        },
      ]}
      player={makePlayer()}
      setPendingCheck={setPendingCheck}
      onAction={onAction}
      input="我查看地面"
      setInput={setInput}
      inputRef={{ current: { focus } }}
      isLoading={false}
      room={null}
      isMySpeakTurn={true}
      multiplayerSyncBlocked={false}
      {...props}
    />,
  )
  return { setPendingCheck, setInput, onAction, onDiceRoll, onExplorationReaction, focus }
}

describe('DialogueResponseBox', () => {
  it('wraps choices, recovery shortcuts, and free speak in a named response region', () => {
    const { setPendingCheck, setInput, onAction } = renderResponseBox()

    const response = screen.getByRole('region', { name: '玩家回应' })
    expect(response).toHaveClass('dialogue-response-box')
    expect(within(response).getByText('你的回应').closest('.dialogue-response-header')).toHaveAttribute('aria-live', 'polite')
    expect(within(response).getByText('1–2 快捷键')).toHaveClass('dialogue-response-shortcuts')
    expect(within(response).getByRole('list', { name: '可选行动' })).toBeInTheDocument()
    expect(within(response).getByRole('group', { name: '回应快捷入口' })).toBeInTheDocument()
    expect(within(response).getByRole('group', { name: '自由行动输入' })).toBeInTheDocument()

    fireEvent.click(within(response).getByRole('button', { name: /观察石门/ }))
    expect(onAction).toHaveBeenCalledWith('观察石门', { actionSource: 'ai_generated_choice' })

    fireEvent.click(within(response).getByRole('button', { name: /撬开铁门/ }))
    expect(setPendingCheck).toHaveBeenCalledWith({
      check_type: '运动',
      dc: 12,
      character_id: 'player-1',
      context: '撬开铁门',
    })

    fireEvent.click(within(response).getByRole('button', { name: '提问：填入询问前缀' }))
    expect(setInput).toHaveBeenCalledWith('我想询问：我查看地面')
    expect(within(response).getByLabelText('✎ 自由行动')).toHaveFocus()
  })

  it('omits the shortcut hint when no choices are visible', () => {
    renderResponseBox({ choices: [] })

    const response = screen.getByRole('region', { name: '玩家回应' })
    expect(within(response).queryByText(/快捷键/)).not.toBeInTheDocument()
    expect(within(response).queryByRole('list', { name: '可选行动' })).not.toBeInTheDocument()
  })

  it('propagates loading and multiplayer sync disables to response controls', () => {
    renderResponseBox({
      room: { code: 'ABCD' },
      isMySpeakTurn: true,
      multiplayerSyncBlocked: true,
    })

    const response = screen.getByRole('region', { name: '玩家回应' })
    expect(within(response).getByRole('button', { name: /观察石门/ })).toBeDisabled()
    expect(within(response).getByRole('button', { name: '继续推进当前场景' })).toBeDisabled()
    expect(within(response).getByLabelText('✎ 自由行动')).toBeDisabled()
    expect(within(response).getByText('你的回应').closest('.dialogue-response-header')).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByText('房间正在重新同步，恢复后可继续发言。')).toHaveClass('free-speak-status')
  })
})
