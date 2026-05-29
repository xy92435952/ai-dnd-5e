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
})
