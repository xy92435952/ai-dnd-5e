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

    fireEvent.click(screen.getByRole('button', { name: /继续/ }))

    expect(onAction).toHaveBeenCalledWith(
      '继续推进当前场景。',
      { actionSource: 'system_action' },
    )
    expect(setInput).not.toHaveBeenCalled()
  })

  it('seeds an editable question and focuses the free input', () => {
    const { setInput, focus, onAction } = renderAffordances()

    fireEvent.click(screen.getByRole('button', { name: /提问/ }))

    expect(setInput).toHaveBeenCalledWith('我想询问：')
    expect(focus).toHaveBeenCalled()
    expect(onAction).not.toHaveBeenCalled()
  })

  it('seeds an editable action without discarding existing text', () => {
    const { setInput } = renderAffordances({ input: '检查井口' })

    fireEvent.click(screen.getByRole('button', { name: /行动/ }))

    expect(setInput).toHaveBeenCalledWith('我尝试：检查井口')
  })

  it('does nothing while disabled', () => {
    const { setInput, onAction, focus } = renderAffordances({ disabled: true })

    fireEvent.click(screen.getByRole('button', { name: /继续/ }))
    fireEvent.click(screen.getByRole('button', { name: /提问/ }))

    expect(onAction).not.toHaveBeenCalled()
    expect(setInput).not.toHaveBeenCalled()
    expect(focus).not.toHaveBeenCalled()
  })
})
