import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ReactionPrompt from '../ReactionPrompt'

describe('ReactionPrompt', () => {
  it('maps backend available_reactions into clickable reaction actions', async () => {
    const onReact = vi.fn()
    render(
      <ReactionPrompt
        currentCharacterId="char-2"
        prompt={{
          context: 'Incoming attack',
          attacker_id: 'enemy-1',
          reactor_character_id: 'char-2',
          available_reactions: [
            {
              id: 'hellish_rebuke',
              type: 'hellish_rebuke',
              name: 'Hellish Rebuke',
              effect: 'Deal fire damage',
            },
          ],
        }}
        onReact={onReact}
        onCancel={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Hellish Rebuke/ }))

    expect(onReact).toHaveBeenCalledWith('hellish_rebuke', 'enemy-1', 'char-2')
  })

  it('prefers reaction id when backend type is generic', async () => {
    const onReact = vi.fn()
    render(
      <ReactionPrompt
        currentCharacterId="char-2"
        prompt={{
          context: 'Incoming spell',
          target_id: 'enemy-mage',
          reactor_character_id: 'char-2',
          available_reactions: [
            {
              id: 'counterspell',
              type: 'spell',
              name: 'Counterspell',
              effect: 'Cancel the spell',
            },
          ],
        }}
        onReact={onReact}
        onCancel={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Counterspell/ }))

    expect(onReact).toHaveBeenCalledWith('counterspell', 'enemy-mage', 'char-2')
  })

  it('passes Absorb Elements actions through from available reactions', async () => {
    const onReact = vi.fn()
    render(
      <ReactionPrompt
        currentCharacterId="char-2"
        prompt={{
          context: 'Incoming fire damage',
          attacker_id: 'enemy-1',
          reactor_character_id: 'char-2',
          available_reactions: [
            {
              id: 'absorb_elements',
              type: 'absorb_elements',
              name: 'Absorb Elements',
              effect: 'Reduce fire damage',
            },
          ],
        }}
        onReact={onReact}
        onCancel={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Absorb Elements/ }))

    expect(onReact).toHaveBeenCalledWith('absorb_elements', 'enemy-1', 'char-2')
  })

  it('passes the prompt back when cancelling a reaction window', async () => {
    const prompt = {
      trigger: 'spell_cast',
      context: 'Incoming spell',
      target_id: 'enemy-mage',
      reactor_character_id: 'char-2',
      available_reactions: [],
    }
    const onCancel = vi.fn()
    render(
      <ReactionPrompt
        currentCharacterId="char-2"
        prompt={prompt}
        onReact={vi.fn()}
        onCancel={onCancel}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /放弃|鏀惧純/ }))

    expect(onCancel).toHaveBeenCalledWith(prompt)
  })

  it('explains when an eligible reactor has no usable reaction option', () => {
    const prompt = {
      trigger: 'incoming_attack',
      context: 'Incoming attack',
      attacker_id: 'enemy-1',
      reactor_character_id: 'char-2',
      available_reactions: [],
    }
    const onReact = vi.fn()
    const onCancel = vi.fn()

    render(
      <ReactionPrompt
        currentCharacterId="char-2"
        prompt={prompt}
        onReact={onReact}
        onCancel={onCancel}
      />,
    )

    expect(screen.getByRole('dialog', { name: '反应触发' })).toBeInTheDocument()
    expect(screen.getByText('当前没有可用反应，只能放弃反应窗口。')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Shield|Counterspell|Hellish Rebuke|Absorb Elements/ })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /放弃反应/ }))
    expect(onCancel).toHaveBeenCalledWith(prompt)
    expect(onReact).not.toHaveBeenCalled()
  })

  it('shows a non-blocking watcher notice for non-reactors', () => {
    const onReact = vi.fn()
    const onCancel = vi.fn()
    render(
      <ReactionPrompt
        currentCharacterId="host-char"
        prompt={{
          context: 'Incoming attack',
          attacker_id: 'enemy-1',
          reactor_character_id: 'guest-char',
          available_reactions: [
            {
              id: 'shield',
              type: 'shield',
              name: 'Shield',
              effect: '+5 AC',
            },
          ],
        }}
        onReact={onReact}
        onCancel={onCancel}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('guest-char 正在选择反应')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Shield/ })).not.toBeInTheDocument()
    expect(onReact).not.toHaveBeenCalled()
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('renders incoming attack details and reaction costs for the eligible reactor', () => {
    render(
      <ReactionPrompt
        currentCharacterId="char-2"
        prompt={{
          context: 'Incoming attack',
          attacker_id: 'enemy-1',
          reactor_character_id: 'char-2',
          attack_roll: 18,
          player_ac: 14,
          incoming_damage: 9,
          target_hp_before_damage: 12,
          available_reactions: [
            {
              id: 'shield',
              type: 'shield',
              name: 'Shield',
              cost: '1st-level spell slot',
              effect: '+5 AC',
              damage_prevented: 9,
            },
          ],
        }}
        onReact={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByRole('dialog', { name: '反应触发' })).toBeInTheDocument()
    expect(screen.getByText('攻击 18 vs AC14')).toBeInTheDocument()
    expect(screen.getByText('伤害 9')).toBeInTheDocument()
    expect(screen.getByText('HP 12 -> 3')).toBeInTheDocument()
    expect(screen.getByText('不反应 HP 12 -> 3')).toBeInTheDocument()
    expect(screen.getByText('使用后 HP 12 -> 12')).toBeInTheDocument()
    expect(screen.getByText('减免 9 伤害')).toBeInTheDocument()
    const action = screen.getByRole('button', { name: /Shield/ })
    expect(action).toHaveAttribute(
      'title',
      'Shield - +5 AC · 1st-level spell slot · 不反应 HP 12 -> 3；使用后 HP 12 -> 12 · 减免 9 伤害',
    )
    expect(screen.getByText('1st-level spell slot')).toBeInTheDocument()
  })

  it('calls out when a reaction avoids dropping to zero hp', () => {
    render(
      <ReactionPrompt
        currentCharacterId="char-2"
        prompt={{
          context: 'Incoming attack',
          attacker_id: 'enemy-1',
          reactor_character_id: 'char-2',
          incoming_damage: 12,
          target_hp_before_damage: 8,
          available_reactions: [
            {
              id: 'absorb_elements',
              type: 'absorb_elements',
              name: 'Absorb Elements',
              damage_prevented: 7,
            },
          ],
        }}
        onReact={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByText('不反应 HP 8 -> 0')).toBeInTheDocument()
    expect(screen.getByText('使用后 HP 8 -> 7')).toBeInTheDocument()
    expect(screen.getByText('可避免倒地')).toBeInTheDocument()
  })
})
