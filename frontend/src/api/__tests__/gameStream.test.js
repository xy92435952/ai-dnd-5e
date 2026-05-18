import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createSseParser, gameApi } from '../game'

function makeStreamResponse(chunks, { ok = true, status = 200 } = {}) {
  const encoder = new TextEncoder()
  let index = 0
  return {
    ok,
    status,
    text: vi.fn(async () => chunks.join('')),
    body: {
      getReader: () => ({
        read: vi.fn(async () => {
          if (index >= chunks.length) return { done: true, value: undefined }
          return { done: false, value: encoder.encode(chunks[index++]) }
        }),
      }),
    },
  }
}

describe('gameApi action streaming', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('parses SSE frames split across chunks', () => {
    const events = []
    const parser = createSseParser((event) => events.push(event))

    parser.feed('event: narrative_delta\ndata: {"text":"雾')
    parser.feed('气"}\n\nevent: final\ndata: {"narrative":"雾气"}\n\n')
    parser.flush()

    expect(events).toEqual([
      { event: 'narrative_delta', data: { text: '雾气' } },
      { event: 'final', data: { narrative: '雾气' } },
    ])
  })

  it('streams action narrative deltas and returns the final payload', async () => {
    localStorage.setItem('token', 'token-1')
    fetch.mockResolvedValue(makeStreamResponse([
      'event: narrative_delta\ndata: {"text":"雾"}\n\n',
      'event: narrative_delta\ndata: {"text":"散"}\n\n',
      'event: final\ndata: {"type":"investigation","narrative":"雾散"}\n\n',
    ]))
    const deltas = []
    const events = []

    const final = await gameApi.actionStream(
      { session_id: 's1', action_text: '检查门' },
      {
        onNarrativeDelta: (text) => deltas.push(text),
        onEvent: (event) => events.push(event.event),
      },
    )

    expect(fetch).toHaveBeenCalledWith('/api/game/action/stream', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({
        Authorization: 'Bearer token-1',
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify({ session_id: 's1', action_text: '检查门' }),
    }))
    expect(deltas).toEqual(['雾', '散'])
    expect(events).toContain('final')
    expect(final).toEqual({ type: 'investigation', narrative: '雾散' })
  })
})
