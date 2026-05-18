import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useAsyncStatus } from '../useAsyncStatus'

describe('useAsyncStatus', () => {
  it('wraps async work with loading, success, and error state', async () => {
    const { result } = renderHook(() => useAsyncStatus())
    const work = vi.fn().mockResolvedValue('done')

    await act(async () => {
      await expect(result.current.run(work)).resolves.toBe('done')
    })

    expect(work).toHaveBeenCalled()
    expect(result.current.status).toBe('success')
    expect(result.current.error).toBe('')
  })

  it('stores normalized error messages and rethrows the original error', async () => {
    const { result } = renderHook(() => useAsyncStatus())
    const error = new Error('服务器暂时不可用')

    await act(async () => {
      await expect(result.current.run(async () => { throw error })).rejects.toBe(error)
    })

    expect(result.current.status).toBe('error')
    expect(result.current.error).toBe('服务器暂时不可用')
  })
})
