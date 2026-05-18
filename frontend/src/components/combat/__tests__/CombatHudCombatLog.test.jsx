import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatHudCombatLog from '../CombatHudCombatLog'

describe('CombatHudCombatLog', () => {
  it('labels mechanical results separately from DM narration', () => {
    render(
      <CombatHudCombatLog
        logs={[
          { id: 'mechanics', role: 'system', log_type: 'combat_mechanics', content: '移动了 30ft | 已靠近，下一回合可继续攻击' },
          { id: 'narration', role: 'dm', log_type: 'combat', content: '你压低身形冲过碎石地。' },
        ]}
      />
    )

    expect(screen.getByText('机制')).toBeInTheDocument()
    expect(screen.getByText('叙事')).toBeInTheDocument()
    expect(screen.getByText(/下一回合可继续攻击/)).toBeInTheDocument()
    expect(screen.getByText(/压低身形/)).toBeInTheDocument()
  })
})
