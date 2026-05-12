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
    fireEvent.click(screen.getByRole('button', { name: '踢出' }))
    expect(onTransfer).toHaveBeenCalledWith('u2')
    expect(onKick).toHaveBeenCalledWith('u2')
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
        myMember={{ user_id: 'me', character_id: null }}
        onCreateChar={onCreateChar}
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
})
