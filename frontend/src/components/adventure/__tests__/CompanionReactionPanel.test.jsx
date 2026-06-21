import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import CompanionReactionPanel from '../CompanionReactionPanel'

describe('CompanionReactionPanel', () => {
  it('renders nothing when hidden or when no reaction has text', () => {
    const { container, rerender } = render(
      <CompanionReactionPanel
        visible={false}
        reactions={[{ speaker: '艾莉', text: '我盯着后门。' }]}
      />,
    )

    expect(container).toBeEmptyDOMElement()

    rerender(
      <CompanionReactionPanel
        reactions={[
          null,
          { speaker: '艾莉' },
          { speaker: '博恩', text: '' },
        ]}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('renders companion reactions as a named polite list with stable classes', () => {
    render(
      <CompanionReactionPanel
        reactions={[
          { speaker: '艾莉', text: '我盯着 **后门**。' },
          { text: '*保持* 队形。' },
          { speaker: '忽略空项' },
        ]}
      />,
    )

    const panel = screen.getByRole('complementary', { name: '队友反应' })
    expect(panel).toHaveClass('companion-reaction-panel')
    expect(panel).toHaveAttribute('aria-live', 'polite')
    expect(within(panel).getByText('队友反应')).toHaveClass('companion-reaction-title')

    const list = within(panel).getByRole('list', { name: '队友反应列表' })
    expect(list).toHaveClass('companion-reaction-list')

    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveClass('companion-reaction-item')
    expect(items[1]).toHaveClass('companion-reaction-item')
    expect(within(items[0]).getByText('艾莉：')).toHaveClass('companion-reaction-speaker')
    expect(within(items[1]).getByText('队友：')).toHaveClass('companion-reaction-speaker')
    const strongText = within(items[0]).getByText('后门')
    expect(strongText).toHaveClass('light-md-strong')
    expect(strongText.style.getPropertyValue('--light-md-accent-color')).toBe('#a8f0c0')
    expect(strongText.style.fontWeight).toBe('')

    const emphasisText = within(items[1]).getByText('保持')
    expect(emphasisText).toHaveClass('light-md-em')
    expect(emphasisText).not.toHaveAttribute('style')
    expect(screen.queryByText('忽略空项')).not.toBeInTheDocument()
  })
})
