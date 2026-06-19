import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import SmitePrompt from '../SmitePrompt'

describe('SmitePrompt', () => {
  it('renders nothing while closed', () => {
    const { container } = render(
      <SmitePrompt open={false} playerSpellSlots={{ '1st': 1 }} onSmite={vi.fn()} onCancel={vi.fn()} />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('uses an available smite slot', () => {
    const onSmite = vi.fn()

    render(
      <SmitePrompt open playerSpellSlots={{ '1st': 1, '2nd': 0 }} onSmite={onSmite} onCancel={vi.fn()} />,
    )

    const dialog = screen.getByRole('dialog', { name: '命中！是否使用神圣斩击？' })
    expect(dialog).toHaveClass('smite-prompt-dialog')
    expect(within(dialog).getByText('消耗 1 环法术位造成 +2d8 辐光伤害（每升一环 +1d8）')).toHaveClass('smite-prompt-description')
    const list = within(dialog).getByRole('list', { name: '可用神圣斩击法术位' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(1)

    const firstSlot = within(list).getByRole('button', {
      name: '使用 1 环法术位发动神圣斩击，额外 2d8 辐光伤害',
    })
    expect(firstSlot).toHaveClass('smite-prompt-slot')
    expect(within(firstSlot).getByText('+2d8')).toHaveClass('smite-prompt-dice')

    fireEvent.click(firstSlot)
    expect(onSmite).toHaveBeenCalledWith(1)
    expect(screen.queryByRole('button', {
      name: '使用 2 环法术位发动神圣斩击，额外 3d8 辐光伤害',
    })).not.toBeInTheDocument()
  })

  it('labels higher-level smite slots with the added radiant dice', () => {
    render(
      <SmitePrompt
        open
        playerSpellSlots={{ '1st': 0, '2nd': 1, '3rd': 1 }}
        onSmite={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    const list = screen.getByRole('list', { name: '可用神圣斩击法术位' })
    expect(within(list).getByRole('listitem', {
      name: /使用 2 环法术位发动神圣斩击，额外 3d8 辐光伤害/,
    })).toBeInTheDocument()
    expect(within(list).getByRole('listitem', {
      name: /使用 3 环法术位发动神圣斩击，额外 4d8 辐光伤害/,
    })).toBeInTheDocument()
  })

  it('explains when no smite slots are available and still allows cancelling', () => {
    const onSmite = vi.fn()
    const onCancel = vi.fn()

    render(
      <SmitePrompt open playerSpellSlots={{ '1st': 0, '2nd': 0 }} onSmite={onSmite} onCancel={onCancel} />,
    )

    const dialog = screen.getByRole('dialog', { name: '命中！是否使用神圣斩击？' })
    expect(within(dialog).getByRole('status')).toHaveTextContent('没有可用法术位，无法发动神圣斩击。')
    expect(screen.queryByRole('button', { name: /环/ })).not.toBeInTheDocument()

    const cancel = within(dialog).getByRole('button', { name: '取消' })
    expect(cancel).toHaveClass('smite-prompt-cancel')
    fireEvent.click(cancel)
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onSmite).not.toHaveBeenCalled()
  })
})
