import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CharacterCreateStepSkillsGrid from '../CharacterCreateStepSkillsGrid'
import CharacterCreateStepSkillsSummary from '../CharacterCreateStepSkillsSummary'

describe('CharacterCreateStepSkillsSummary', () => {
  it('projects selected skill count and save proficiencies with stable classes', () => {
    const { container } = render(
      <CharacterCreateStepSkillsSummary
        form={{ char_class: 'Fighter' }}
        skillConfig={{ count: 2 }}
        chosenSkills={['运动', '察觉']}
        saveProfs={['str', 'con']}
      />,
    )

    const summary = container.querySelector('.create-skills-summary')
    expect(summary).toHaveClass('create-skills-summary')
    expect(summary).toHaveAttribute('data-complete', 'true')
    expect(summary.querySelector('.create-skills-summary-count')).toHaveTextContent('2')
    expect(summary.querySelector('.create-skills-summary-selected')).toHaveTextContent('2')

    const note = container.querySelector('.create-skills-save-note')
    expect(note).toHaveClass('create-note', 'create-skills-save-note')
    expect(within(note).getByText('职业豁免熟练')).toHaveClass('lead')
    expect(note).toHaveTextContent('力量')
    expect(note).toHaveTextContent('体质')
  })
})

describe('CharacterCreateStepSkillsGrid', () => {
  it('renders selectable skill cards with stable state and isolated detail buttons', () => {
    const toggleSkill = vi.fn()
    const openModal = vi.fn()

    render(
      <CharacterCreateStepSkillsGrid
        skillConfig={{ count: 1, options: ['运动', '察觉'] }}
        chosenSkills={['运动']}
        toggleSkill={toggleSkill}
        openModal={openModal}
      />,
    )

    const list = screen.getByRole('list', { name: 'Skill choices' })
    expect(list).toHaveClass('skill-grid', 'create-skills-grid')

    const athletics = within(list).getByRole('listitem', { name: '运动 力量' })
    const perception = within(list).getByRole('listitem', { name: '察觉 感知' })
    expect(athletics).toHaveClass('skill-card', 'sel')
    expect(athletics).toHaveAttribute('data-selected', 'true')
    expect(athletics).toHaveAttribute('data-disabled', 'false')
    expect(perception).toHaveClass('skill-card', 'dis')
    expect(perception).toHaveAttribute('data-selected', 'false')
    expect(perception).toHaveAttribute('data-disabled', 'true')

    fireEvent.click(athletics)
    expect(toggleSkill).toHaveBeenCalledWith('运动')

    const detailButton = within(perception).getByRole('button', { name: '察觉 details' })
    expect(detailButton).toHaveClass('create-skills-info-button')
    fireEvent.click(detailButton)
    expect(openModal).toHaveBeenCalledWith('skill', '察觉')
    expect(toggleSkill).toHaveBeenCalledTimes(1)
  })
})
