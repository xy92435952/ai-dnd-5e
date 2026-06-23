import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import CombatOverlays from '../CombatOverlays'

function renderOverlays(overrides = {}) {
  return render(
    <CombatOverlays
      playerSpellSlots={{}}
      playerAvailableSpells={[]}
      playerCantrips={[]}
      selectedTarget={null}
      playerId="hero-1"
      combat={{ entities: {} }}
      onSmite={vi.fn()}
      onCancelSmite={vi.fn()}
      onResetAoeCenter={vi.fn()}
      onCastSpell={vi.fn()}
      onCloseSpell={vi.fn()}
      onSpellHover={vi.fn()}
      onToggleBardicSpellSave={vi.fn()}
      onUseManeuver={vi.fn()}
      onCloseManeuver={vi.fn()}
      onReact={vi.fn()}
      onCancelReaction={vi.fn()}
      onUseLairAction={vi.fn()}
      onSkipLairAction={vi.fn()}
      onUseLegendaryAction={vi.fn()}
      onSkipLegendaryAction={vi.fn()}
      onConfirmForceEndCombat={vi.fn()}
      onCancelForceEndCombat={vi.fn()}
      {...overrides}
    />,
  )
}

describe('CombatOverlays', () => {
  it('renders combat errors as a stable alert toast', () => {
    renderOverlays({ error: '目标超出法术射程' })

    const alert = screen.getByRole('alert')
    expect(alert).toHaveClass('combat-overlay-error')
    expect(alert).toHaveTextContent('目标超出法术射程')
  })

  it('gives lair action prompts precedence over legendary action prompts', () => {
    const onUseLairAction = vi.fn()
    const onUseLegendaryAction = vi.fn()

    renderOverlays({
      lairActionPrompt: {
        source_id: 'lair-1',
        source_name: 'Cracked Shrine',
        round_number: 2,
        actions: [{ id: 'pulse', name: 'Seismic Pulse' }],
      },
      legendaryActionPrompt: {
        actor_id: 'dragon-1',
        actor_name: 'Ancient Gatekeeper',
        remaining: 1,
        uses: 3,
        actions: [{ id: 'tail', name: 'Tail Strike' }],
      },
      onUseLairAction,
      onUseLegendaryAction,
    })

    expect(screen.getByRole('dialog', { name: '巢穴动作窗口' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: '传奇动作窗口' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Seismic Pulse/ }))
    expect(onUseLairAction).toHaveBeenCalledWith('lair-1', 'pulse', undefined)
    expect(onUseLegendaryAction).not.toHaveBeenCalled()
  })

  it('renders force-end combat confirmation as a stable in-app dialog', () => {
    const onConfirmForceEndCombat = vi.fn()
    const onCancelForceEndCombat = vi.fn()

    renderOverlays({
      forceEndConfirmOpen: true,
      onConfirmForceEndCombat,
      onCancelForceEndCombat,
    })

    const dialog = screen.getByRole('dialog', { name: '强制结束战斗' })
    expect(dialog).toHaveClass('combat-force-end-confirm')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByText('这会立即结束当前战斗并返回冒险场景。')).toHaveAttribute(
      'id',
      'combat-force-end-confirm-desc',
    )

    const actions = screen.getByRole('group', { name: '强制结束战斗操作' })
    expect(actions).toHaveClass('combat-force-end-confirm-actions')
    const cancel = screen.getByRole('button', { name: '取消' })
    const confirm = screen.getByRole('button', { name: '确认结束' })
    expect(cancel).toHaveClass('combat-force-end-confirm-cancel')
    expect(confirm).toHaveClass('combat-force-end-confirm-submit')

    fireEvent.click(cancel)
    fireEvent.click(confirm)

    expect(onCancelForceEndCombat).toHaveBeenCalledTimes(1)
    expect(onConfirmForceEndCombat).toHaveBeenCalledTimes(1)
  })

  it('renders Cutting Words contested-check confirmation as a stable in-app dialog', () => {
    const onConfirmCuttingWordsCheck = vi.fn()
    const onCancelCuttingWordsCheck = vi.fn()

    renderOverlays({
      cuttingWordsConfirm: {
        actionType: 'grapple',
        die: 'd8',
        faces: 8,
        targetId: 'enemy-1',
        targetName: 'Training Dummy',
      },
      onConfirmCuttingWordsCheck,
      onCancelCuttingWordsCheck,
    })

    const dialog = screen.getByRole('dialog', { name: 'Use Cutting Words?' })
    expect(dialog).toHaveClass('combat-cutting-words-confirm')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog.querySelector('.combat-cutting-words-confirm-panel')).toHaveAttribute('data-action', 'grapple')
    expect(screen.getByText("Spend Bardic Inspiration to subtract d8 from Training Dummy's contested check.")).toHaveAttribute(
      'id',
      'combat-cutting-words-confirm-desc',
    )

    const context = screen.getByRole('group', { name: 'Cutting Words roll context' })
    expect(context).toHaveClass('combat-cutting-words-confirm-meta')
    expect(context).toHaveTextContent('d8')
    expect(context).toHaveTextContent('Grapple')
    expect(context).toHaveTextContent('Training Dummy')

    const actions = screen.getByRole('group', { name: 'Cutting Words confirmation actions' })
    expect(actions).toHaveClass('combat-cutting-words-confirm-actions')
    const cancel = screen.getByRole('button', { name: 'Skip' })
    const confirm = screen.getByRole('button', { name: 'Use Cutting Words' })
    expect(cancel).toHaveClass('combat-cutting-words-confirm-cancel')
    expect(confirm).toHaveClass('combat-cutting-words-confirm-submit')

    fireEvent.click(cancel)
    fireEvent.click(confirm)

    expect(onCancelCuttingWordsCheck).toHaveBeenCalledTimes(1)
    expect(onConfirmCuttingWordsCheck).toHaveBeenCalledTimes(1)
  })
})
