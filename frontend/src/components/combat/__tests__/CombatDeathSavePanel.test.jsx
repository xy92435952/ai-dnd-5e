import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CombatDeathSavePanel from '../CombatDeathSavePanel'

describe('CombatDeathSavePanel', () => {
  it('shows a roll button for dying characters on their turn', () => {
    const onDeathSave = vi.fn()
    render(
      <CombatDeathSavePanel
        character={{
          hp_current: 0,
          life_state: 'dying',
          death_saves: { successes: 1, failures: 2, stable: false },
        }}
        isPlayerTurn
        isProcessing={false}
        onDeathSave={onDeathSave}
      />,
    )

    const panel = screen.getByRole('region', { name: '死亡豁免状态' })
    expect(within(panel).getByText('濒死豁免')).toBeTruthy()
    const progress = within(panel).getByRole('list', { name: '死亡豁免进度：成功 1/3，失败 2/3' })
    expect(within(progress).getByRole('listitem', { name: '成功 1/3' })).toBeInTheDocument()
    expect(within(progress).getByRole('listitem', { name: '失败 2/3' })).toBeInTheDocument()
    expect(within(progress).getAllByRole('listitem', { name: /第 \d 格/ })).toHaveLength(6)
    const dotItems = within(progress).getAllByRole('listitem', { name: /第 \d 格/ })
    expect(dotItems[0]).toHaveAttribute('data-tone', 'success')
    expect(dotItems[0]).not.toHaveAttribute('style')
    expect(dotItems[3]).toHaveAttribute('data-tone', 'failure')
    expect(dotItems[3]).not.toHaveAttribute('style')

    const button = within(panel).getByRole('button', { name: '掷死亡豁免' })
    expect(button).not.toBeDisabled()
    fireEvent.click(button)
    expect(onDeathSave).toHaveBeenCalledTimes(1)
  })

  it('shows and toggles Bardic Inspiration for dying characters with an unused die', () => {
    const onToggleBardicDeathSave = vi.fn()
    render(
      <CombatDeathSavePanel
        character={{
          hp_current: 0,
          life_state: 'dying',
          death_saves: { successes: 0, failures: 1, stable: false },
        }}
        isPlayerTurn
        isProcessing={false}
        classResources={{ bardic_inspiration: { die: 'd8', uses_remaining: 1 } }}
        useBardicDeathSave
        onToggleBardicDeathSave={onToggleBardicDeathSave}
        onDeathSave={vi.fn()}
      />,
    )

    const bardic = screen.getByRole('button', { name: 'Bardic Inspiration 开启，d8' })
    expect(bardic).toHaveAttribute('aria-pressed', 'true')
    expect(bardic).toHaveTextContent('Bardic ON · d8')

    fireEvent.click(bardic)
    expect(onToggleBardicDeathSave).toHaveBeenCalledTimes(1)
  })

  it('shows stable status without allowing another roll', () => {
    render(
      <CombatDeathSavePanel
        character={{
          hp_current: 0,
          life_state: 'stable',
          death_saves: { successes: 3, failures: 0, stable: true },
        }}
        isPlayerTurn
        isProcessing={false}
        onDeathSave={vi.fn()}
      />,
    )

    const panel = screen.getByRole('region', { name: '死亡豁免状态' })
    expect(within(panel).getByText('已稳定')).toBeTruthy()
    const button = screen.getByRole('button', { name: '无需检定' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', '角色已稳定')
    expect(screen.getByRole('status')).toHaveTextContent('角色已稳定，等待治疗或战斗结束。')
  })

  it('explains why a dying character cannot roll yet', () => {
    const onDeathSave = vi.fn()

    render(
      <CombatDeathSavePanel
        character={{
          hp_current: 0,
          life_state: 'dying',
          death_saves: { successes: 0, failures: 1, stable: false },
        }}
        isPlayerTurn={false}
        isProcessing={false}
        onDeathSave={onDeathSave}
      />,
    )

    const button = screen.getByRole('button', { name: '掷死亡豁免' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', '等待你的回合')
    expect(screen.getByRole('status')).toHaveTextContent('等待你的回合后进行死亡豁免。')

    fireEvent.click(button)
    expect(onDeathSave).not.toHaveBeenCalled()
  })

  it('explains sync-blocked death saves', () => {
    render(
      <CombatDeathSavePanel
        character={{
          hp_current: 0,
          life_state: 'dying',
          death_saves: { successes: 0, failures: 1, stable: false },
        }}
        isPlayerTurn
        isProcessing={false}
        syncBlocked
        onDeathSave={vi.fn()}
      />,
    )

    const button = screen.getByRole('button', { name: '同步中' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', '等待战斗同步恢复')
    expect(screen.getByRole('status')).toHaveTextContent('等待战斗同步恢复后进行死亡豁免。')
  })
})
