import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import JournalModal from '../JournalModal'

function makeSession() {
  return {
    current_scene: '低语者酒馆。雨水敲打窗棂。',
    combat_active: true,
    game_state: {
      scene_vibe: {
        location: '低语者酒馆',
        time_of_day: '深夜',
        tension: '危险',
      },
    },
    campaign_state: {
      completed_scenes: ['矿洞入口'],
      quest_log: [
        { quest: '寻找失踪矿工', status: 'active', outcome: '矿工可能被带往井底。' },
      ],
      npc_registry: {
        铁匠格雷: {
          relationship: '谨慎盟友',
          key_facts: ['知道旧井的位置'],
          promises: ['答应修好队伍的盾牌'],
        },
      },
      clues: [
        { text: '暗门在井底', category: 'location', is_new: true },
        { text: '符文需要月光启动', category: 'arcana' },
      ],
      key_decisions: ['信任铁匠格雷'],
      world_flags: {
        mine_alarm_raised: true,
      },
      recent_updates: [
        { type: 'world', label: '守卫开始巡逻', detail: '矿村警戒提高' },
      ],
    },
  }
}

describe('JournalModal', () => {
  it('renders a structured dossier for quests, NPCs, clues, locations, threats, and decisions', () => {
    render(
      <JournalModal
        session={makeSession()}
        room={{
          party_groups: [
            { id: 'alley', name: '后巷组', location: '酒馆后巷' },
          ],
        }}
        text="上一幕日志"
        loading={false}
        onGenerate={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const dossier = screen.getByLabelText('冒险卷宗')
    expect(within(dossier).getByText('任务')).toBeInTheDocument()
    expect(within(dossier).getByText('寻找失踪矿工')).toBeInTheDocument()
    expect(within(dossier).getByText('NPC')).toBeInTheDocument()
    expect(within(dossier).getByText('铁匠格雷')).toBeInTheDocument()
    expect(within(dossier).getByText(/知道旧井的位置/)).toBeInTheDocument()
    expect(within(dossier).getByText('线索')).toBeInTheDocument()
    expect(within(dossier).getAllByText('暗门在井底')).toHaveLength(2)
    expect(within(dossier).getByText('地点')).toBeInTheDocument()
    expect(within(dossier).getByText('低语者酒馆')).toBeInTheDocument()
    expect(within(dossier).getByText('酒馆后巷')).toBeInTheDocument()
    expect(within(dossier).getByText('未解决威胁')).toBeInTheDocument()
    expect(within(dossier).getByText('战斗仍在进行')).toBeInTheDocument()
    expect(within(dossier).getByText('mine alarm raised')).toBeInTheDocument()
    expect(within(dossier).getByText('守卫开始巡逻')).toBeInTheDocument()
    expect(within(dossier).getByText('关键决定')).toBeInTheDocument()
    expect(within(dossier).getByText('信任铁匠格雷')).toBeInTheDocument()
    expect(screen.getByText('上一幕日志')).toBeInTheDocument()
  })

  it('keeps generated journal controls available', () => {
    const onGenerate = vi.fn()
    const onClose = vi.fn()
    render(
      <JournalModal
        session={{ campaign_state: {}, game_state: {} }}
        text=""
        loading={false}
        onGenerate={onGenerate}
        onClose={onClose}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /重新生成/ }))
    fireEvent.click(screen.getByRole('button', { name: '关闭' }))

    expect(onGenerate).toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })
})
