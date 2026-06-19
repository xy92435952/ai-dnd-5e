import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { roomsApi } from '../../../api/client'
import MultiplayerPartyPanel from '../MultiplayerPartyPanel'

vi.mock('../../../api/client', () => ({
  roomsApi: {
    submitGroupAction: vi.fn(),
    joinGroup: vi.fn(),
    focusGroup: vi.fn(),
    setGroupReadiness: vi.fn(),
  },
}))

describe('MultiplayerPartyPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    roomsApi.submitGroupAction.mockResolvedValue({ is_multiplayer: true })
    roomsApi.joinGroup.mockResolvedValue({ is_multiplayer: true })
    roomsApi.focusGroup.mockResolvedValue({ is_multiplayer: true })
    roomsApi.setGroupReadiness.mockResolvedValue({ is_multiplayer: true, group_readiness: { alley: { me: 'ready' } } })
  })

  it('shows an explicit active camera hint when focus moved to another ready group', () => {
    render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: true,
        session_id: 'sess-1',
        active_group_id: 'tavern',
        members: [
          { user_id: 'me', display_name: '我' },
          { user_id: 'u2', display_name: '凯伦' },
        ],
        party_groups: [
          { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me'] },
          { id: 'tavern', name: '酒馆组', location: '酒馆大厅', member_user_ids: ['u2'] },
        ],
        pending_actions_by_group: {
          alley: [],
          tavern: [{ user_id: 'u2', display_name: '凯伦', text: '我继续套老板的话。' }],
        },
        group_readiness: {
          alley: { me: 'drafting' },
          tavern: { u2: 'ready' },
        },
      }}
      myUserId="me"
      isMySpeakTurn={false}
      isLoading={false}
    />)

    expect(screen.getByRole('region', { name: '分队协作面板' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: '当前分队状态' })).toHaveTextContent('后巷组')
    expect(screen.getByLabelText('当前镜头状态')).toHaveTextContent('酒馆大厅')
    expect(screen.getByRole('group', { name: '分队切换' })).toHaveTextContent('焦点 · 酒馆组')
    expect(screen.getByRole('group', { name: '分队确认操作' })).toHaveTextContent('我的状态：草拟中')
    expect(screen.getByRole('group', { name: '分队意图提交' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: '创建或切换分队' })).toBeInTheDocument()
    expect(screen.getByText('当前镜头：酒馆组')).toBeInTheDocument()
    expect(screen.getByText('下一处理：酒馆组 · 1 条待处理 · 全员已确认')).toBeInTheDocument()
    expect(screen.getByLabelText('DM处理提示')).toHaveTextContent('当前镜头「酒馆组」已全员确认，等待当前发言者处理 1 条意图')
    expect(screen.queryByText('主持')).not.toBeInTheDocument()
  })

  it('shows my submitted intent and group readiness feedback', () => {
    render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: true,
        session_id: 'sess-1',
        active_group_id: 'alley',
        members: [
          { user_id: 'me', display_name: '我' },
          { user_id: 'u2', display_name: '凯伦' },
        ],
        party_groups: [
          { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me', 'u2'] },
        ],
        pending_actions_by_group: {
          alley: [
            { user_id: 'me', display_name: '我', text: '我守住后门。' },
            { user_id: 'u2', display_name: '凯伦', text: '我检查脚印。' },
          ],
        },
        group_readiness: {
          alley: { me: 'ready', u2: 'drafting' },
        },
      }}
      myUserId="me"
      isMySpeakTurn={false}
      isLoading={false}
    />)

    expect(screen.getByText('你已提交意图 · 等当前发言者带给 DM')).toBeInTheDocument()
    expect(screen.getByText('确认进度：1/2 已确认')).toBeInTheDocument()
    const readinessDetail = screen.getByLabelText('分队确认详情')
    expect(readinessDetail).toHaveTextContent('未确认：凯伦')
    expect(readinessDetail).toHaveTextContent('已确认：我')
    expect(readinessDetail).toHaveTextContent('继续草拟：凯伦')
    expect(readinessDetail.querySelector('[title="未确认：凯伦"]')).toHaveAttribute('data-tone', 'urgent')
    expect(readinessDetail.querySelector('[title="已确认：我"]')).toHaveAttribute('data-tone', 'ready')
    expect(readinessDetail.querySelector('[title="继续草拟：凯伦"]')).toHaveAttribute('data-tone', 'drafting')
    const prompt = screen.getByLabelText('分队确认提示')
    expect(prompt).toHaveAttribute('data-tone', 'pending')
    expect(prompt).toHaveTextContent('确认提示')
    expect(prompt).toHaveTextContent('等待凯伦确认当前分队计划。')
    expect(screen.getByRole('list', { name: '分队待处理意图' })).toHaveTextContent('我：我守住后门。')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText(/我守住后门。/)).toBeInTheDocument()
  })

  it('prompts me to confirm after submitting an intent while still drafting', () => {
    render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: true,
        session_id: 'sess-1',
        active_group_id: 'alley',
        members: [
          { user_id: 'me', display_name: '我' },
          { user_id: 'u2', display_name: '凯伦' },
        ],
        party_groups: [
          { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me', 'u2'] },
        ],
        pending_actions_by_group: {
          alley: [
            { user_id: 'me', display_name: '我', text: '我检查门锁。' },
          ],
        },
        group_readiness: {
          alley: { me: 'drafting', u2: 'ready' },
        },
      }}
      myUserId="me"
      isMySpeakTurn={false}
      isLoading={false}
    />)

    expect(screen.getByText('你已提交意图 · 点“我已确认”后 DM 才会处理')).toBeInTheDocument()
    const prompt = screen.getByLabelText('分队确认提示')
    expect(prompt).toHaveAttribute('data-tone', 'urgent')
    expect(prompt).toHaveTextContent('确认提示')
    expect(prompt).toHaveTextContent('你提交了意图，但这轮分队计划仍是草拟状态；点“我已确认”后 DM 才会处理。')
    expect(screen.getByRole('button', { name: /我已确认/ })).not.toBeDisabled()
  })

  it('warns when a revised group intent resets everyone to drafting', () => {
    render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: true,
        session_id: 'sess-1',
        active_group_id: 'alley',
        members: [
          { user_id: 'me', display_name: '我' },
          { user_id: 'u2', display_name: '凯伦' },
        ],
        party_groups: [
          { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me', 'u2'] },
        ],
        pending_actions_by_group: {
          alley: [
            { user_id: 'u2', display_name: '凯伦', text: '我改为守住楼梯。' },
          ],
        },
        group_readiness: {
          alley: { me: 'drafting', u2: 'drafting' },
        },
      }}
      myUserId="me"
      isMySpeakTurn={false}
      isLoading={false}
    />)

    expect(screen.getByLabelText('分队确认提示')).toHaveTextContent('需重新确认')
    expect(screen.getByLabelText('分队确认提示')).toHaveTextContent('分队计划已更新，全队确认被重置；请确认当前意图或继续补充。')
  })

  it('tells the active speaker how many group intents will be aggregated', () => {
    render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: true,
        session_id: 'sess-1',
        active_group_id: 'alley',
        members: [
          { user_id: 'me', display_name: '我' },
          { user_id: 'u2', display_name: '凯伦' },
        ],
        party_groups: [
          { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me', 'u2'] },
        ],
        pending_actions_by_group: {
          alley: [
            { user_id: 'me', display_name: '我', text: '我守住后门。' },
            { user_id: 'u2', display_name: '凯伦', text: '我检查脚印。' },
          ],
        },
        group_readiness: {
          alley: { me: 'ready', u2: 'ready' },
        },
      }}
      myUserId="me"
      isMySpeakTurn
      isLoading={false}
    />)

    expect(screen.getByText('你是当前发言者 · DM 会汇总本分队 2 条意图')).toBeInTheDocument()
    expect(screen.getByText('确认进度：2/2 已确认')).toBeInTheDocument()
    expect(screen.getByLabelText('DM处理提示')).toHaveTextContent('你的主行动会汇总当前镜头「后巷组」的 2 条意图')
  })

  it('clarifies when my speaking group differs from the current camera', () => {
    render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: true,
        session_id: 'sess-1',
        active_group_id: 'tavern',
        members: [
          { user_id: 'me', display_name: '我' },
          { user_id: 'u2', display_name: '凯伦' },
        ],
        party_groups: [
          { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me'] },
          { id: 'tavern', name: '酒馆组', location: '酒馆大厅', member_user_ids: ['u2'] },
        ],
        pending_actions_by_group: {
          alley: [
            { user_id: 'me', display_name: '我', text: '我守住后门。' },
          ],
        },
        group_readiness: {
          alley: { me: 'ready' },
          tavern: { u2: 'drafting' },
        },
      }}
      myUserId="me"
      isMySpeakTurn
      isLoading={false}
    />)

    expect(screen.getByText('当前镜头：酒馆组')).toBeInTheDocument()
    expect(screen.getByLabelText('DM处理提示')).toHaveTextContent('你的主行动会汇总「后巷组」的 1 条意图；当前镜头仍在「酒馆组」')
  })

  it('can submit an intent and confirm it in one explicit action', async () => {
    const onRoomUpdated = vi.fn()
    const finalRoom = { is_multiplayer: true, group_readiness: { alley: { me: 'ready' } } }
    roomsApi.submitGroupAction.mockResolvedValue({ is_multiplayer: true, pending_actions_by_group: { alley: [] } })
    roomsApi.setGroupReadiness.mockResolvedValue(finalRoom)

    render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: true,
        session_id: 'sess-1',
        active_group_id: 'alley',
        members: [
          { user_id: 'me', display_name: '我' },
          { user_id: 'u2', display_name: '凯伦' },
        ],
        party_groups: [
          { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me', 'u2'] },
        ],
        pending_actions_by_group: { alley: [] },
        group_readiness: { alley: { me: 'drafting', u2: 'ready' } },
      }}
      myUserId="me"
      isMySpeakTurn={false}
      isLoading={false}
      onRoomUpdated={onRoomUpdated}
    />)

    const input = screen.getByPlaceholderText(/先提交你的分队行动/)
    fireEvent.change(input, { target: { value: '我检查门锁。' } })
    fireEvent.click(screen.getByRole('button', { name: '提交并确认' }))

    await waitFor(() => {
      expect(roomsApi.submitGroupAction).toHaveBeenCalledWith('sess-1', 'alley', '我检查门锁。')
      expect(roomsApi.setGroupReadiness).toHaveBeenCalledWith('sess-1', 'alley', 'ready')
    })
    expect(roomsApi.submitGroupAction.mock.invocationCallOrder[0])
      .toBeLessThan(roomsApi.setGroupReadiness.mock.invocationCallOrder[0])
    expect(onRoomUpdated).toHaveBeenLastCalledWith(finalRoom)
    expect(input).toHaveValue('')
  })

  it('preserves Chinese group names when creating a split-party group', async () => {
    render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: true,
        session_id: 'sess-1',
        active_group_id: 'main',
        members: [
          { user_id: 'me', display_name: '我' },
          { user_id: 'u2', display_name: '凯伦' },
        ],
        party_groups: [
          { id: 'main', name: '主队', location: '酒馆大厅', member_user_ids: ['me', 'u2'] },
        ],
        pending_actions_by_group: { main: [] },
        group_readiness: { main: { me: 'drafting', u2: 'ready' } },
      }}
      myUserId="me"
      isMySpeakTurn={false}
      isLoading={false}
    />)

    fireEvent.change(screen.getByPlaceholderText('新分队名'), { target: { value: '后巷组' } })
    fireEvent.change(screen.getByPlaceholderText('位置'), { target: { value: '酒馆后巷' } })
    fireEvent.click(screen.getByRole('button', { name: '切换/创建分队' }))

    await waitFor(() => {
      expect(roomsApi.joinGroup).toHaveBeenCalledWith('sess-1', '后巷组', '后巷组', '酒馆后巷')
    })
  })

  it('blocks room mutation controls while multiplayer sync is reconnecting', () => {
    render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: true,
        session_id: 'sess-1',
        active_group_id: 'alley',
        members: [
          { user_id: 'me', display_name: '我' },
          { user_id: 'u2', display_name: '凯伦' },
        ],
        party_groups: [
          { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me'] },
          { id: 'tavern', name: '酒馆组', location: '酒馆大厅', member_user_ids: ['u2'] },
        ],
        pending_actions_by_group: { alley: [] },
        group_readiness: { alley: { me: 'drafting' }, tavern: { u2: 'ready' } },
      }}
      myUserId="me"
      isMySpeakTurn={false}
      isLoading={false}
      syncBlocked
      syncBlockedReason="房间正在重新同步，请恢复连接后再发言。"
    />)

    expect(screen.getByRole('status')).toHaveTextContent('同步暂停')
    expect(screen.getByText('房间正在重新同步，请恢复连接后再发言。')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/先提交你的分队行动/)).toBeDisabled()
    expect(screen.getByPlaceholderText('新分队名')).toBeDisabled()
    expect(screen.getByPlaceholderText('位置')).toBeDisabled()
    expect(screen.getByRole('button', { name: /切焦点 · 酒馆组/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: '我已确认' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '提交意图' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '切换/创建分队' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '我已确认' }))
    expect(roomsApi.setGroupReadiness).not.toHaveBeenCalled()
  })

  it('stays hidden for single-player sessions', () => {
    const { container } = render(<MultiplayerPartyPanel
      room={{
        is_multiplayer: false,
        session_id: 'sess-1',
        active_group_id: 'main',
        members: [{ user_id: 'me', display_name: '我' }],
        party_groups: [
          { id: 'main', name: '单人队伍', location: '大厅', member_user_ids: ['me'] },
        ],
      }}
      myUserId="me"
      isMySpeakTurn={true}
      isLoading={false}
    />)

    expect(container).toBeEmptyDOMElement()
  })
})
