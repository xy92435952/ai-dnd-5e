import { describe, expect, it } from 'vitest'
import { getChoiceIntent, getChoiceLocationExit } from '../adventureChoices'

describe('getChoiceIntent', () => {
  it('uses explicit choice intent fields first', () => {
    expect(getChoiceIntent({ text: '聊聊', action_type: 'dialogue' })).toMatchObject({
      type: 'dialogue',
      label: '对话',
    })
    expect(getChoiceIntent({ text: '扎营', choice_type: 'rest' })).toMatchObject({
      type: 'rest',
      label: '休整',
    })
  })

  it('maps skill and tag metadata to Adventure choice intents', () => {
    expect(getChoiceIntent({
      text: '观察脚印',
      skill_check: true,
      tags: [{ kind: 'perception', label: '察觉', dc: 12 }],
    })).toMatchObject({ type: 'investigation', label: '调查' })

    expect(getChoiceIntent({
      text: '攀上墙头',
      skill_check: true,
      tags: [{ kind: 'athletic', label: '运动', dc: 12 }],
    })).toMatchObject({ type: 'movement', label: '移动' })

    expect(getChoiceIntent({
      text: '辨认符文',
      skill_check: true,
      check_type: '奥秘',
      dc: 15,
    })).toMatchObject({ type: 'lore', label: '知识' })
  })

  it('marks dangerous actions before softer text or tag hints', () => {
    expect(getChoiceIntent({
      text: '先谈判，再拔剑威胁',
      action: true,
      tags: [{ kind: 'persuade', label: '劝说', dc: 12 }],
    })).toMatchObject({ type: 'danger', label: '危险' })
  })

  it('falls back from text heuristics to pure roleplay', () => {
    expect(getChoiceIntent('向篝火旁的人点头致意')).toMatchObject({
      type: 'roleplay',
      label: '扮演',
    })
    expect(getChoiceIntent({ text: '询问酒馆老板最近的传闻' })).toMatchObject({
      type: 'dialogue',
      label: '对话',
    })
    expect(getChoiceIntent({ text: '进入东侧走廊' })).toMatchObject({
      type: 'movement',
      label: '移动',
    })
  })

  it('treats visible location exits as movement choices and summarizes route flags', () => {
    const choice = {
      text: '前往军械库',
      location_exit: {
        target_location_id: 'armory',
        target_location_name: '军械库',
        route_type: 'locked',
        locked: true,
        one_way: true,
        requires_key: '青铜钥匙',
        check_type: 'thieves_tools',
        dc: 15,
      },
    }

    expect(getChoiceIntent(choice)).toMatchObject({ type: 'movement', label: '移动' })
    expect(getChoiceLocationExit(choice)).toEqual({
      destination: '军械库',
      flags: ['锁定', '单向', '钥匙: 青铜钥匙', 'thieves_tools DC 15'],
      tone: 'locked',
    })
    expect(getChoiceLocationExit({
      text: '发现暗门',
      location_exit: { target_location_name: '密室', hidden: true },
    })).toBeNull()
  })
})
