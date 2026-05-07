import { useCallback, useEffect, useRef, useState } from 'react'

export function useCombatLog(initialLogs = []) {
  const [logs, setLogs] = useState(initialLogs)
  const logsEndRef = useRef(null)

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const addLog = useCallback((entry) => {
    setLogs(prev => [...prev, { id: `log-${Date.now()}-${Math.random()}`, ...entry }])
  }, [])

  return {
    logs,
    setLogs,
    addLog,
    logsEndRef,
  }
}
