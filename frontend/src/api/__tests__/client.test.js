import { beforeEach, describe, expect, it, vi } from 'vitest'

const { fakeApi } = vi.hoisted(() => {
  const fakeApi = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  }
  return { fakeApi }
})

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => fakeApi),
  },
}))

import { authApi, charactersApi, gameApi, modulesApi, roomsApi } from '../client'
import { authApi as domainAuthApi } from '../auth'
import { gameApi as domainGameApi } from '../game'
import { modulesApi as domainModulesApi } from '../modules'
import { roomsApi as domainRoomsApi } from '../rooms'

describe('api client domain exports', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps legacy client.js exports wired to the domain modules', () => {
    expect(authApi).toBe(domainAuthApi)
    expect(gameApi).toBe(domainGameApi)
    expect(modulesApi).toBe(domainModulesApi)
    expect(roomsApi).toBe(domainRoomsApi)
  })

  it('preserves key endpoint contracts after splitting client.js', () => {
    gameApi.action({ session_id: 's1', action_text: 'open door' })
    gameApi.attackRoll('s1', 'char-1', 'enemy-1', 'melee', false, 17)
    roomsApi.joinGroup('s1', 'alley', '后巷组', '酒馆后巷')
    charactersApi.updateEquipment('char-1', { weapons: [] })

    expect(fakeApi.post).toHaveBeenCalledWith('/game/action', {
      session_id: 's1',
      action_text: 'open door',
    })
    expect(fakeApi.post).toHaveBeenCalledWith('/game/combat/s1/attack-roll', {
      entity_id: 'char-1',
      target_id: 'enemy-1',
      action_type: 'melee',
      is_offhand: false,
      d20_value: 17,
    })
    expect(fakeApi.post).toHaveBeenCalledWith('/game/rooms/s1/groups/join', {
      group_id: 'alley',
      group_name: '后巷组',
      location: '酒馆后巷',
    })
    expect(fakeApi.patch).toHaveBeenCalledWith('/characters/char-1/equipment-bulk', {
      equipment: { weapons: [] },
    })
  })
})
