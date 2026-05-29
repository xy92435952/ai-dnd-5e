import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import DialogueStagePlayer from '../DialogueStagePlayer'

describe('DialogueStagePlayer', () => {
  it('renders companion reactions in a secondary area after the main line finishes typing', () => {
    const onAdvanceDialogue = vi.fn()

    render(
      <DialogueStagePlayer
        dialogueQueue={[{
          speaker: 'DM',
          role: 'dm',
          text: '酒馆的灯火突然暗下去。',
          companionReactions: [
            { speaker: '艾莉', text: '我盯着后门。' },
            { speaker: '博恩', text: '别分散。' },
          ],
        }]}
        dialogueIdx={0}
        typingText="酒馆的灯火突然暗下去。"
        typingDone
        onAdvanceDialogue={onAdvanceDialogue}
      />,
    )

    const secondary = screen.getByLabelText('队友反应')
    expect(within(secondary).getByText('队友反应')).toBeInTheDocument()
    expect(within(secondary).getByText(/艾莉/)).toBeInTheDocument()
    expect(within(secondary).getByText(/我盯着后门/)).toBeInTheDocument()
    expect(within(secondary).getByText(/博恩/)).toBeInTheDocument()
    expect(within(secondary).getByText(/别分散/)).toBeInTheDocument()

    fireEvent.click(screen.getByText(/酒馆的灯火/).closest('div'))
    expect(onAdvanceDialogue).toHaveBeenCalledTimes(1)
  })

  it('hides companion reactions while the main line is still typing', () => {
    render(
      <DialogueStagePlayer
        dialogueQueue={[{
          speaker: 'DM',
          role: 'dm',
          text: '酒馆的灯火突然暗下去。',
          companionReactions: [{ speaker: '艾莉', text: '我盯着后门。' }],
        }]}
        dialogueIdx={0}
        typingText="酒馆"
        typingDone={false}
        onAdvanceDialogue={vi.fn()}
      />,
    )

    expect(screen.queryByLabelText('队友反应')).not.toBeInTheDocument()
  })

  it('keeps long stage narration inside a wrapping layout shell', () => {
    const longWord = 'ancient-rune-'.repeat(30)

    render(
      <DialogueStagePlayer
        dialogueQueue={[{
          speaker: 'DM',
          role: 'dm',
          text: longWord,
          companionReactions: [],
        }]}
        dialogueIdx={0}
        typingText={`${longWord}\n第二段叙事继续展开。`}
        typingDone
        onAdvanceDialogue={vi.fn()}
      />,
    )

    const text = screen.getByText(/ancient-rune/)
    expect(text).toHaveClass('stage-bubble-text')
    expect(text).toHaveStyle({ whiteSpace: 'pre-wrap' })
    expect(text.closest('.stage-bubble')).toBeInTheDocument()
    expect(text.closest('.dialogue-stage-player')).toBeInTheDocument()
  })
})
