import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import CheckpointModal from '../CheckpointModal'

const getCheckpointMock = vi.hoisted(() => vi.fn())

vi.mock('../../../api/client', () => ({
  gameApi: {
    getCheckpoint: getCheckpointMock,
  },
}))

describe('CheckpointModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('explains what checkpoint memory restores and what it does not restore', async () => {
    getCheckpointMock.mockResolvedValue({
      has_checkpoint: true,
      campaign_state: {
        quest_log: [{ quest: '寻找失踪矿工', status: 'active' }],
        npc_registry: { 铁匠格雷: { relationship: '谨慎盟友' } },
        clues: [
          { text: '暗门在井底' },
          { text: '隐藏金库', hidden: true },
        ],
        completed_scenes: ['矿洞入口'],
        world_flags: { mine_alarm_raised: true },
        key_decisions: ['信任铁匠格雷'],
      },
    })

    render(
      <CheckpointModal
        sessionId="sess-1"
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const scope = screen.getByLabelText('Checkpoint 保存范围')
    expect(within(scope).getByText('会更新')).toBeInTheDocument()
    expect(within(scope).getByText('DM 长期战役记忆')).toBeInTheDocument()
    expect(within(scope).getByText('任务、NPC、线索、地点与世界状态')).toBeInTheDocument()
    expect(within(scope).getByText('不会回滚')).toBeInTheDocument()
    expect(within(scope).getByText('HP、位置、背包或法术位')).toBeInTheDocument()
    expect(within(scope).getByText('战斗回合、临时提示或实时同步状态')).toBeInTheDocument()

    const summary = screen.getByLabelText('Checkpoint 当前记忆摘要')
    await waitFor(() => {
      expect(within(summary).getByText('任务')).toBeInTheDocument()
      expect(within(summary).getByText('NPC')).toBeInTheDocument()
    })

    const preview = screen.getByLabelText('Checkpoint 会恢复的记忆')
    expect(preview).toHaveAttribute('aria-live', 'polite')
    expect(within(preview).getByText(/寻找失踪矿工/)).toBeInTheDocument()
    expect(within(preview).getByText(/铁匠格雷/)).toBeInTheDocument()
    expect(within(preview).getByText('暗门在井底')).toBeInTheDocument()
    expect(within(preview).queryByText('隐藏金库')).not.toBeInTheDocument()
    expect(within(preview).getByText('mine alarm raised')).toBeInTheDocument()
  })

  it('saves checkpoint after explicit confirmation and closes on success', async () => {
    getCheckpointMock.mockResolvedValue({ has_checkpoint: false, campaign_state: {} })
    const onSave = vi.fn().mockResolvedValue({
      ok: true,
      campaign_state: { quest_log: [{ quest: '新任务', status: 'active' }] },
    })
    const onClose = vi.fn()

    render(
      <CheckpointModal
        sessionId="sess-1"
        onSave={onSave}
        onClose={onClose}
      />,
    )

    await screen.findByText(/还没有 checkpoint/)
    const actions = screen.getByRole('group', { name: 'Checkpoint 操作' })
    const saveButton = within(actions).getByRole('button', { name: /保存 \/ 更新 checkpoint/ })
    fireEvent.click(saveButton)
    expect(await screen.findByRole('status')).toHaveTextContent('正在保存 checkpoint 记忆...')

    await waitFor(() => {
      expect(onSave).toHaveBeenCalled()
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('keeps the dialog open and shows an error when save fails', async () => {
    getCheckpointMock.mockResolvedValue({ has_checkpoint: false, campaign_state: {} })
    const onSave = vi.fn().mockRejectedValue(new Error('档案生成失败'))
    const onClose = vi.fn()

    render(
      <CheckpointModal
        sessionId="sess-1"
        onSave={onSave}
        onClose={onClose}
      />,
    )

    await screen.findByText(/还没有 checkpoint/)
    fireEvent.click(screen.getByRole('button', { name: /保存 \/ 更新 checkpoint/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('档案生成失败')
    expect(onClose).not.toHaveBeenCalled()
  })
})
