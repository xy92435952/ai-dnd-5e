import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import AdventureQuestHud from '../AdventureQuestHud'

describe('AdventureQuestHud', () => {
  it('renders recent consequences and quest updates after campaign state changes', () => {
    render(
      <AdventureQuestHud
        questLine={{
          quest: '调查暗门',
          status: 'active',
          branch: '井底调查线',
          next_step: '确认井底暗门是否会在月光下开启',
          failure_consequence: '守卫巡逻会提前封锁井口',
          fail_forward: '错过月光窗口后仍可寻找铁匠旧钥匙',
        }}
        clues={[{ text: '暗门在井底', category: 'location', is_new: true }]}
        locationGraph={{
          current_location_id: 'well',
          nodes: [
            { id: 'town', name: '矿村广场', visited: true },
            { id: 'well', name: '矿村井口', visited: true },
          ],
          edges: [{ from: 'town', to: 'well', type: 'discovered' }],
          encounter_templates: [{
            id: 'enc_well',
            location_id: 'well',
            status: 'available',
            name: 'Well Ambush',
            difficulty_hint: 'moderate',
            enemy_names: ['Cave Guard'],
          }],
        }}
        npcUpdates={[]}
        keyDecisions={[]}
        recentConsequences={[
          { type: 'quest', label: '寻找矿工', detail: '矿工获救' },
          { type: 'companion', label: '艾琳', detail: '好感+6' },
          { type: 'clue', label: '暗门在井底', detail: 'location' },
          { type: 'decision', label: '信任铁匠', detail: '关键决定' },
        ]}
      />,
    )

    expect(screen.getByText('调查暗门')).toBeInTheDocument()
    expect(screen.getByText('进行中')).toHaveClass('quest-status-pill', 'active')
    expect(screen.getByText('井底调查线')).toHaveClass('quest-branch-pill')
    expect(screen.getByText('确认井底暗门是否会在月光下开启')).toHaveClass('quest-outcome-snippet', 'active')
    expect(screen.getByText(/地图/)).toBeInTheDocument()
    expect(screen.getByText('矿村井口')).toBeInTheDocument()
    expect(screen.getByText((_, element) => element?.textContent === '2/2')).toBeInTheDocument()
    expect(screen.queryByText('ENC 1')).not.toBeInTheDocument()
    expect(screen.getByText('最近')).toBeInTheDocument()

    const recent = screen.getByText('最近').parentElement
    expect(within(recent).getByText('任务')).toBeInTheDocument()
    expect(within(recent).getByText(/寻找矿工/)).toHaveClass('quest-recent-item', 'quest')
    expect(within(recent).getByText('队友')).toBeInTheDocument()
    expect(within(recent).getByText(/艾琳：好感\+6/)).toHaveClass('quest-recent-item', 'companion')
    expect(within(recent).getByText('线索')).toBeInTheDocument()
    expect(within(recent).getByText(/暗门在井底：location/)).toHaveClass('quest-recent-item', 'clue')
    expect(within(recent).getByText('决定')).toBeInTheDocument()
    expect(within(recent).getByText(/信任铁匠：关键决定/)).toHaveClass('quest-recent-item', 'decision')
  })

  it('surfaces failed quest outcomes as immediate fail-forward context', () => {
    render(
      <AdventureQuestHud
        questLine={{ quest: '守住营地', status: 'failed', outcome: '狼群冲破外圈，幸存者退入旧矿道。' }}
        clues={[]}
      />,
    )

    expect(screen.getByText('守住营地')).toBeInTheDocument()
    expect(screen.getByText('失败')).toHaveClass('quest-status-pill', 'danger')
    expect(screen.getByText('狼群冲破外圈，幸存者退入旧矿道。')).toHaveClass('quest-outcome-snippet', 'danger')
  })
})
