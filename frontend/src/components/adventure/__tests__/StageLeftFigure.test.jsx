import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import StageLeftFigure from '../StageLeftFigure'

describe('StageLeftFigure', () => {
  it('hides the speaker figure in chat mode when there is no DM content', () => {
    const { container } = render(
      <StageLeftFigure
        dialogueMode="chat"
        currentSeg={null}
        companions={[]}
        hasDmContent={false}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('renders the chat-mode DM narrator with stable speaker classes', () => {
    render(
      <StageLeftFigure
        dialogueMode="chat"
        currentSeg={null}
        companions={[]}
        hasDmContent
      />,
    )

    const figure = screen.getByRole('group', { name: '当前说话者：旁白' })
    expect(figure).toHaveClass('stage-figure', 'left', 'stage-speaker-figure', 'dm_narration')
    expect(figure).not.toHaveAttribute('style')
    expect(figure.querySelector('.stage-speaker-silhouette')).toBeInTheDocument()
    expect(within(figure).getByText('DM')).toHaveClass('stage-figure-initial', 'stage-speaker-initial')
    expect(within(figure).getByText('❖ 旁白')).toHaveClass('nameplate', 'stage-speaker-nameplate', 'gold')
  })

  it('renders NPC and companion stage speakers without inline plate chrome', () => {
    const { rerender } = render(
      <StageLeftFigure
        dialogueMode="stage"
        currentSeg={{ role: 'npc', speaker: '薇拉' }}
        companions={[]}
        hasDmContent
      />,
    )

    const npcFigure = screen.getByRole('group', { name: '当前说话者：薇拉' })
    expect(npcFigure).toHaveClass('stage-speaker-figure', 'npc')
    expect(npcFigure).not.toHaveAttribute('style')
    expect(within(npcFigure).getByText('薇')).toHaveClass('stage-speaker-initial')
    expect(within(npcFigure).getByText('❖ 薇拉')).toHaveClass('stage-speaker-nameplate', 'default')

    rerender(
      <StageLeftFigure
        dialogueMode="stage"
        currentSeg={{ role: 'companion', speaker: '艾莉' }}
        companions={[{ id: 'ally-1', name: '艾莉娜' }]}
        hasDmContent
      />,
    )

    const companionFigure = screen.getByRole('group', { name: '当前说话者：艾莉' })
    expect(companionFigure).toHaveClass('stage-speaker-figure', 'companion')
    expect(companionFigure).not.toHaveAttribute('style')
    expect(within(companionFigure).getByText('艾')).toHaveClass('stage-speaker-initial')
    expect(within(companionFigure).getByText('◈ 艾莉')).toHaveClass('stage-speaker-nameplate', 'companion')
  })
})
