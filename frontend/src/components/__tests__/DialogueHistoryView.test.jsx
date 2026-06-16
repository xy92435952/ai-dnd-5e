import { describe, expect, it } from 'vitest'

import { logsToHistoryEntries } from '../DialogueHistoryView'

describe('DialogueHistoryView logsToHistoryEntries', () => {
  it('shows Feather Fall reaction dice from restored DM logs', () => {
    const entries = logsToHistoryEntries([
      {
        id: 'log-1',
        role: 'dm',
        log_type: 'narrative',
        content: 'The pit opens, but the fall slows.',
        dice_result: {
          kind: 'reaction',
          reaction_type: 'feather_fall',
          spell_name: 'Feather Fall',
          slot_level: '1st',
          damage_prevented: 9,
        },
      },
    ])

    expect(entries).toHaveLength(2)
    expect(entries[0]).toMatchObject({
      kind: 'narration',
      txt: 'The pit opens, but the fall slows.',
    })
    expect(entries[1]).toMatchObject({
      kind: 'roll',
      rawText: 'Feather Fall reaction：prevented 9 damage · spent 1st slot',
      result: 'neutral',
    })
  })

  it('preserves DM narration and expands restored dice_result arrays', () => {
    const entries = logsToHistoryEntries([
      {
        id: 'log-1',
        role: 'dm',
        log_type: 'narrative',
        content: 'The hidden pit opens, but the fall slows.',
        dice_result: [
          {
            kind: 'saving_throw',
            label: 'Hidden Pit saving throw',
            raw: 3,
            modifier: 2,
            total: 5,
            dc: 14,
            success: false,
          },
          {
            kind: 'damage',
            label: 'Hidden Pit damage',
            raw: 7,
            total: 0,
          },
          {
            kind: 'reaction',
            reaction_type: 'feather_fall',
            spell_name: 'Feather Fall',
            slot_level: '1st',
            damage_prevented: 7,
          },
        ],
      },
    ])

    expect(entries).toHaveLength(4)
    expect(entries[0]).toMatchObject({
      kind: 'narration',
      txt: 'The hidden pit opens, but the fall slows.',
    })
    expect(entries[1]).toMatchObject({
      kind: 'roll',
      label: 'Hidden Pit saving throw',
      roll: 3,
      mod: 2,
      total: 5,
      dc: 14,
      result: 'failure',
    })
    expect(entries[2]).toMatchObject({
      kind: 'roll',
      label: 'Hidden Pit damage',
      roll: 7,
      mod: null,
      total: 0,
      result: 'neutral',
    })
    expect(entries[3]).toMatchObject({
      kind: 'roll',
      rawText: 'Feather Fall reaction：prevented 7 damage · spent 1st slot',
      result: 'neutral',
    })
  })
})
