/**
 * useDialogueFlow — 剧场模式对话流的状态机。
 *
 * 原位：Adventure.jsx 里 dialogueMode / dialogueQueue / dialogueIdx /
 * typingText / typingDone / typingTimerRef + 2 个 useEffect + advanceDialogue。
 *
 * 抽出后 Adventure 只需：
 *   const dialogue = useDialogueFlow({ addLog })
 *   // 有新剧场内容要播 → dialogue.enterStage(queue)
 *   // UI 点击气泡 → dialogue.advance()
 *   // 渲染时读 dialogue.dialogueMode / typingText / ... 即可
 *
 * 状态机：
 *   chat  →  enterStage(queue) → stage（打字机从 idx=0 开始）
 *   stage 中 advance() → 当前段入 log，dialogueIdx+=1 或回到 chat
 *
 * 打字机分级：
 *   ≤ 60 字：30ms / 字（正常）
 *   60-150 字：18ms / 字（加速）
 *   > 150 字：整段淡入（避免长叙述让玩家干等）
 *
 * @param {{ addLog: (role:string, content:string, logType?:string, extra?:object) => void }} deps
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export function useDialogueFlow({ addLog }) {
  const [dialogueMode, setDialogueMode] = useState('chat')   // 'chat' | 'stage'
  const [showHistory,  setShowHistory]  = useState(false)    // 对话史册视图独立开关
  const [dialogueQueue, setDialogueQueue] = useState([])     // {speaker, role, text}[]
  const [dialogueIdx, setDialogueIdx]   = useState(0)
  const [typingText,  setTypingText]    = useState('')
  const [typingDone,  setTypingDone]    = useState(true)
  const typingTimerRef = useRef(null)

  // 启动剧场模式。外部构造好 queue 后调这个。
  const enterStage = useCallback((queue) => {
    if (!Array.isArray(queue) || queue.length === 0) return
    setDialogueQueue(queue)
    setDialogueIdx(0)
    setDialogueMode('stage')
  }, [])

  // 打字机效果：每当 idx / queue 变化逐字显示当前段
  useEffect(() => {
    if (dialogueMode !== 'stage') return
    if (dialogueIdx >= dialogueQueue.length) return
    const seg = dialogueQueue[dialogueIdx]
    if (!seg) return
    setTypingText('')
    setTypingDone(false)
    const full = seg.text || ''
    const len = full.length

    // 极长文本：不走打字机，下一帧直接显示完整内容（靠 CSS 淡入）
    if (len > 150) {
      typingTimerRef.current = setTimeout(() => {
        setTypingText(full)
        setTypingDone(true)
      }, 60)
      return () => { if (typingTimerRef.current) clearTimeout(typingTimerRef.current) }
    }

    const interval = len > 60 ? 18 : 30
    let i = 0
    const step = () => {
      i += 1
      setTypingText(full.slice(0, i))
      if (i >= len) {
        setTypingDone(true)
        return
      }
      typingTimerRef.current = setTimeout(step, interval)
    }
    typingTimerRef.current = setTimeout(step, 60)
    return () => { if (typingTimerRef.current) clearTimeout(typingTimerRef.current) }
  }, [dialogueMode, dialogueIdx, dialogueQueue])

  // 推进：点击气泡 / 按空格 / 按回车
  const advance = useCallback(() => {
    if (dialogueMode !== 'stage') return
    // 字没打完 → 立即打完
    if (!typingDone) {
      if (typingTimerRef.current) clearTimeout(typingTimerRef.current)
      const seg = dialogueQueue[dialogueIdx]
      setTypingText(seg?.text || '')
      setTypingDone(true)
      return
    }
    // 字已打完 → 当前段入 log，推进下一段
    const seg = dialogueQueue[dialogueIdx]
    if (seg) addLog(seg.role, seg.text, seg.role === 'dm' ? 'narrative' : seg.role)
    const next = dialogueIdx + 1
    if (next >= dialogueQueue.length) {
      // 队列播完 → 回到聊天模式
      setDialogueMode('chat')
      setDialogueQueue([])
      setDialogueIdx(0)
      setTypingText('')
      setTypingDone(true)
    } else {
      setDialogueIdx(next)
    }
  }, [dialogueMode, dialogueIdx, dialogueQueue, typingDone, addLog])

  // 空格 / 回车推进
  useEffect(() => {
    if (dialogueMode !== 'stage') return
    const onKey = (e) => {
      if (e.code === 'Space' || e.code === 'Enter') {
        e.preventDefault()
        advance()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dialogueMode, advance])

  return {
    // 状态
    dialogueMode,
    dialogueQueue,
    dialogueIdx,
    typingText,
    typingDone,
    showHistory,
    // 动作
    enterStage,
    advance,
    setShowHistory,
    // 仅兜底场景使用（一般不需要）
    setDialogueMode,
  }
}
