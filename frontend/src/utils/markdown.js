/**
 * 轻量 markdown 渲染 —— 只支持 **bold** 和 *italic*
 * =====================================================
 * 专为 DM 对话气泡 / 日志 / 历史回看设计。
 * 不引入完整 markdown lib（如 react-markdown）因为：
 *   - 整个项目风格定制化严重，完整 md 容易破坏布局
 *   - 对话场景只需 bold 强调关键概念
 *
 * 安全性：返回的是 React 片段数组（非 dangerouslySetInnerHTML），
 * 不会执行脚本。
 *
 * 打字机半路兼容：若遇到没闭合的 **delim**，原样输出星号，
 * 等打字完成、全部字符到位后会自动变粗。
 */
import React from 'react'

export function renderLightMarkdown(text, accentColor = 'var(--amber)') {
  if (!text) return null
  const parts = []
  // **bold**（非贪婪最短）或 *italic*（不跨空格，不紧邻星号）
  const pattern = /(\*\*(.+?)\*\*|\*([^\s*][^*]*?)\*)/
  let remaining = String(text)
  let key = 0
  let safety = 0
  while (remaining && safety++ < 500) {
    const m = pattern.exec(remaining)
    if (!m) {
      parts.push(remaining)
      break
    }
    const before = remaining.slice(0, m.index)
    if (before) parts.push(before)
    if (m[2] != null) {
      parts.push(
        React.createElement(
          'strong',
          { key: `b-${key++}`, style: { color: accentColor, fontWeight: 700, fontStyle: 'normal' } },
          m[2]
        )
      )
    } else if (m[3] != null) {
      parts.push(
        React.createElement(
          'em',
          { key: `i-${key++}`, style: { fontStyle: 'italic' } },
          m[3]
        )
      )
    }
    remaining = remaining.slice(m.index + m[0].length)
  }
  return parts
}

export default renderLightMarkdown
