import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import DialogueRecoveryAffordances from '../DialogueRecoveryAffordances'

function renderAffordances(props = {}) {
  const setInput = vi.fn()
  const onAction = vi.fn()
  const focus = vi.fn()
  render(
    <DialogueRecoveryAffordances
      input=""
      setInput={setInput}
      inputRef={{ current: { focus } }}
      onAction={onAction}
      disabled={false}
      {...props}
    />,
  )
  return { setInput, onAction, focus }
}

describe('DialogueRecoveryAffordances', () => {
  it('submits a continue action directly', () => {
    const { onAction, setInput } = renderAffordances()

    const group = screen.getByRole('group', { name: '回应快捷入口' })
    expect(group).toHaveClass('recovery-affordances')

    const button = screen.getByRole('button', { name: '继续推进当前场景' })
    expect(button).toHaveAttribute('title', '直接请求 DM 继续推进当前场景')
    fireEvent.click(button)

    expect(onAction).toHaveBeenCalledWith(
      '继续推进当前场景。',
      { actionSource: 'system_action' },
    )
    expect(setInput).not.toHaveBeenCalled()
  })

  it('seeds an editable question and focuses the free input', () => {
    const { setInput, focus, onAction } = renderAffordances()

    const ask = screen.getByRole('button', { name: '提问：填入询问前缀' })
    expect(ask).toHaveAttribute('title', '在自由行动输入框中填入询问前缀')
    fireEvent.click(ask)

    expect(setInput).toHaveBeenCalledWith('我想询问：')
    expect(focus).toHaveBeenCalled()
    expect(onAction).not.toHaveBeenCalled()
  })

  it('seeds an editable action without discarding existing text', () => {
    const { setInput } = renderAffordances({ input: '检查井口' })

    const act = screen.getByRole('button', { name: '行动：填入尝试前缀' })
    expect(act).toHaveAttribute('title', '在自由行动输入框中填入尝试行动前缀')
    fireEvent.click(act)

    expect(setInput).toHaveBeenCalledWith('我尝试：检查井口')
  })

  it('does nothing while disabled', () => {
    const { setInput, onAction, focus } = renderAffordances({ disabled: true })

    fireEvent.click(screen.getByRole('button', { name: '继续推进当前场景' }))
    fireEvent.click(screen.getByRole('button', { name: '提问：填入询问前缀' }))

    expect(onAction).not.toHaveBeenCalled()
    expect(setInput).not.toHaveBeenCalled()
    expect(focus).not.toHaveBeenCalled()
  })
})
