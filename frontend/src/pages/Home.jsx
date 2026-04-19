import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { modulesApi, gameApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import { Divider } from '../components/Ornaments'
import Portrait from '../components/Portrait'
import { classKey } from '../components/Crests'

export default function Home() {
  const navigate = useNavigate()
  const { setSelectedModule, resetGame } = useGameStore()

  const [modules, setModules] = useState([])
  const [sessions, setSessions] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [tab, setTab] = useState('modules')

  const me = (() => {
    try { return JSON.parse(localStorage.getItem('user') || 'null') } catch { return null }
  })()
  const displayName = me?.display_name || me?.displayName || me?.username || '冒险者'

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

  const handleSelectModule = (m) => {
    if (m.parse_status !== 'done') return
    setSelectedModule(m)
    navigate(`/setup/${m.id}`)
  }

  const handleLogout = () => {
    if (!confirm('确认退出登录？')) return
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  return (
    <div style={{ minHeight: '100vh', padding: '24px 32px', maxWidth: 1100, margin: '0 auto', position: 'relative', zIndex: 1 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <div className="eyebrow">❧ 英雄大厅 ❧</div>
          <div className="display-title" style={{ fontSize: 32, marginTop: 4 }}>欢迎归来，{displayName}</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button className="btn-ghost" onClick={() => navigate('/lobby')}>☰ 多人房间</button>
          <button className="btn-ghost" onClick={() => navigate('/gallery')}>❖ 职业图鉴</button>
          <button className="btn-ghost" onClick={handleLogout}>⎋ 退出</button>
        </div>
      </header>

      <Divider>⚜ 选择你的冒险 ⚜</Divider>

      {/* 标签栏 */}
      <div style={{ display: 'flex', gap: 0, margin: '20px 0 18px', borderBottom: '1px solid var(--bark-light)' }}>
        {[
          { key: 'modules', label: '✦ 模组库' },
          { key: 'saves',   label: '❦ 存档档案' },
        ].map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              flex: 1, textAlign: 'center', padding: '10px 0', cursor: 'pointer',
              fontSize: 14, border: 'none', background: 'none',
              color: tab === t.key ? 'var(--amber)' : 'var(--parchment-dark)',
              borderBottom: tab === t.key ? '2px solid var(--amber)' : '2px solid transparent',
              transition: 'var(--transition)',
              fontFamily: 'var(--font-display)',
              letterSpacing: '.12em',
              fontWeight: tab === t.key ? 700 : 400,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'modules' && (
        <div>
          {/* 上传区 */}
          <div
            onClick={() => document.getElementById('file-input').click()}
            className="panel"
            style={{
              border: '2px dashed var(--bark-light)',
              padding: '36px 20px', textAlign: 'center', marginBottom: 16,
              cursor: 'pointer', transition: 'var(--transition)',
            }}
          >
            <input id="file-input" type="file" accept=".pdf,.docx,.doc,.md,.markdown,.txt"
              style={{ display: 'none' }} onChange={handleFileUpload} />
            {uploading ? (
              <p style={{ color: 'var(--amber)', fontFamily: 'var(--font-display)', letterSpacing: '.2em' }}>⏳ 上传中…</p>
            ) : (
              <>
                <div style={{ fontSize: 32, color: 'var(--parchment-dark)', marginBottom: 6 }}>✦</div>
                <p style={{ color: 'var(--parchment)', fontSize: 14, fontFamily: 'var(--font-heading)', margin: 0 }}>点击上传新模组</p>
                <p style={{ color: 'var(--parchment-dark)', fontSize: 11, marginTop: 4, fontFamily: 'var(--font-mono)' }}>支持 PDF · DOCX · Markdown · TXT</p>
              </>
            )}
          </div>

          {uploadError && (
            <p style={{ color: '#ffaaaa', fontSize: 12, marginBottom: 12, padding: 8, background: 'rgba(139,32,32,.2)', border: '1px solid var(--blood)', borderRadius: 4 }}>
              ⚠ {uploadError}
            </p>
          )}

          {modules.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', opacity: 0.5 }}>
              <div style={{ fontSize: 48, marginBottom: 6 }}>📜</div>
              <p style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)' }}>
                还没有模组，上传一个开始冒险吧
              </p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
              {modules.map((m, i) => (
                <ModuleCard key={m.id} m={m} featured={i === 0}
                  onSelect={() => handleSelectModule(m)}
                  onDelete={(e) => handleDeleteModule(m.id, e)} />
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'saves' && (
        <div>
          {sessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', opacity: 0.5 }}>
              <div style={{ fontSize: 48, marginBottom: 6 }}>❦</div>
              <p style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)' }}>
                还没有存档，选择一个模组开始冒险吧
              </p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px,1fr))', gap: 12 }}>
              {sessions.map(s => (
                <div key={s.id} className="panel" style={{
                  padding: 14, display: 'flex', gap: 12, alignItems: 'center',
                  cursor: 'pointer', transition: 'var(--transition)',
                }} onClick={() => navigate(`/adventure/${s.id}`)}>
                  <Portrait cls={classKey(s.player_class)} size="sm" />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontFamily: 'var(--font-heading)', fontSize: 13,
                      color: 'var(--parchment)', fontWeight: 600,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {s.save_name}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                      {s.player_name ? `${s.player_name} · ${s.player_race} ${s.player_class}` : s.module_name}
                    </div>
                    <div style={{ fontSize: 10, marginTop: 2 }}>
                      <span style={{ color: s.combat_active ? 'var(--blood-light)' : 'var(--amber)' }}>
                        {s.combat_active ? '⚔ 战斗中' : '🗺 探索中'}
                      </span>
                      <span style={{ color: 'var(--parchment-dark)', marginLeft: 6, opacity: 0.6 }}>
                        {s.updated_at ? new Date(s.updated_at).toLocaleString() : ''}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDeleteSession(s.id, e)}
                    title="删除存档"
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: 'var(--parchment-dark)', padding: 4, fontSize: 16,
                      transition: 'color 0.2s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = 'var(--blood-light)'}
                    onMouseLeave={e => e.currentTarget.style.color = 'var(--parchment-dark)'}
                  >🗑</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ── 模组卡 ── */
function ModuleCard({ m, featured, onSelect, onDelete }) {
  const ready = m.parse_status === 'done'
  return (
    <div className="panel-ornate" style={{
      padding: 18,
      minHeight: 180,
      position: 'relative', overflow: 'hidden',
      display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      cursor: ready ? 'pointer' : 'default',
      opacity: ready ? 1 : 0.65,
      transition: 'var(--transition)',
    }} onClick={ready ? onSelect : undefined}>
      {featured && ready && (
        <div style={{ position: 'absolute', top: 12, right: 12 }}>
          <span className="tag tag-gold" style={{ fontSize: 10 }}>★ 推荐</span>
        </div>
      )}
      <div>
        <div style={{ fontSize: 28, marginBottom: 8 }}>📜</div>
        <div className="display-title" style={{ fontSize: 18, lineHeight: 1.3 }}>{m.name}</div>
        {m.setting && (
          <div style={{
            fontFamily: 'var(--font-script)', fontStyle: 'italic',
            fontSize: 12, color: 'var(--parchment-dark)',
            marginTop: 6, lineHeight: 1.5,
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}>
            {m.setting}
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <StatusBadge status={m.parse_status} />
        {ready && m.level_min != null && (
          <span className="tag tag-info" style={{ fontSize: 10 }}>Lv {m.level_min}-{m.level_max}</span>
        )}
        {ready && m.recommended_party_size != null && (
          <span className="tag tag-blue" style={{ fontSize: 10 }}>{m.recommended_party_size} 人</span>
        )}
      </div>
      {ready && (
        <div style={{ marginTop: 12, display: 'flex', gap: 6 }}>
          <button className="btn-gold" style={{ flex: 1, fontSize: 11, padding: '7px' }}>开始冒险 ►</button>
          <button
            className="btn-ghost"
            style={{ padding: '7px 10px', fontSize: 10, borderColor: 'var(--blood)' }}
            onClick={onDelete}
          >删除</button>
        </div>
      )}
    </div>
  )
}

/* ── 状态徽章 ── */
function StatusBadge({ status }) {
  const map = {
    pending:    { text: '等待解析', cls: 'tag-info' },
    processing: { text: '解析中…', cls: 'tag-magic' },
    done:       { text: '✓ 已就绪', cls: 'tag-ok' },
    failed:     { text: '✗ 失败', cls: 'tag-danger' },
  }
  const s = map[status] || map.pending
  return (
    <span className={`tag ${s.cls}`} style={{
      animation: status === 'processing' ? 'pulse 1.5s infinite' : undefined,
    }}>
      {s.text}
    </span>
  )
}
