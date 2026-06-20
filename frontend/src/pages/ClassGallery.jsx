/**
 * ClassGallery — 12 职业纹章图鉴页（design v0.10 新增页面）
 */
import { useNavigate } from 'react-router-dom'
import Portrait from '../components/Portrait'
import { Divider } from '../components/Ornaments'

const ALL_CLASSES = [
  { key: 'fighter', name: '战士', desc: '战阵中屹立不倒的钢铁意志' },
  { key: 'wizard', name: '法师', desc: '奥术研习者，操纵纯粹的魔法' },
  { key: 'cleric', name: '牧师', desc: '神祇的仆从，神圣的治愈者' },
  { key: 'rogue', name: '游荡者', desc: '阴影之间的敏捷刺客' },
  { key: 'paladin', name: '圣武士', desc: '誓言所铸的神圣战士' },
  { key: 'ranger', name: '游侠', desc: '荒野的守望与追踪者' },
  { key: 'barbarian', name: '蛮战士', desc: '狂暴怒火的原始力量' },
  { key: 'bard', name: '吟游诗人', desc: '用乐符编织魔法的艺人' },
  { key: 'druid', name: '德鲁伊', desc: '自然的守护者与变形者' },
  { key: 'sorcerer', name: '术士', desc: '血脉之中流淌的魔力' },
  { key: 'warlock', name: '契约师', desc: '与异界存在缔结契约' },
  { key: 'monk', name: '武僧', desc: '身体即武器，修行成道' },
]

export default function ClassGallery() {
  const nav = useNavigate()
  return (
    <div className="class-gallery-page">
      <div className="class-gallery-header">
        <div className="eyebrow">☙ 职业纹章图鉴 ❧</div>
        <div className="display-title class-gallery-title">十二道英雄之路</div>
        <div className="class-gallery-copy">
          ~ 每个职业都有专属的纹章与配色 ~
        </div>
      </div>

      <Divider>⚜ Classes ⚜</Divider>

      <div className="class-gallery-grid">
        {ALL_CLASSES.map(c => (
          <div key={c.key} className="panel-ornate class-gallery-card">
            <div className="class-gallery-portrait-slot">
              <Portrait cls={c.key} size="lg" />
            </div>
            <div className="class-gallery-class-name">
              {c.name}
            </div>
            <div className="eyebrow class-gallery-key">{c.key.toUpperCase()}</div>
            <div className="class-gallery-desc">
              "{c.desc}"
            </div>
          </div>
        ))}
      </div>

      <div className="class-gallery-footer">
        <button className="btn-ghost class-gallery-back" onClick={() => nav('/')}>⬅ 返回主页</button>
      </div>
    </div>
  )
}
