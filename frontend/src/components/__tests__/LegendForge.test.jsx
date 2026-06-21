import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import LegendForge from '../LegendForge'

const audioMock = vi.hoisted(() => ({
  unlock: vi.fn(),
  crit: vi.fn(),
  turn: vi.fn(),
}))

vi.mock('../../juice', () => ({
  JuiceAudio: audioMock,
}))

describe('LegendForge', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('renders nothing while closed', () => {
    const { container } = render(<LegendForge open={false} />)

    expect(container.firstChild).toBeNull()
  })

  it('renders crest chrome through stable classes while preserving dynamic ceremony inputs', () => {
    const { container } = render(
      <LegendForge
        open
        name="Mira"
        cls="wizard"
        raceZh="Human"
        classZh="Wizard"
        duration={4200}
      />,
    )

    expect(container.querySelector('.legend-forge')).toBeInTheDocument()
    const crestDisc = container.querySelector('.legend-forge-crest-disc')
    expect(crestDisc).toBeInTheDocument()
    expect(crestDisc).toHaveAttribute('style', '--legend-crest-color: #a070e8;')
    expect(crestDisc.style.width).toBe('')

    const crestGlyph = container.querySelector('.legend-forge-crest-glyph')
    expect(crestGlyph).toBeInTheDocument()
    expect(crestGlyph).not.toHaveAttribute('style')
    expect(screen.getByText('Mira')).toHaveClass('title')
    expect(screen.getByText(/Human/)).toHaveClass('subtitle')

    const sparks = container.querySelectorAll('.sparks span')
    expect(sparks).toHaveLength(24)
    expect(sparks[0].style.getPropertyValue('--legend-spark-angle')).toMatch(/\d+deg/)
    expect(sparks[0].style.getPropertyValue('--legend-spark-distance')).toMatch(/\d+(\.\d+)?px/)
    expect(sparks[0].style.getPropertyValue('--legend-spark-delay')).toMatch(/\d+(\.\d+)?s/)
    expect(sparks[0].style.getPropertyValue('--a')).toBe('')
    expect(sparks[0].style.getPropertyValue('--d')).toBe('')
    expect(sparks[0].style.animationDelay).toBe('')

    expect(audioMock.unlock).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(600)
    expect(audioMock.crit).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(800)
    expect(audioMock.turn).toHaveBeenCalledTimes(1)
  })

  it('calls onDone after the supplied duration', () => {
    const onDone = vi.fn()

    render(<LegendForge open onDone={onDone} duration={1200} />)
    vi.advanceTimersByTime(1199)
    expect(onDone).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    expect(onDone).toHaveBeenCalledTimes(1)
  })
})
