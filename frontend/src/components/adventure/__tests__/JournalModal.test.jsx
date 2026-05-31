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
        { quest: '寻找失踪矿工', status: 'active', next_step: '确认矿工是否被带往井底。' },
        { quest: '守住营地', status: 'failed', outcome: '狼群冲破外圈，幸存者退入旧矿道。' },
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
      companion_bonds: {
        'ally-1': {
          name: '艾琳',
          character_id: 'ally-1',
          relationship: '信任',
          approval: 18,
          last_approval_delta: 6,
          last_approval_reason: '尊重了她的侦察判断',
          personal_quest: {
            title: '月下旧誓',
            status: 'active',
            detail: '她愿意谈起银叶徽记的来源。',
            next_step: '在安全营地单独交谈。',
          },
        },
      },
      recent_updates: [
        { type: 'quest', label: '寻找失踪矿工', detail: '发现井底拖拽痕迹', status: 'active', at: '1' },
        { type: 'quest', label: '守住营地', detail: '营地被攻破', status: 'failed', at: '2' },
        { type: 'world', label: '守卫开始巡逻', detail: '矿村警戒提高' },
      ],
    },
    companions: [
      {
        id: 'ally-1',
        name: '艾琳',
        race: '半精灵',
        char_class: 'Ranger',
        level: 2,
        hp_current: 15,
        hp_max: 18,
        derived: { ac: 14, speed: 30 },
        personality: '冷静的斥候，遇到危险会先确认撤退路线。',
        speech_style: '短句、实用',
        combat_preference: '远程压制并保护后排',
        catchphrase: '先看脚印，再拔剑。',
      },
    ],
    logs: [
      {
        id: 'log-companion-1',
        role: 'companion',
        log_type: 'companion',
        content: '[艾琳]: 我盯着后门，别让他们绕过来。',
        created_at: '2026-06-01T10:00:00Z',
      },
    ],
  }
}

describe('JournalModal', () => {
  it('renders a structured dossier for quests, companions, NPCs, clues, locations, threats, and decisions', () => {
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
    expect(within(dossier).getAllByText('任务').length).toBeGreaterThanOrEqual(1)
    expect(within(dossier).getByText('寻找失踪矿工')).toBeInTheDocument()
    expect(within(dossier).getAllByText('进行中').length).toBeGreaterThanOrEqual(1)
    expect(within(dossier).getByText('确认矿工是否被带往井底。')).toBeInTheDocument()
    expect(within(dossier).getByText('发现井底拖拽痕迹')).toBeInTheDocument()
    expect(within(dossier).getByText('守住营地')).toBeInTheDocument()
    expect(within(dossier).getAllByText('失败').length).toBeGreaterThanOrEqual(1)
    expect(within(dossier).getByText('狼群冲破外圈，幸存者退入旧矿道。')).toBeInTheDocument()
    expect(within(dossier).getByText('营地被攻破')).toBeInTheDocument()
    expect(within(dossier).getByText('近期')).toBeInTheDocument()
    const timeline = within(dossier).getByLabelText('近期时间线')
    expect(within(timeline).getByText('后果')).toBeInTheDocument()
    expect(within(timeline).getByText('守卫开始巡逻：矿村警戒提高')).toBeInTheDocument()
    expect(within(timeline).getAllByText('任务')).toHaveLength(2)
    expect(within(timeline).getByText('守住营地：营地被攻破')).toBeInTheDocument()
    expect(within(timeline).getByText('寻找失踪矿工：发现井底拖拽痕迹')).toBeInTheDocument()
    expect(within(dossier).getByText('队友')).toBeInTheDocument()
    expect(within(dossier).getByText('艾琳')).toBeInTheDocument()
    expect(within(dossier).getByText('半精灵 · Ranger · Lv 2')).toBeInTheDocument()
    expect(within(dossier).getByText(/冷静的斥候/)).toBeInTheDocument()
    expect(within(dossier).getByText(/HP 15\/18/)).toBeInTheDocument()
    expect(within(dossier).getByText(/说话风格：短句、实用/)).toBeInTheDocument()
    expect(within(dossier).getByText(/战斗偏好：远程压制并保护后排/)).toBeInTheDocument()
    expect(within(dossier).getByText(/口头禅：先看脚印，再拔剑。/)).toBeInTheDocument()
    expect(within(dossier).getByText('关系：信任')).toBeInTheDocument()
    expect(within(dossier).getByText('好感 +18 · 认可')).toBeInTheDocument()
    expect(within(dossier).getByLabelText('艾琳 好感 +18')).toBeInTheDocument()
    expect(within(dossier).getByText(/最近影响：尊重了她的侦察判断/)).toBeInTheDocument()
    expect(within(dossier).getByText('个人任务：月下旧誓')).toBeInTheDocument()
    expect(within(dossier).getAllByText('进行中').length).toBeGreaterThanOrEqual(2)
    expect(within(dossier).getByText('她愿意谈起银叶徽记的来源。')).toBeInTheDocument()
    expect(within(dossier).getByText(/下一步：在安全营地单独交谈。/)).toBeInTheDocument()
    expect(within(dossier).getByText('最近反应')).toBeInTheDocument()
    expect(within(dossier).getByText('我盯着后门，别让他们绕过来。')).toBeInTheDocument()
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

  it('uses the latest role-scoped companion combat log as the dossier reaction', () => {
    const session = makeSession()
    session.logs = [
      ...session.logs,
      {
        id: 'log-companion-2',
        role: 'companion_艾琳',
        log_type: 'combat',
        content: '{"narrative":"我压住左侧通道，先别追太深。"}',
        created_at: '2026-06-01T10:05:00Z',
      },
    ]

    render(
      <JournalModal
        session={session}
        text=""
        loading={false}
        onGenerate={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const dossier = screen.getByLabelText('冒险卷宗')
    expect(within(dossier).getByText('最近反应')).toBeInTheDocument()
    expect(within(dossier).getByText('我压住左侧通道，先别追太深。')).toBeInTheDocument()
    expect(within(dossier).queryByText('我盯着后门，别让他们绕过来。')).not.toBeInTheDocument()
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
