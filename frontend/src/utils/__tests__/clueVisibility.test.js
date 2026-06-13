import { describe, expect, it } from 'vitest'
import {
  filterPublicClues,
  filterPublicRecentUpdates,
  isPublicClue,
  isPublicRecentUpdate,
} from '../clueVisibility'

describe('clueVisibility', () => {
  it('keeps legacy discovered clues visible by default', () => {
    expect(isPublicClue({ id: 'seen', text: 'Found sigil', is_new: false })).toBe(true)
    expect(filterPublicClues([
      { id: 'seen', text: 'Found sigil' },
      { id: 'also-seen', text: 'Known route', is_new: false },
    ]).map(clue => clue.id)).toEqual(['seen', 'also-seen'])
  })

  it('filters hidden, private, and unrevealed clues', () => {
    const clues = [
      { id: 'visible', text: 'Public clue' },
      { id: 'hidden', text: 'Hidden clue', hidden: true },
      { id: 'dm-only', text: 'DM clue', dmOnly: true },
      { id: 'unrevealed', text: 'Future clue', revealed: false },
      { id: 'private-scope', text: 'Private clue', visibility: { scope: 'private' } },
      { id: 'string-status', text: 'Secret clue', visibility: 'secret' },
    ]

    expect(filterPublicClues(clues).map(clue => clue.id)).toEqual(['visible'])
  })

  it('allows explicit public visibility on scoped visibility objects', () => {
    expect(isPublicClue({
      id: 'party-note',
      text: 'Shared with players',
      visibility: { scope: 'group', public: true },
    })).toBe(true)
  })

  it('rejects blank or non-object clue records', () => {
    expect(filterPublicClues([
      { id: 'blank', text: '   ' },
      'raw clue',
      null,
      { id: 'visible', text: 'Visible clue' },
    ]).map(clue => clue.id)).toEqual(['visible'])
  })

  it('filters hidden clue recent updates against the public clue catalog', () => {
    const clues = [
      { id: 'visible-door', text: 'Visible moon door', category: 'location' },
      { id: 'hidden-vault', text: 'Secret vault under moonwell', category: 'secret', hidden: true },
    ]

    expect(filterPublicRecentUpdates([
      { type: 'quest', label: 'Find the mine' },
      { type: 'clue', clue_id: 'visible-door', label: 'Visible moon door', detail: 'location' },
      { type: 'clue', clue_id: 'hidden-vault', label: 'Secret vault under moonwell', detail: 'secret' },
      { type: 'clue', label: 'Uncatalogued clue', detail: 'unknown' },
    ], clues).map(update => update.label)).toEqual(['Find the mine', 'Visible moon door'])
  })

  it('keeps legacy clue updates when no clue catalog exists unless the update is explicitly hidden', () => {
    expect(isPublicRecentUpdate({ type: 'clue', label: 'Legacy clue update' }, [])).toBe(true)
    expect(isPublicRecentUpdate({ type: 'clue', label: 'Hidden legacy update', hidden: true }, [])).toBe(false)
  })
})
