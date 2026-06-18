import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import AdventureStage from '../AdventureStage'

function renderStage(props = {}) {
  render(
    <AdventureStage
      dialogueMode="chat"
      currentSeg={null}
      companions={[]}
      player={{ id: 'player-1', name: 'Mara Quickstep' }}
      hasDmContent
      sceneVibe={{
        location: 'Gatehouse',
        time_of_day: 'Dawn',
        tension: '危险',
      }}
      isLoading={false}
      {...props}
    />,
  )
}

describe('AdventureStage', () => {
  it('renders the stage shell, player figure, focus glow, and scene status with stable classes', () => {
    renderStage()

    const stage = screen.getByRole('region', { name: '冒险剧场舞台' })
    expect(stage).toHaveClass('dialogue-stage')
    expect(stage.querySelector('.stage-letterbox.top')).toBeInTheDocument()
    expect(stage.querySelector('.stage-letterbox.bottom')).toBeInTheDocument()
    expect(stage.querySelector('.stage-focus-glow')).toHaveAttribute('aria-hidden', 'true')
    expect(stage.querySelector('.stage-focus-glow-core')).toBeInTheDocument()

    const playerFigure = within(stage).getByRole('group', { name: '玩家角色：Mara Quickstep' })
    expect(playerFigure).toHaveClass('stage-figure', 'right', 'stage-figure-player')
    expect(playerFigure.querySelector('.player-silhouette')).toBeInTheDocument()
    expect(within(playerFigure).getByText('M')).toHaveClass('stage-figure-initial')
    expect(within(playerFigure).getByText('◈ Mara Quickstep')).toHaveClass('nameplate', 'player-nameplate')

    const vibe = within(stage).getByRole('status', { name: '当前场景状态' })
    expect(vibe).toHaveClass('scene-vibe-strip')
    expect(vibe).toHaveAttribute('aria-live', 'polite')
    expect(within(vibe).getByText('🜂 Gatehouse')).toHaveClass('scene-vibe-item', 'location')
    expect(within(vibe).getByText('☀ Dawn')).toHaveClass('scene-vibe-item', 'time')
    expect(within(vibe).getByText('⚠ 危险')).toHaveClass('scene-vibe-item', 'tension', 'danger')
  })

  it('keeps calm and watch tension states distinct without requiring a player figure', () => {
    const { rerender } = render(
      <AdventureStage
        dialogueMode="chat"
        currentSeg={null}
        companions={[]}
        player={null}
        hasDmContent={false}
        sceneVibe={{ tension: '平静' }}
        isLoading={false}
      />,
    )

    const calmStage = screen.getByRole('region', { name: '冒险剧场舞台' })
    expect(within(calmStage).queryByRole('group', { name: /玩家角色/ })).not.toBeInTheDocument()
    expect(within(calmStage).getByText('⚠ 平静')).toHaveClass('scene-vibe-item', 'tension', 'calm')

    rerender(
      <AdventureStage
        dialogueMode="chat"
        currentSeg={null}
        companions={[]}
        player={null}
        hasDmContent={false}
        sceneVibe={{ tension: '紧张' }}
        isLoading={false}
      />,
    )

    expect(screen.getByText('⚠ 紧张')).toHaveClass('scene-vibe-item', 'tension', 'watch')
  })
})
