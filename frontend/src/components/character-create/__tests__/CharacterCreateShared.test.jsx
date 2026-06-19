import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import {
  CharacterCreateField,
  CharacterCreateInfoBtn,
  CharacterCreateSelect,
} from '../CharacterCreateShared'

describe('CharacterCreate shared controls', () => {
  it('renders the info button with stable chrome and preserves click handoff', () => {
    const onClick = vi.fn()
    render(<CharacterCreateInfoBtn onClick={onClick} />)

    const button = screen.getByRole('button', { name: 'ℹ' })
    expect(button).toHaveClass('create-shared-info-button')
    expect(button).toHaveAttribute('title', '查看详情')

    fireEvent.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('renders field labels with stable classes without changing children', () => {
    const { container } = render(
      <CharacterCreateField label="背景（可选）">
        <input aria-label="background child" />
      </CharacterCreateField>,
    )

    const field = container.querySelector('.create-shared-field')
    expect(field).toBeInTheDocument()
    expect(field.querySelector('.create-shared-field-label')).toHaveTextContent('背景（可选）')
    expect(screen.getByLabelText('background child')).toBeInTheDocument()
  })

  it('projects select state through data attributes and preserves onChange payloads', () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <CharacterCreateSelect
        value=""
        options={['守序善良', '中立善良']}
        placeholder="选择阵营"
        onChange={onChange}
      />,
    )

    const placeholderSelect = screen.getByDisplayValue('选择阵营')
    expect(placeholderSelect).toHaveClass('input-fantasy', 'create-shared-select')
    expect(placeholderSelect).toHaveAttribute('data-selected', 'false')

    fireEvent.change(placeholderSelect, { target: { value: '守序善良' } })
    expect(onChange).toHaveBeenCalledWith('守序善良')

    rerender(
      <CharacterCreateSelect
        value="中立善良"
        options={['守序善良', '中立善良']}
        placeholder="选择阵营"
        onChange={onChange}
      />,
    )

    const selected = screen.getByDisplayValue('中立善良')
    expect(selected).toHaveAttribute('data-selected', 'true')
    expect(selected.querySelector('option[value="中立善良"]')).toHaveClass('create-shared-select-option')
  })
})
