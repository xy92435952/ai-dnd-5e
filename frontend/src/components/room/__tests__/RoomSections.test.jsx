import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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
    expect(screen.getByText('角色：战士')).toBeInTheDocument()
    expect(screen.getByText('○ 尚未选择角色')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '转让' }))
    fireEvent.click(screen.getByRole('button', { name: '发起移出投票' }))
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

    expect(screen.getByText('移出投票：1/2')).toBeInTheDocument()
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
    expect(screen.getByText('Human · Cleric · Lv1')).toBeInTheDocument()
    expect(screen.getByText('✦ AI')).toBeInTheDocument()
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

    fireEvent.click(screen.getByRole('button', { name: '✦ 创建你的英雄 ✦' }))
    fireEvent.click(screen.getByRole('button', { name: '✦ 召唤 2 位 AI 队友 ✦' }))
    fireEvent.click(screen.getByRole('button', { name: '✦ 开启冒险 ✦' }))
    fireEvent.click(screen.getByRole('button', { name: '⎋ 离开房间' }))

    expect(onCreateChar).toHaveBeenCalledTimes(1)
    expect(onFillAi).toHaveBeenCalledTimes(1)
    expect(onStart).toHaveBeenCalledTimes(1)
    expect(onLeave).toHaveBeenCalledTimes(1)
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
    expect(screen.getByText('1/2 位玩家已认领，所有真人玩家认领后才能开始')).toBeInTheDocument()
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

    fireEvent.click(screen.getByRole('button', { name: '✦ 确认准备 ✦' }))
    expect(onToggleStartReady).toHaveBeenCalledWith(true)
    expect(screen.getByText('1/2 位玩家已准备，等待全员确认')).toBeInTheDocument()
  })
})
