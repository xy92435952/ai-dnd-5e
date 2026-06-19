import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import RoomActionsPanel from '../RoomActionsPanel'
import RoomAiCompanionsSection from '../RoomAiCompanionsSection'
import RoomMembersGrid from '../RoomMembersGrid'

describe('Room sections', () => {
  it('renders room members and exposes host management callbacks', () => {
    const onTransfer = vi.fn()
    const onKick = vi.fn()

    render(
      <RoomMembersGrid
        members={[
          { user_id: 'me', display_name: '我', role: 'host', character_id: 'c1', character_name: '战士', is_online: true },
          { user_id: 'u2', display_name: '队友', role: 'player', character_id: null, character_name: null, is_online: true },
        ]}
        myUserId="me"
        isHost
        onTransfer={onTransfer}
        onKick={onKick}
      />
    )

    expect(screen.getByText('★ 房主')).toBeInTheDocument()
    const hostCard = screen.getByText('角色：战士').closest('.room-member-card')
    const guestCard = screen.getByText('队友').closest('.room-member-card')
    expect(hostCard).toHaveAttribute('data-online', 'true')
    expect(hostCard.querySelector('.room-member-online-dot')).toBeInTheDocument()
    expect(hostCard.querySelector('.room-member-tag.tag-blue')).toHaveTextContent('我')
    expect(within(hostCard).getByText('角色：战士')).toHaveClass('room-member-meta')
    expect(guestCard).toHaveAttribute('data-online', 'true')
    expect(within(guestCard).getByText('队友')).toHaveClass('room-member-name')
    expect(within(guestCard).getByText('○ 尚未选择角色')).toHaveClass('room-member-meta')
    expect(screen.getByText('角色：战士')).toBeInTheDocument()
    expect(screen.getByText('○ 尚未选择角色')).toBeInTheDocument()

    const transfer = screen.getByRole('button', { name: '转让' })
    const kick = screen.getByRole('button', { name: '发起移出投票' })
    expect(transfer).toHaveClass('room-member-action')
    expect(kick).toHaveClass('room-member-action-danger')
    fireEvent.click(transfer)
    fireEvent.click(kick)
    expect(onTransfer).toHaveBeenCalledWith('u2')
    expect(onKick).toHaveBeenCalledWith('u2')
  })

  it('shows active kick vote progress and disables repeated votes', () => {
    const onKick = vi.fn()

    render(
      <RoomMembersGrid
        members={[
          { user_id: 'me', display_name: '我', role: 'player', character_id: 'c1', character_name: '战士', is_online: true },
          { user_id: 'u2', display_name: '队友', role: 'host', character_id: 'c2', character_name: '法师', is_online: true },
        ]}
        myUserId="me"
        isHost={false}
        roomVotes={[{
          id: 'kick:u2',
          type: 'kick',
          target_user_id: 'u2',
          status: 'open',
          yes_user_ids: ['me'],
          threshold: 2,
        }]}
        onTransfer={vi.fn()}
        onKick={onKick}
      />
    )

    expect(screen.getByText('移出投票：1/2')).toHaveClass('room-member-vote-meta')
    expect(screen.getByRole('button', { name: '已赞成 1/2' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: '转让' })).not.toBeInTheDocument()
  })

  it('renders AI companions without room lifecycle controls', () => {
    render(
      <RoomAiCompanionsSection
        aiCompanions={[
          { id: 'ai-1', name: '布兰', race: 'Human', char_class: 'Cleric', level: 1 },
        ]}
      />
    )

    expect(screen.getByText('布兰')).toBeInTheDocument()
    const aiCard = screen.getByText('布兰').closest('.room-ai-card')
    expect(aiCard.querySelector('.room-ai-body')).toBeInTheDocument()
    expect(within(aiCard).getByText('布兰')).toHaveClass('room-ai-name')
    expect(within(aiCard).getByText('Human · Cleric · Lv1')).toHaveClass('room-ai-meta')
    expect(within(aiCard).getByText('✦ AI')).toHaveClass('room-ai-tag')
  })

  it('keeps room actions wired through explicit callbacks', () => {
    const onCreateChar = vi.fn()
    const onFillAi = vi.fn()
    const onStart = vi.fn()
    const onLeave = vi.fn()

    render(
      <RoomActionsPanel
        isHost
        busy={false}
        canStart
        slotsAvailable={2}
        claimedCount={1}
        memberCount={1}
        myMember={{ user_id: 'me', character_id: null }}
        onCreateChar={onCreateChar}
        onToggleStartReady={vi.fn()}
        onFillAi={onFillAi}
        onStart={onStart}
        onLeave={onLeave}
      />
    )

    const create = screen.getByRole('button', { name: '✦ 创建你的英雄 ✦' })
    const fillAi = screen.getByRole('button', { name: '✦ 召唤 2 位 AI 队友 ✦' })
    const start = screen.getByRole('button', { name: '✦ 开启冒险 ✦' })
    const leave = screen.getByRole('button', { name: '⎋ 离开房间' })
    expect(create.closest('.room-action-row-create')).toBeInTheDocument()
    expect(create).toHaveClass('room-action-button-primary')
    expect(fillAi.closest('.room-action-row-fill-ai')).toBeInTheDocument()
    expect(fillAi).toHaveClass('room-action-button-secondary')
    expect(screen.getByText('根据第一位玩家的职业生成互补角色')).toHaveClass('room-action-hint')
    expect(start.closest('.room-action-row-start')).toBeInTheDocument()
    expect(start).toHaveClass('room-action-button-start')
    expect(start).toHaveAttribute('data-can-start', 'true')
    expect(leave).toHaveClass('room-action-button-leave')

    fireEvent.click(create)
    fireEvent.click(fillAi)
    fireEvent.click(start)
    fireEvent.click(leave)

    expect(onCreateChar).toHaveBeenCalledTimes(1)
    expect(onFillAi).toHaveBeenCalledTimes(1)
    expect(onStart).toHaveBeenCalledTimes(1)
    expect(onLeave).toHaveBeenCalledTimes(1)
  })

  it('blocks room lifecycle actions while lobby sync is reconnecting', () => {
    const onCreateChar = vi.fn()
    const onToggleStartReady = vi.fn()
    const onFillAi = vi.fn()
    const onStart = vi.fn()
    const onLeave = vi.fn()

    render(
      <RoomActionsPanel
        isHost
        busy={false}
        canStart
        slotsAvailable={2}
        claimedCount={2}
        memberCount={2}
        startReadyCount={2}
        isStartReady={false}
        myMember={{ user_id: 'me', character_id: 'c1' }}
        syncBlocked
        syncBlockedReason="房间正在重新同步，请恢复连接后再调整准备、分组或启动冒险。"
        onCreateChar={onCreateChar}
        onToggleStartReady={onToggleStartReady}
        onFillAi={onFillAi}
        onStart={onStart}
        onLeave={onLeave}
      />
    )

    expect(screen.getByText('同步暂停')).toBeInTheDocument()
    expect(screen.getByText('同步暂停').closest('.room-actions-sync-guard')).toBeInTheDocument()
    const ready = screen.getByRole('button', { name: '✦ 确认准备 ✦' })
    const fillAi = screen.getByRole('button', { name: '✦ 召唤 2 位 AI 队友 ✦' })
    const start = screen.getByRole('button', { name: '✦ 开启冒险 ✦' })
    expect(ready).toBeDisabled()
    expect(fillAi).toBeDisabled()
    expect(start).toBeDisabled()

    fireEvent.click(ready)
    fireEvent.click(fillAi)
    fireEvent.click(start)
    fireEvent.click(screen.getByRole('button', { name: '⎋ 离开房间' }))

    expect(onToggleStartReady).not.toHaveBeenCalled()
    expect(onFillAi).not.toHaveBeenCalled()
    expect(onStart).not.toHaveBeenCalled()
    expect(onCreateChar).not.toHaveBeenCalled()
    expect(onLeave).toHaveBeenCalledTimes(1)
  })

  it('blocks host member management while room sync is reconnecting', () => {
    const onTransfer = vi.fn()
    const onKick = vi.fn()

    render(
      <RoomMembersGrid
        members={[
          { user_id: 'me', display_name: '我', role: 'host', character_id: 'c1', character_name: '战士', is_online: true },
          { user_id: 'u2', display_name: '队友', role: 'player', character_id: 'c2', character_name: '法师', is_online: true },
        ]}
        myUserId="me"
        isHost
        disabledHostControls
        disabledReason="房间正在重新同步，请恢复连接后再调整成员。"
        onTransfer={onTransfer}
        onKick={onKick}
      />
    )

    const transfer = screen.getByRole('button', { name: '转让' })
    const kick = screen.getByRole('button', { name: '发起移出投票' })
    expect(transfer).toBeDisabled()
    expect(kick).toBeDisabled()

    fireEvent.click(transfer)
    fireEvent.click(kick)
    expect(onTransfer).not.toHaveBeenCalled()
    expect(onKick).not.toHaveBeenCalled()
  })

  it('keeps start disabled until every room member has claimed a character', () => {
    render(
      <RoomActionsPanel
        isHost
        busy={false}
        canStart={false}
        slotsAvailable={2}
        claimedCount={1}
        memberCount={2}
        myMember={{ user_id: 'me', character_id: 'c1' }}
        onCreateChar={vi.fn()}
        onToggleStartReady={vi.fn()}
        onFillAi={vi.fn()}
        onStart={vi.fn()}
        onLeave={vi.fn()}
      />
    )

    expect(screen.getByRole('button', { name: '✦ 开启冒险 ✦' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '✦ 开启冒险 ✦' })).toHaveAttribute('data-can-start', 'false')
    expect(screen.getByText('1/2 位玩家已认领，所有真人玩家认领后才能开始')).toHaveClass('room-action-start-hint')
  })

  it('lets claimed players toggle their start-ready vote', () => {
    const onToggleStartReady = vi.fn()

    render(
      <RoomActionsPanel
        isHost
        busy={false}
        canStart={false}
        slotsAvailable={0}
        claimedCount={2}
        memberCount={2}
        startReadyCount={1}
        isStartReady={false}
        myMember={{ user_id: 'me', character_id: 'c1' }}
        onCreateChar={vi.fn()}
        onToggleStartReady={onToggleStartReady}
        onFillAi={vi.fn()}
        onStart={vi.fn()}
        onLeave={vi.fn()}
      />
    )

    const ready = screen.getByRole('button', { name: '✦ 确认准备 ✦' })
    expect(ready.closest('.room-action-row-ready')).toBeInTheDocument()
    expect(ready).toHaveClass('room-action-button-ready')
    expect(ready).toHaveAttribute('data-ready', 'false')
    fireEvent.click(ready)
    expect(onToggleStartReady).toHaveBeenCalledWith(true)
    expect(screen.getByText('1/2 位玩家已准备，等待全员确认')).toBeInTheDocument()
  })

  it('shows a stable waiting-for-host state for non-host players', () => {
    render(
      <RoomActionsPanel
        isHost={false}
        busy={false}
        canStart={false}
        slotsAvailable={0}
        claimedCount={1}
        memberCount={2}
        myMember={{ user_id: 'me', character_id: 'c1' }}
        onCreateChar={vi.fn()}
        onToggleStartReady={vi.fn()}
        onFillAi={vi.fn()}
        onStart={vi.fn()}
        onLeave={vi.fn()}
      />
    )

    expect(screen.getByText('~ 等待房主开启冒险 ~')).toHaveClass('room-action-waiting-host')
  })
})
