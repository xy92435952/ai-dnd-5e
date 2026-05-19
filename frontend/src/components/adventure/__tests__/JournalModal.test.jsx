import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import JournalModal from '../JournalModal'

vi.mock('../Overlay', () => ({
  default: ({ children }) => <div data-testid="overlay">{children}</div>,
}))

describe('JournalModal', () => {
  it('shows structured campaign memory beside generated journal prose', () => {
    const campaignState = {
      quest_log: [
        { title: '调查矿洞', status: 'active', summary: '找到鸦翼矿洞失踪矿工的真相。' },
        { title: '护送雷克', status: 'completed', summary: '雷克已经抵达灰岩镇。' },
      ],
      clues: [
        { text: '矿洞深处有苍白符文', found_at: '鸦翼矿洞口' },
      ],
      npc_registry: {
        雷克: {
          relationship: '谨慎信任',
          key_facts: ['曾在矿洞里听见亡灵低语'],
        },
      },
      key_decisions: ['玩家决定夜间进入矿洞'],
    }

    render(
      <JournalModal
        text="DM 生成的冒险日志仍然应该可读。"
        loading={false}
        campaignState={campaignState}
        onGenerate={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('任务')).toBeInTheDocument()
    expect(screen.getByText('调查矿洞')).toBeInTheDocument()
    expect(screen.getByText('线索')).toBeInTheDocument()
    expect(screen.getByText('矿洞深处有苍白符文')).toBeInTheDocument()
    expect(screen.getByText('人物')).toBeInTheDocument()
    expect(screen.getByText('雷克')).toBeInTheDocument()
    expect(screen.getByText('关键决定')).toBeInTheDocument()
    expect(screen.getByText('玩家决定夜间进入矿洞')).toBeInTheDocument()
    expect(screen.getByText('DM 生成的冒险日志仍然应该可读。')).toBeInTheDocument()
  })
})
