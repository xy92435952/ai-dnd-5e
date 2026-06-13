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

    expect(screen.getByText(/会更新 DM 的长期战役记忆/)).toBeInTheDocument()
    expect(screen.getByText(/不会回滚 HP、位置、背包、战斗回合或已经写入的日志/)).toBeInTheDocument()

    const summary = screen.getByLabelText('Checkpoint 当前记忆摘要')
    await waitFor(() => {
      expect(within(summary).getByText('任务')).toBeInTheDocument()
      expect(within(summary).getByText('NPC')).toBeInTheDocument()
    })

    const preview = screen.getByLabelText('Checkpoint 会恢复的记忆')
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
    fireEvent.click(screen.getByRole('button', { name: /保存 \/ 更新 checkpoint/ }))

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

    expect(await screen.findByText('档案生成失败')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })
})
