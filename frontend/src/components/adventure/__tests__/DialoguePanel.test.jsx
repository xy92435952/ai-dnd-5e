import { describe, expect, it, vi } from 'vitest'
import { createRef } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import DialoguePanel from '../DialoguePanel'

function makePlayer() {
  return {
    id: 'player-1',
    hp_current: 12,
    hp_max: 12,
    derived: {
      proficiency_bonus: 2,
      ability_modifiers: { str: 3, dex: 2, con: 1, int: 0, wis: 1, cha: -1 },
    },
    proficient_skills: ['运动'],
  }
}

function renderPanel(props = {}) {
  const onAdvanceDialogue = vi.fn()
  const setPendingCheck = vi.fn()
  const onAction = vi.fn()
  const setInput = vi.fn()
  const onDiceRoll = vi.fn()
  const onExplorationReaction = vi.fn()
  const logsEndRef = createRef()

  render(
    <DialoguePanel
      dialogueMode="chat"
      dialogueQueue={[{
        role: 'dm',
        speaker: 'DM',
        text: '矿道深处传来回声。',
        companionReactions: [],
      }]}
      dialogueIdx={0}
      typingText="矿道深处传来回声。"
      typingDone
      onAdvanceDialogue={onAdvanceDialogue}
      logs={[
        { id: 'dm-1', role: 'dm', content: '钟声从矿道深处传来。' },
        { id: 'player-1', role: 'player', content: '我举起火把。' },
      ]}
      logsEndRef={logsEndRef}
      pendingCheck={null}
      pendingExplorationReaction={null}
      checkRolling={false}
      onDiceRoll={onDiceRoll}
      onExplorationReaction={onExplorationReaction}
      choices={[{ text: '观察石门', choice_type: 'investigation', tags: [] }]}
      player={makePlayer()}
      setPendingCheck={setPendingCheck}
      onAction={onAction}
      input="我查看地面"
      setInput={setInput}
      inputRef={{ current: null }}
      isLoading={false}
      room={null}
      isMySpeakTurn
      multiplayerSyncBlocked={false}
      {...props}
    />,
  )

  return { onAdvanceDialogue, setPendingCheck, onAction, setInput, onDiceRoll, onExplorationReaction, logsEndRef }
}

describe('DialoguePanel', () => {
  it('renders chat logs and the response composer inside a named dialogue panel', () => {
    const { onAction, logsEndRef } = renderPanel()

    const panel = screen.getByRole('region', { name: '冒险对话面板' })
    expect(panel).toHaveClass('adventure-dialogue-panel')

    const log = within(panel).getByRole('log', { name: '冒险对话日志' })
    expect(within(log).getByText('钟声从矿道深处传来。')).toBeInTheDocument()
    expect(logsEndRef.current).toHaveClass('dialogue-log-end')

    const response = within(panel).getByRole('region', { name: '玩家回应' })
    expect(response.closest('.dialogue-response-shell')).toHaveClass('dialogue-response-shell')
    fireEvent.click(within(response).getByRole('button', { name: /观察石门/ }))
    expect(onAction).toHaveBeenCalledWith('观察石门', { actionSource: 'ai_generated_choice' })
  })

  it('shows theatre playback and hides the response shell during stage mode', () => {
    const { onAdvanceDialogue } = renderPanel({ dialogueMode: 'stage' })

    const panel = screen.getByRole('region', { name: '冒险对话面板' })
    const stage = within(panel).getByRole('button', { name: 'DM剧场对白，1 / 1，点击继续' })
    fireEvent.click(stage)

    expect(onAdvanceDialogue).toHaveBeenCalledTimes(1)
    expect(within(panel).queryByRole('log', { name: '冒险对话日志' })).not.toBeInTheDocument()
    expect(panel.querySelector('.dialogue-response-shell')).toHaveClass('hidden')
  })

  it('routes pending checks through the same panel shell', () => {
    const { onDiceRoll } = renderPanel({
      pendingCheck: {
        check_type: '运动',
        dc: 12,
        context: '撬开铁门',
      },
    })

    const panel = screen.getByRole('region', { name: '冒险对话面板' })
    expect(within(panel).getByLabelText('待处理技能检定')).toBeInTheDocument()
    fireEvent.click(within(panel).getByRole('button', { name: /投掷 d20/ }))
    expect(onDiceRoll).toHaveBeenCalledTimes(1)
  })
})
