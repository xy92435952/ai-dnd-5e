import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { TutorialHost } from '../Tutorial'

describe('TutorialHost', () => {
  it('places untargeted coach content in the upper half of the viewport', () => {
    render(<TutorialHost open initialChapter="intro" onClose={() => {}} />)

    const coach = document.querySelector('.tut-coach')
    expect(coach).toBeInTheDocument()
    expect(coach).toHaveTextContent('艾尔德林')
    expect(parseFloat(coach.style.top)).toBeLessThanOrEqual(window.innerHeight * 0.42)
  })
})
