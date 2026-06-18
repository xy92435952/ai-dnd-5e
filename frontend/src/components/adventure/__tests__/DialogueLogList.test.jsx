import { describe, expect, it } from 'vitest'
import { createRef } from 'react'
import { render, screen, within } from '@testing-library/react'
import DialogueLogList from '../DialogueLogList'

describe('DialogueLogList', () => {
  it('renders adventure logs as a named live log with list semantics', () => {
    const logsEndRef = createRef()

    render(
      <DialogueLogList
        logs={[
          { id: 'dm-1', role: 'dm', content: '钟声从矿道深处传来。' },
          { id: 'player-1', role: 'player', content: '我举起火把。' },
          { id: 'dice-1', role: 'dice', content: 'd20 = 14' },
          { id: 'system-1', role: 'system', content: '自动保存完成。' },
        ]}
        logsEndRef={logsEndRef}
      />,
    )

    const log = screen.getByRole('log', { name: '冒险对话日志' })
    expect(log).toHaveClass('dialogue-log-list')
    expect(log).toHaveAttribute('aria-live', 'polite')

    const items = within(log).getByRole('list', { name: '对话记录' })
    expect(items).toHaveClass('dialogue-log-items')
    expect(within(items).getAllByRole('listitem')).toHaveLength(4)
    expect(within(items).getByText('钟声从矿道深处传来。')).toHaveClass('dialogue-log-line-dm')
    expect(within(items).getByText(/我举起火把/)).toHaveClass('dialogue-log-line-player')
    expect(within(items).getByText(/d20 = 14/)).toHaveClass('dialogue-log-line-dice')
    expect(within(items).getByText('自动保存完成。')).toHaveClass('dialogue-log-line-system')
    expect(logsEndRef.current).toHaveClass('dialogue-log-end')
    expect(logsEndRef.current).toHaveAttribute('aria-hidden', 'true')
  })

  it('keeps the log shell present for an empty chat history', () => {
    render(<DialogueLogList logs={[]} logsEndRef={createRef()} />)

    const log = screen.getByRole('log', { name: '冒险对话日志' })
    expect(within(log).getByRole('list', { name: '对话记录' })).toBeInTheDocument()
    expect(within(log).queryAllByRole('listitem')).toHaveLength(0)
  })
})
