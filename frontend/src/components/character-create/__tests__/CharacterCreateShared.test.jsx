import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import {
  CharacterCreateField,
  CharacterCreateInfoBtn,
  CharacterCreateInfoModal,
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

  it('renders info modal shell with stable classes and preserves close behavior', () => {
    const onClose = vi.fn()
    const { container } = render(
      <CharacterCreateInfoModal type="background" itemKey="Sage" onClose={onClose} />,
    )

    const dialog = screen.getByRole('dialog', { name: '学者' })
    expect(dialog).toHaveClass('create-info-modal-backdrop')
    expect(dialog).toHaveAttribute('aria-modal', 'true')

    const panel = container.querySelector('.create-info-modal-panel')
    expect(panel).toHaveClass('panel')
    expect(screen.getByRole('heading', { name: '学者' })).toHaveClass('create-info-modal-title')

    fireEvent.click(panel)
    expect(onClose).not.toHaveBeenCalled()

    fireEvent.click(dialog)
    expect(onClose).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Close details' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('renders race modal body with stable summary, traits, and note classes', () => {
    const { container } = render(
      <CharacterCreateInfoModal type="race" itemKey="Human" onClose={vi.fn()} />,
    )

    expect(container.querySelector('.create-info-modal-body')).toBeInTheDocument()
    expect(screen.getByText(/人类是人间界最多见/)).toHaveClass('create-info-modal-copy')

    const summary = screen.getByLabelText('Race summary')
    expect(summary).toHaveClass('create-info-modal-tag-row')
    expect(summary).toHaveTextContent('速度 30尺')
    expect(summary).toHaveTextContent('体型 中型')

    expect(screen.getByText('种族特性')).toHaveClass('create-info-modal-section-title')
    const traitList = screen.getByRole('list', { name: 'Race traits' })
    expect(traitList).toHaveClass('create-info-modal-item-list')
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getByText('全能：')).toHaveClass('create-info-modal-item-name')
    expect(screen.getByText(/所有能力值 \+1/)).toHaveClass('create-info-modal-item-copy')
    expect(container.querySelector('.create-info-modal-note-copy')).toHaveTextContent('提示：')
  })

  it('renders class modal body with feature and subclass list semantics', () => {
    render(
      <CharacterCreateInfoModal type="class" itemKey="Fighter" onClose={vi.fn()} />,
    )

    const summary = screen.getByLabelText('Class summary')
    expect(summary).toHaveClass('create-info-modal-tag-row')
    expect(summary).toHaveTextContent('生命骰 d10')
    expect(summary).toHaveTextContent('力量 或 敏捷')
    expect(screen.getByText(/战士是各类武器和战斗风格的大师/)).toHaveClass('create-info-modal-copy')
    expect(screen.getByText(/护甲: 所有盔甲和盾牌/)).toHaveClass('create-info-modal-meta')

    const featureList = screen.getByRole('list', { name: 'Class features' })
    expect(featureList).toHaveClass('create-info-modal-item-list')
    expect(screen.getAllByText('Lv1')[0]).toHaveClass('create-info-modal-level')
    expect(screen.getByText('战斗风格：')).toHaveClass('create-info-modal-item-name')

    const subclassTitle = screen.getByText('武学传承（3级解锁）')
    expect(subclassTitle).toHaveClass('create-info-modal-section-title', 'create-info-modal-section-title-spaced')
    expect(screen.getByRole('list', { name: 'Subclass options' })).toHaveClass('create-info-modal-item-list')
    expect(screen.getByText('斗士：')).toHaveClass('create-info-modal-item-name')
  })

  it('renders skill and background modal body copy without inline chrome contracts', () => {
    const { rerender } = render(
      <CharacterCreateInfoModal type="skill" itemKey="察觉" onClose={vi.fn()} />,
    )

    expect(screen.getByRole('dialog', { name: '察觉（Perception）' })).toBeInTheDocument()
    expect(screen.getByText('关联属性：感知')).toHaveClass('create-info-modal-inline-tag')
    expect(screen.getByText(/利用感官察觉隐藏的事物/)).toHaveClass('create-info-modal-copy')

    rerender(<CharacterCreateInfoModal type="background" itemKey="Sage" onClose={vi.fn()} />)

    expect(screen.getByRole('dialog', { name: '学者' })).toBeInTheDocument()
    expect(screen.getByText(/毕生钻研知识/)).toHaveClass('create-info-modal-copy')
  })
})
