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

    const stage = screen.getByRole('button', { name: 'DM剧场对白，1 / 1，点击继续' })
    expect(stage).toHaveClass('dialogue-stage-player')
    expect(screen.getByRole('article', { name: '剧场对白：DM' })).toHaveClass('stage-bubble', 'dm')
    const progress = screen.getByRole('status')
    expect(progress).toHaveClass('dialogue-stage-progress')
    expect(progress).toHaveTextContent('1 / 1')
    expect(within(progress).getByText('▸ 点击继续（空格/回车）')).toHaveClass('ready')

    const secondary = screen.getByLabelText('队友反应')
    expect(within(secondary).getByText('队友反应')).toBeInTheDocument()
    expect(within(secondary).getByText(/艾莉/)).toBeInTheDocument()
    expect(within(secondary).getByText(/我盯着后门/)).toBeInTheDocument()
    expect(within(secondary).getByText(/博恩/)).toBeInTheDocument()
    expect(within(secondary).getByText(/别分散/)).toBeInTheDocument()

    fireEvent.click(stage)
    fireEvent.keyDown(stage, { key: 'Enter' })
    fireEvent.keyDown(stage, { key: ' ' })
    expect(onAdvanceDialogue).toHaveBeenCalledTimes(3)
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
    expect(screen.getByRole('button', { name: 'DM剧场对白，1 / 1，点击跳过打字' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('… 打字中（点击跳过）')
    expect(document.querySelector('.stage-bubble-cursor')).toBeInTheDocument()
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
    expect(text.closest('.stage-bubble')).toBeInTheDocument()
    expect(text.closest('.dialogue-stage-player')).toBeInTheDocument()
  })

  it('labels NPC speakers without using inline speaker chrome', () => {
    render(
      <DialogueStagePlayer
        dialogueQueue={[{
          speaker: '薇拉',
          role: 'npc',
          text: '别碰那个封印。',
          companionReactions: [],
        }]}
        dialogueIdx={0}
        typingText="别碰那个封印。"
        typingDone
        onAdvanceDialogue={vi.fn()}
      />,
    )

    const bubble = screen.getByRole('article', { name: '剧场对白：薇拉' })
    expect(bubble).toHaveClass('stage-bubble', 'npc')
    expect(within(bubble).getByText('❖ 薇拉')).toHaveClass('stage-bubble-speaker')
  })
})
