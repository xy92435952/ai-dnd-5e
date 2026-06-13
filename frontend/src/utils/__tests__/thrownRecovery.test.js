import { describe, expect, it } from 'vitest'
import {
  formatThrownRecoverySummary,
  getRecoverableThrownWeapons,
  mergeThrownRecoveryResultIntoSession,
} from '../thrownRecovery'

describe('thrownRecovery', () => {
  it('selects only available thrown weapons for the requested character', () => {
    const session = {
      game_state: {
        thrown_weapon_recovery_pool: {
          items: [
            { id: 'a', character_id: 'hero-1', status: 'available', weapon: 'Javelin', quantity: 1 },
            { id: 'b', character_id: 'hero-1', status: 'recovered', weapon: 'Dagger', quantity: 1 },
            { id: 'c', character_id: 'hero-2', status: 'available', weapon: 'Handaxe', quantity: 2 },
          ],
        },
      },
    }

    expect(getRecoverableThrownWeapons(session, 'hero-1')).toEqual([
      { id: 'a', character_id: 'hero-1', status: 'available', weapon: 'Javelin', quantity: 1 },
    ])
  })

  it('formats recovered weapon summaries', () => {
    expect(formatThrownRecoverySummary([
      { weapon: 'Javelin', quantity: 1 },
      { item: { name: 'Dagger', quantity: 2 } },
    ])).toBe('Javelin x1, Dagger x2')
  })

  it('merges recovery pool and current character equipment into a session snapshot', () => {
    const session = {
      game_state: {
        thrown_weapon_recovery_pool: {
          items: [{ id: 'a', character_id: 'hero-1', status: 'available' }],
        },
      },
      player: {
        id: 'hero-1',
        equipment: { weapons: [] },
      },
      companions: [
        { id: 'ally-1', equipment: { weapons: [] } },
      ],
    }
    const result = {
      character_id: 'hero-1',
      equipment: { weapons: [{ name: 'Javelin', quantity: 2 }] },
      recovery_pool: {
        items: [{ id: 'a', character_id: 'hero-1', status: 'recovered' }],
      },
    }

    expect(mergeThrownRecoveryResultIntoSession(session, result)).toMatchObject({
      game_state: {
        thrown_weapon_recovery_pool: {
          items: [{ id: 'a', status: 'recovered' }],
        },
      },
      player: {
        id: 'hero-1',
        equipment: { weapons: [{ name: 'Javelin', quantity: 2 }] },
      },
      companions: [
        { id: 'ally-1', equipment: { weapons: [] } },
      ],
    })
  })
})
