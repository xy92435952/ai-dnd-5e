import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import RestModal from '../RestModal'

describe('RestModal', () => {
  it('shows party rest impact before confirming a long rest', () => {
    const onRest = vi.fn()
    const onClose = vi.fn()
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
        onClose={onClose}
      />,
    )

    expect(screen.getByText(/确认前预览/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '关闭休息面板' }))
    expect(onClose).toHaveBeenCalledTimes(1)

    const status = screen.getByRole('status')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(within(status).getByText('当前选择')).toBeInTheDocument()
    expect(within(status).getByText('长休')).toBeInTheDocument()
    expect(within(status).getByText('1 名角色预览')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '选择长休（8小时）' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '选择短休（1小时）' })).toHaveAttribute('aria-pressed', 'false')

    const preview = screen.getByLabelText('休息前队伍状态预览')
    expect(within(preview).getByText('Aria')).toBeInTheDocument()
    expect(within(preview).getByText('HP 5/18')).toBeInTheDocument()
    const hpMeterFill = preview.querySelector('.rest-member-meter-fill')
    expect(hpMeterFill).toHaveStyle({ '--rest-hp-pct': '27.77777777777778%' })
    expect(within(preview).getByText('生命骰 1/4')).toBeInTheDocument()
    expect(within(preview).getAllByText('法术位 1st+3').length).toBeGreaterThan(0)
    expect(within(preview).getByText('状态 poisoned')).toBeInTheDocument()
    expect(within(preview).getByText('HP 恢复到 18/18')).toBeInTheDocument()
    expect(within(preview).getByText('重置濒死豁免')).toBeInTheDocument()

    const actions = screen.getByRole('group', { name: '休息操作' })
    fireEvent.click(within(actions).getByRole('button', { name: '执行长休' }))
    expect(onRest).toHaveBeenCalledWith('long')
  })

  it('keeps short rest as an explicit confirmation and reports hit dice risk', () => {
    const onRest = vi.fn()
    const onClose = vi.fn()
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
        onClose={onClose}
      />,
    )

    const shortSummary = screen.getByLabelText('短休（1小时）预览摘要')
    expect(within(shortSummary).getByText('1 人生命骰不足')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '选择短休（1小时）' }))
    expect(onRest).not.toHaveBeenCalled()
    const status = screen.getByRole('status')
    expect(within(status).getByText('短休')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '选择长休（8小时）' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: '选择短休（1小时）' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('HP 缺 11，但生命骰不足')).toBeInTheDocument()

    const actions = screen.getByRole('group', { name: '休息操作' })
    fireEvent.click(within(actions).getByRole('button', { name: '执行短休' }))
    expect(onRest).toHaveBeenCalledWith('short')
    fireEvent.click(within(actions).getByRole('button', { name: '取消休息' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
