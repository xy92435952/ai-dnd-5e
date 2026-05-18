import { afterEach, describe, expect, it, vi } from 'vitest'

import { rollDiceBoxWithTimeout } from '../DiceRollerOverlay'

vi.mock('@3d-dice/dice-box', () => ({
  default: class MockDiceBox {},
}))

describe('rollDiceBoxWithTimeout', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('falls back to a numeric roll if the 3D dice library never settles', async () => {
    vi.useFakeTimers()
    const box = {
      clear: vi.fn(),
      roll: vi.fn(() => new Promise(() => {})),
      _onSettled: null,
    }

    const rollPromise = rollDiceBoxWithTimeout(box, 20, 1, 8000)
    await Promise.resolve()
    vi.advanceTimersByTime(8100)

    await expect(rollPromise).resolves.toMatchObject({
      total: expect.any(Number),
      rolls: expect.arrayContaining([expect.any(Number)]),
    })
    expect(box.clear).toHaveBeenCalled()
    expect(box._onSettled).toBeNull()
  })
})
