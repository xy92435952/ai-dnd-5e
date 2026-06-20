import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import DMThinkingOverlay from '../DMThinkingOverlay'

describe('DMThinkingOverlay', () => {
  it('does not render while hidden', () => {
    const { container } = render(<DMThinkingOverlay visible={false} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('renders fate weave indexes through classes without inline style', () => {
    const { container } = render(<DMThinkingOverlay visible />)

    expect(screen.getByLabelText('地下城主正在编织命运')).toHaveClass('dm-thinking-overlay')

    const lines = Array.from(container.querySelectorAll('.fate-lines .fate-line'))
    expect(lines).toHaveLength(8)
    lines.forEach((line, index) => {
      expect(line).toHaveClass('fate-line', `fate-line-${index + 1}`)
      expect(line).not.toHaveAttribute('style')
    })

    const nodes = Array.from(container.querySelectorAll('.fate-orbit .orbit-node'))
    expect(nodes).toHaveLength(8)
    nodes.forEach((node, index) => {
      expect(node).toHaveClass('orbit-node', `orbit-node-${index + 1}`)
      expect(node).not.toHaveAttribute('style')
    })
  })
})
