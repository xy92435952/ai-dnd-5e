import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import DialogueFreeSpeak from '../DialogueFreeSpeak'

function renderFreeSpeak(props = {}) {
  const setInput = vi.fn()
  const onAction = vi.fn()
  const inputRef = { current: null }
  render(
    <DialogueFreeSpeak
      input=""
      setInput={setInput}
      inputRef={inputRef}
      onAction={onAction}
      isLoading={false}
      room={null}
      isMySpeakTurn={true}
      multiplayerSyncBlocked={false}
      {...props}
    />,
  )
  return { setInput, onAction }
}

describe('DialogueFreeSpeak', () => {
  it('labels the free-action input and sends entered text by button or Enter', () => {
    const { setInput, onAction } = renderFreeSpeak({ input: '检查门闩' })

    const group = screen.getByRole('group', { name: '自由行动输入' })
    expect(group).toHaveClass('free-speak')
    expect(screen.getByRole('status')).toHaveTextContent('自由行动已准备发送。')

    const input = screen.getByLabelText('✎ 自由行动')
    expect(input).toHaveAttribute('placeholder', '描述你的行动，或按上方编号快捷回应')
    fireEvent.change(input, { target: { value: '推开门' } })
    expect(setInput).toHaveBeenCalledWith('推开门')

    const send = screen.getByRole('button', { name: '发送自由行动' })
    expect(send).toHaveClass('free-speak-send')
    expect(send).toHaveAttribute('title', '发送自由行动')
    fireEvent.click(send)
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(onAction).toHaveBeenCalledTimes(2)
  })

  it('keeps send disabled until text is present', () => {
    const { onAction } = renderFreeSpeak()

    expect(screen.getByRole('status')).toHaveTextContent('输入行动描述后即可发送。')
    const send = screen.getByRole('button', { name: '发送自由行动（需要输入）' })
    expect(send).toBeDisabled()
    expect(send).toHaveAttribute('title', '请输入行动描述')

    fireEvent.click(send)
    expect(onAction).not.toHaveBeenCalled()
  })

  it('blocks free speak while waiting for multiplayer turn or room sync', () => {
    renderFreeSpeak({
      input: '我继续前进',
      room: { code: 'ABCD' },
      isMySpeakTurn: false,
    })

    expect(screen.getByRole('status')).toHaveTextContent('等待当前发言者结束回合。')
    expect(screen.getByLabelText('✎ 自由行动')).toHaveAttribute('placeholder', '等待发言权…')
    expect(screen.getByRole('button', { name: '发送自由行动' })).toBeDisabled()
  })

  it('surfaces loading and sync-blocked reasons in the input status', () => {
    const { rerender } = render(
      <DialogueFreeSpeak
        input="观察大厅"
        setInput={vi.fn()}
        inputRef={{ current: null }}
        onAction={vi.fn()}
        isLoading
        room={null}
        isMySpeakTurn
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('地下城主正在回应，暂时不能发送自由行动。')
    expect(screen.getByLabelText('✎ 自由行动')).toHaveAttribute('placeholder', '✦ 地下城主正在编织命运… ✦')

    rerender(
      <DialogueFreeSpeak
        input="观察大厅"
        setInput={vi.fn()}
        inputRef={{ current: null }}
        onAction={vi.fn()}
        isLoading={false}
        room={{ code: 'ABCD' }}
        isMySpeakTurn
        multiplayerSyncBlocked
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('房间正在重新同步，恢复后可继续发言。')
    expect(screen.getByLabelText('✎ 自由行动')).toHaveAttribute('placeholder', '正在重新同步房间，恢复后可继续发言…')
  })
})
