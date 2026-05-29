import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import RestModal from '../RestModal'

describe('RestModal', () => {
  it('shows party rest impact before confirming a long rest', () => {
    const onRest = vi.fn()
    render(
      <RestModal
        party={[{
          id: 'hero-1',
          name: 'Aria',
          char_class: 'Wizard',
          level: 4,
          hp_current: 5,
          hp_max: 18,
          hit_dice_remaining: 1,
          spell_slots: { '1st': 0 },
          derived: { spell_slots_max: { '1st': 3 } },
          conditions: ['poisoned'],
          death_saves: { failures: 1 },
        }]}
        onRest={onRest}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText(/确认前预览/)).toBeInTheDocument()

    const preview = screen.getByLabelText('休息前队伍状态预览')
    expect(within(preview).getByText('Aria')).toBeInTheDocument()
    expect(within(preview).getByText('HP 5/18')).toBeInTheDocument()
    expect(within(preview).getByText('生命骰 1/4')).toBeInTheDocument()
    expect(within(preview).getAllByText('法术位 1st+3').length).toBeGreaterThan(0)
    expect(within(preview).getByText('状态 poisoned')).toBeInTheDocument()
    expect(within(preview).getByText('HP 恢复到 18/18')).toBeInTheDocument()
    expect(within(preview).getByText('重置濒死豁免')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /执行长休/ }))
    expect(onRest).toHaveBeenCalledWith('long')
  })

  it('keeps short rest as an explicit confirmation and reports hit dice risk', () => {
    const onRest = vi.fn()
    render(
      <RestModal
        party={[{
          id: 'fighter-1',
          name: 'Borin',
          char_class: 'Fighter',
          level: 2,
          hp_current: 3,
          hp_max: 14,
          hit_dice_remaining: 0,
        }]}
        onRest={onRest}
        onClose={vi.fn()}
      />,
    )

    const shortSummary = screen.getByLabelText('短休（1小时）预览摘要')
    expect(within(shortSummary).getByText('1 人生命骰不足')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /短休/ }))
    expect(onRest).not.toHaveBeenCalled()
    expect(screen.getByText('HP 缺 11，但生命骰不足')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /执行短休/ }))
    expect(onRest).toHaveBeenCalledWith('short')
  })
})
