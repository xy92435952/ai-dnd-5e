import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { modulesApi, gameApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import { BookIcon, UploadIcon, TrashIcon, ScrollIcon, SaveIcon, SwordIcon } from '../components/Icons'

export default function Home() {
  const navigate = useNavigate()
  const { setSelectedModule, resetGame } = useGameStore()

  const [modules, setModules] = useState([])
  const [sessions, setSessions] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [tab, setTab] = useState('modules')

  useEffect(() => { resetGame(); loadModules(); loadSessions() }, [])

  const loadModules = async () => {
    try { setModules(await modulesApi.list()) } catch (e) { console.error(e) }
  }
  const loadSessions = async () => {
    try { setSessions(await gameApi.listSessions()) } catch (e) { console.error(e) }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true); setUploadError('')
    try {
      const result = await modulesApi.upload(file)
      setModules(prev => [{ ...result, file_type: file.name.split('.').pop() }, ...prev])
      pollModuleStatus(result.id)
    } catch (err) { setUploadError(err.message) }
    finally { setUploading(false); e.target.value = '' }
  }

  const pollIntervalRef = useRef(null)
  useEffect(() => () => { if (pollIntervalRef.current) clearInterval(pollIntervalRef.current) }, [])

  const pollModuleStatus = (moduleId) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    pollIntervalRef.current = setInterval(async () => {
      try {
        const m = await modulesApi.get(moduleId)
        setModules(prev => prev.map(mod => mod.id === moduleId ? { ...mod, ...m } : mod))
        if (m.parse_status === 'done' || m.parse_status === 'failed') {
          clearInterval(pollIntervalRef.current); pollIntervalRef.current = null
        }
      } catch { clearInterval(pollIntervalRef.current); pollIntervalRef.current = null }
    }, 3000)
  }

  const handleDeleteModule = async (id, e) => {
    e.stopPropagation()
    if (!confirm('确定要删除这个模组吗？')) return
    try { await modulesApi.delete(id); setModules(prev => prev.filter(m => m.id !== id)) }
    catch (err) { alert(err.message) }
  }

  const handleDeleteSession = async (id, e) => {
    e.stopPropagation()
    if (!confirm('确定要删除这个存档吗？删除后无法恢复。')) return
    try { await gameApi.deleteSession(id); setSessions(prev => prev.filter(s => s.id !== id)) }
    catch (err) { alert(err.message) }
  }

  const handleSelectModule = (module) => {
    if (module.parse_status !== 'done') return
    setSelectedModule(module)
    navigate(`/setup/${module.id}`)
  }

  return (
    <div style={{ minHeight: '100vh', padding: 24, maxWidth: 900, margin: '0 auto' }}>

      {/* ── 标题 ── */}
      <div style={{ textAlign: 'center', padding: '30px 0 24px' }}>
        <h1 style={{
          fontSize: '3rem', fontWeight: 900, color: 'var(--gold)',
          textShadow: '0 2px 8px rgba(201,168,76,0.3), 0 0 40px rgba(201,168,76,0.1)',
          letterSpacing: '0.15em', fontFamily: 'Georgia, "Noto Serif SC", serif',
        }}>
          <SwordIcon size={36} color="var(--gold)" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 8 }} />
          AI 跑团
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-dim)', letterSpacing: '0.1em', marginTop: 6 }}>
          DnD 5e · AI地下城主 · 单人冒险
        </p>
      </div>

      {/* ── 标签栏 ── */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 20, borderBottom: '1px solid var(--wood-light)' }}>
        {[
          { key: 'modules', icon: <BookIcon size={14} />, label: '模组库' },
          { key: 'saves',   icon: <SaveIcon size={14} />, label: '存档' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            flex: 1, textAlign: 'center', padding: '10px 0', cursor: 'pointer',
            fontSize: 14, border: 'none', background: 'none',
            color: tab === t.key ? 'var(--gold)' : 'var(--text-dim)',
            borderBottom: tab === t.key ? '2px solid var(--gold)' : '2px solid transparent',
            transition: 'all 0.3s', fontFamily: 'inherit', fontWeight: tab === t.key ? 700 : 400,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* ── 模组列表 ── */}
      {tab === 'modules' && (
        <div>
          {/* 上传区 */}
          <div onClick={() => document.getElementById('file-input').click()} style={{
            border: '2px dashed var(--wood-light)', borderRadius: 12,
            padding: '36px 20px', textAlign: 'center', marginBottom: 16,
            background: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(46,31,14,0.3) 10px, rgba(46,31,14,0.3) 11px)',
            cursor: 'pointer', transition: 'all 0.3s',
          }}>
            <input id="file-input" type="file" accept=".pdf,.docx,.doc,.md,.markdown,.txt"
              style={{ display: 'none' }} onChange={handleFileUpload} />
            {uploading ? (
              <p style={{ color: 'var(--gold)', animation: 'pulse 1.5s infinite' }}>⏳ 上传中...</p>
            ) : (
              <>
                <UploadIcon size={36} color="var(--parchment-dark)" style={{ margin: '0 auto 8px' }} />
                <p style={{ color: 'var(--parchment-dark)', fontSize: 14 }}>点击上传模组文件</p>
                <p style={{ color: 'var(--text-dim)', fontSize: 11, marginTop: 4 }}>支持 PDF · DOCX · Markdown · TXT</p>
              </>
            )}
          </div>

          {uploadError && <p style={{ color: 'var(--red-light)', fontSize: 12, marginBottom: 12 }}>⚠ {uploadError}</p>}

          {modules.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', opacity: 0.4 }}>
              <BookIcon size={40} color="var(--text-dim)" style={{ margin: '0 auto 8px' }} />
              <p>还没有模组，上传一个开始冒险吧</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {modules.map(m => (
                <div key={m.id} onClick={() => handleSelectModule(m)} className="panel" style={{
                  padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14,
                  cursor: m.parse_status === 'done' ? 'pointer' : 'default',
                  opacity: m.parse_status === 'done' ? 1 : 0.6,
                  transition: 'all 0.2s',
                }}>
                  <div style={{
                    width: 46, height: 46, borderRadius: 8, flexShrink: 0,
                    background: 'linear-gradient(135deg, #3a2a18, #5a4a30)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: '1px solid var(--wood-light)',
                  }}>
                    <ScrollIcon size={24} color="var(--parchment-dark)" />
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-bright)', margin: 0 }}>{m.name}</p>
                    {m.setting && <p style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.setting}</p>}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 5 }}>
                      <StatusBadge status={m.parse_status} />
                      {m.parse_status === 'done' && (
                        <>
                          <span className="tag tag-level">Lv {m.level_min}-{m.level_max}</span>
                          <span className="tag tag-info">推荐{m.recommended_party_size}人</span>
                        </>
                      )}
                    </div>
                  </div>

                  {m.parse_status === 'done' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flexShrink: 0 }}>
                      <button className="btn-gold" style={{ padding: '5px 14px', fontSize: 12 }}>开始 →</button>
                      <button className="btn-danger" style={{ padding: '4px 10px', fontSize: 11 }}
                        onClick={e => handleDeleteModule(m.id, e)}>
                        <TrashIcon size={12} /> 删除
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── 存档列表 ── */}
      {tab === 'saves' && (
        <div>
          {sessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', opacity: 0.4 }}>
              <SaveIcon size={40} color="var(--text-dim)" style={{ margin: '0 auto 8px' }} />
              <p>还没有存档，选择一个模组开始冒险吧</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {sessions.map(s => (
                <div key={s.id} className="panel" style={{
                  padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14,
                  cursor: 'pointer', transition: 'all 0.2s',
                }} onClick={() => navigate(`/adventure/${s.id}`)}>
                  <div style={{
                    width: 46, height: 46, borderRadius: 8, flexShrink: 0,
                    background: s.combat_active ? 'linear-gradient(135deg, #3a1a1a, #5a2a2a)' : 'linear-gradient(135deg, #1a3a1a, #2a4a2a)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: `1px solid ${s.combat_active ? 'var(--red)' : 'var(--green)'}`,
                  }}>
                    {s.combat_active
                      ? <SwordIcon size={22} color="var(--red-light)" />
                      : <BookIcon size={22} color="var(--green-light)" />}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <p style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)', margin: 0 }}>{s.save_name}</p>
                      {s.player_name && (
                        <span className="tag tag-ok" style={{ fontSize: 10 }}>
                          {s.player_name} · {s.player_race} {s.player_class}
                        </span>
                      )}
                    </div>
                    <p style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 3 }}>
                      {s.module_name}
                      <span style={{ marginLeft: 8, color: s.combat_active ? 'var(--red-light)' : 'var(--gold)' }}>
                        {s.combat_active ? '⚔ 战斗中' : '🗺 探索中'}
                      </span>
                    </p>
                    <p style={{ fontSize: 10, color: 'var(--text-dim)', opacity: 0.5, marginTop: 2 }}>
                      {s.updated_at ? new Date(s.updated_at).toLocaleString() : ''}
                    </p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, color: 'var(--gold-dim)' }}>继续 →</span>
                    <button
                      onClick={(e) => handleDeleteSession(s.id, e)}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--text-dim)', padding: '4px', borderRadius: 4,
                        transition: 'color 0.2s',
                      }}
                      onMouseEnter={e => e.currentTarget.style.color = 'var(--red)'}
                      onMouseLeave={e => e.currentTarget.style.color = 'var(--text-dim)'}
                      title="删除存档"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14"/>
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ── 状态徽章组件 ── */
function StatusBadge({ status }) {
  const map = {
    pending:    { text: '等待解析', color: 'var(--gold-dim)', bg: 'rgba(201,168,76,0.1)', border: 'var(--gold-dim)' },
    processing: { text: '解析中...', color: 'var(--blue-light)', bg: 'rgba(58,122,170,0.1)', border: 'var(--blue)' },
    done:       { text: '✓ 已就绪', color: 'var(--green-light)', bg: 'rgba(42,90,42,0.15)', border: 'var(--green)' },
    failed:     { text: '✗ 失败', color: 'var(--red-light)', bg: 'rgba(139,32,32,0.15)', border: 'var(--red)' },
  }
  const s = map[status] || map.pending
  return (
    <span className="tag" style={{
      color: s.color, background: s.bg, borderColor: s.border,
      animation: status === 'processing' ? 'pulse 1.5s infinite' : undefined,
    }}>
      {s.text}
    </span>
  )
}
