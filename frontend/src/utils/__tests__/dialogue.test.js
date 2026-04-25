/**
 * dialogue.js 单元测试 —— DM 叙事 / 队友反应文本拆段。
 *
 * 重点保护两个之前修过的 bug：
 *   1. splitCompanionReactions 不能把 "低声从牙缝里挤出一句：" 当作 speaker
 *      （裸名字必须在 companion 白名单）
 *   2. extractNarrative 兼容历史 LLM 输出（整块 JSON 塞 log）
 */
import { describe, it, expect } from 'vitest'
import {
  splitDmNarrative,
  splitCompanionReactions,
  extractNarrative,
} from '../dialogue'


describe('splitDmNarrative', () => {
  it('空 / 空白返回 []', () => {
    expect(splitDmNarrative('')).toEqual([])
    expect(splitDmNarrative('   ')).toEqual([])
    expect(splitDmNarrative(null)).toEqual([])
  })

  it('普通段落整段作 DM 旁白', () => {
    const segs = splitDmNarrative('你推开门，里面一片漆黑。\n传来低沉的呼吸声。')
    expect(segs).toHaveLength(1)
    expect(segs[0].role).toBe('dm')
    expect(segs[0].speaker).toBe('DM')
    expect(segs[0].text).toContain('你推开门')
  })

  it('首行 [格雷]: ... 抽出 NPC 段', () => {
    const segs = splitDmNarrative('[格雷]: 你来得正好。\n他递给你一张地图。')
    expect(segs).toHaveLength(2)
    expect(segs[0].role).toBe('npc')
    expect(segs[0].speaker).toBe('格雷')
    expect(segs[1].role).toBe('dm')
    expect(segs[1].text).toBe('他递给你一张地图。')
  })

  it('首行 "格雷说：" 也识别', () => {
    const segs = splitDmNarrative('格雷说：你来得正好。\n他递给你一张地图。')
    expect(segs[0].role).toBe('npc')
    expect(segs[0].speaker).toBe('格雷')
  })

  it('首行不像 NPC 头时整段归 DM', () => {
    const segs = splitDmNarrative('雨还没停。你踏入酒馆的瞬间...')
    expect(segs).toHaveLength(1)
    expect(segs[0].role).toBe('dm')
  })
})


describe('splitCompanionReactions', () => {
  it('[名字]: 格式按 speaker 切', () => {
    const out = splitCompanionReactions('[艾莉]: 危险！\n[博恩]: 准备战斗。', [])
    expect(out).toHaveLength(2)
    expect(out[0].speaker).toBe('艾莉')
    expect(out[0].text).toContain('危险')
    expect(out[1].speaker).toBe('博恩')
  })

  it('裸名字必须在 companion 白名单内才接受', () => {
    const companions = [{ name: '艾莉' }, { name: '博恩' }]
    const out = splitCompanionReactions('艾莉: 这边走。\n博恩: 跟上。', companions)
    expect(out).toHaveLength(2)
    expect(out.map(s => s.speaker)).toEqual(['艾莉', '博恩'])
  })

  it('裸名字不在白名单时被拒（防御 "低声从牙缝里挤出一句:"）', () => {
    // 没有 companions 白名单：所有裸名字都会被拒，回退到第一队友兜底（这里没队友，用"队友"）
    const out = splitCompanionReactions('低声从牙缝里挤出一句：嘘。', [])
    // 不应把"低声从牙缝里挤出一句"当作 speaker
    expect(out.every(s => s.speaker !== '低声从牙缝里挤出一句')).toBe(true)
  })

  it('同一人多句合并成一条气泡（保持顺序）', () => {
    const companions = [{ name: '艾莉' }]
    const out = splitCompanionReactions('[艾莉]: 第一句。\n[艾莉]: 第二句。', companions)
    expect(out).toHaveLength(1)
    expect(out[0].text).toContain('第一句')
    expect(out[0].text).toContain('第二句')
  })

  it('整段无可识别 speaker → 用第一个队友兜底', () => {
    const companions = [{ name: '艾莉' }, { name: '博恩' }]
    const out = splitCompanionReactions('某种神秘的喃喃声从远方传来。', companions)
    expect(out).toHaveLength(1)
    expect(out[0].speaker).toBe('艾莉')   // 用第一个
  })

  it('空字符串 / null 返回空数组', () => {
    expect(splitCompanionReactions('', [])).toEqual([])
    expect(splitCompanionReactions(null, [])).toEqual([])
  })
})


describe('extractNarrative', () => {
  it('普通文本原样返回（trim）', () => {
    expect(extractNarrative('  hello world  ')).toBe('hello world')
  })

  it('JSON 格式抽 narrative 字段', () => {
    const json = JSON.stringify({ narrative: '你看到一道光', action_type: 'exploration' })
    expect(extractNarrative(json)).toBe('你看到一道光')
  })

  it('Markdown 代码块包裹 JSON 也能抽', () => {
    const md = '```json\n{"narrative":"门开了"}\n```'
    expect(extractNarrative(md)).toBe('门开了')
  })

  it('JSON 解析失败时正则兜底抽 narrative', () => {
    const broken = '```\n{"narrative":"半坏的 JSON","extra":  // 注释让解析失败\n```'
    const result = extractNarrative(broken)
    expect(result).toContain('半坏的 JSON')
  })

  it('空 / null 返回空字符串', () => {
    expect(extractNarrative('')).toBe('')
    expect(extractNarrative(null)).toBe('')
  })
})
