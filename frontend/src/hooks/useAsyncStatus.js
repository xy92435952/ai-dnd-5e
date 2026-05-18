import { useCallback, useState } from 'react'

export function normalizeAsyncError(error, fallback = '请求失败') {
  if (!error) return ''
  if (typeof error === 'string') return error
  if (error.status === 401) return '登录状态已失效，请重新登录。'
  return error.message || fallback
}

export function useAsyncStatus(initialStatus = 'idle') {
  const [status, setStatus] = useState(initialStatus)
  const [error, setErrorState] = useState('')

  const setError = useCallback((value) => {
    setErrorState(normalizeAsyncError(value))
    if (value) setStatus('error')
  }, [])

  const reset = useCallback(() => {
    setStatus('idle')
    setErrorState('')
  }, [])

  const run = useCallback(async (work, { successStatus = 'success' } = {}) => {
    setStatus('loading')
    setErrorState('')
    try {
      const result = await work()
      setStatus(successStatus)
      return result
    } catch (err) {
      setStatus('error')
      setErrorState(normalizeAsyncError(err))
      throw err
    }
  }, [])

  return {
    status,
    setStatus,
    error,
    setError,
    reset,
    run,
    isLoading: status === 'loading',
    isError: status === 'error',
    isSuccess: status === 'success',
  }
}
