import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import StageBubble from '../StageBubble'

describe('StageBubble', () => {
  it('renders a DM theatre line as a busy article while typing', () => {
    render(
      <StageBubble
        seg={{ role: 'dm', speaker: 'Narrator' }}
        typingText="The **rune** wakes."
        typingDone={false}
      />,
    )

    const bubble = screen.getByRole('article', { name: '剧场对白：Narrator', busy: true })
    expect(bubble).toHaveClass('stage-bubble', 'dm', 'is-typing')
    expect(bubble).toHaveAttribute('data-typing-state', 'typing')
    expect(within(bubble).queryByText(/❖/)).not.toBeInTheDocument()
    const strongText = within(bubble).getByText('rune')
    expect(strongText).toHaveClass('light-md-strong')
    expect(strongText.style.getPropertyValue('--light-md-accent-color')).toBe('var(--amber)')
    expect(strongText.style.fontWeight).toBe('')
    expect(strongText.style.fontStyle).toBe('')
    expect(bubble.querySelector('.stage-bubble-cursor')).toBeInTheDocument()
  })

  it('labels NPC and companion speakers with role-specific shell classes', () => {
    const { rerender } = render(
      <StageBubble
        seg={{ role: 'npc', speaker: '薇拉' }}
        typingText="别碰那个封印。"
        typingDone
      />,
    )

    const npcBubble = screen.getByRole('article', { name: '剧场对白：薇拉', busy: false })
    expect(npcBubble).toHaveClass('stage-bubble', 'npc', 'is-complete')
    expect(within(npcBubble).getByText('❖ 薇拉')).toHaveClass('stage-bubble-speaker')
    expect(npcBubble).toHaveAttribute('data-typing-state', 'complete')
    expect(npcBubble.querySelector('.stage-bubble-cursor')).not.toBeInTheDocument()

    rerender(
      <StageBubble
        seg={{ role: 'companion', speaker: '艾莉' }}
        typingText="我会守住门口。"
        typingDone
      />,
    )

    const companionBubble = screen.getByRole('article', { name: '剧场对白：艾莉', busy: false })
    expect(companionBubble).toHaveClass('stage-bubble', 'companion', 'is-complete')
    expect(within(companionBubble).getByText('❖ 艾莉')).toBeInTheDocument()
  })

  it('falls back unknown segment roles to the DM visual treatment', () => {
    render(
      <StageBubble
        seg={{ role: 'monster' }}
        typingText="The room goes quiet."
        typingDone
      />,
    )

    const bubble = screen.getByRole('article', { name: '剧场对白：DM', busy: false })
    expect(bubble).toHaveClass('stage-bubble', 'dm', 'is-complete')
    expect(within(bubble).getByText('The room goes quiet.')).toHaveClass('stage-bubble-text')
  })
})
