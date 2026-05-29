import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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

    fireEvent.click(screen.getByRole('button', { name: '1环' }))
    expect(onSmite).toHaveBeenCalledWith(1)
    expect(screen.queryByRole('button', { name: '2环' })).not.toBeInTheDocument()
  })

  it('explains when no smite slots are available and still allows cancelling', () => {
    const onSmite = vi.fn()
    const onCancel = vi.fn()

    render(
      <SmitePrompt open playerSpellSlots={{ '1st': 0, '2nd': 0 }} onSmite={onSmite} onCancel={onCancel} />,
    )

    expect(screen.getByText('没有可用法术位，无法发动神圣斩击。')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /环/ })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onSmite).not.toHaveBeenCalled()
  })
})
