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
    <div style={{ minHeight: '100vh', padding: '32px 28px', position: 'relative', zIndex: 1, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <div className="eyebrow">☙ 职业纹章图鉴 ❧</div>
        <div className="display-title" style={{ fontSize: 30, marginTop: 4 }}>十二道英雄之路</div>
        <div style={{
          fontFamily: 'var(--font-script)', fontStyle: 'italic',
          color: 'var(--parchment-dark)', marginTop: 6, fontSize: 13,
        }}>
          ~ 每个职业都有专属的纹章与配色 ~
        </div>
      </div>

      <Divider>⚜ Classes ⚜</Divider>

      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
        gap: 16, maxWidth: 1100, margin: '20px auto 0',
      }}>
        {ALL_CLASSES.map(c => (
          <div key={c.key} className="panel-ornate" style={{
            padding: '20px 14px', textAlign: 'center', transition: 'var(--transition)',
          }}>
            <Portrait cls={c.key} size="lg" style={{ margin: '0 auto 10px' }} />
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--parchment)', marginBottom: 3 }}>
              {c.name}
            </div>
            <div className="eyebrow" style={{ fontSize: 9 }}>{c.key.toUpperCase()}</div>
            <div style={{
              fontFamily: 'var(--font-script)', fontSize: 12,
              color: 'var(--parchment-dark)', fontStyle: 'italic',
              marginTop: 6, lineHeight: 1.5,
            }}>
              "{c.desc}"
            </div>
          </div>
        ))}
      </div>

      <div style={{ textAlign: 'center', marginTop: 32 }}>
        <button className="btn-ghost" onClick={() => nav('/')}>⬅ 返回主页</button>
      </div>
    </div>
  )
}
