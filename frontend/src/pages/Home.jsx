import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { modulesApi, gameApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import { Divider } from '../components/Ornaments'
import Portrait from '../components/Portrait'
import { classKey } from '../components/Crests'
import { TutorialEntryCard, TutorialHost, getTutorialProgress } from '../components/Tutorial'
import { useUser } from '../hooks/useUser'

export default function Home() {
  const navigate = useNavigate()
  const { setSelectedModule, resetGame } = useGameStore()

  const [modules, setModules] = useState([])
  const [sessions, setSessions] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [homeActionError, setHomeActionError] = useState('')
  const [homeConfirmAction, setHomeConfirmAction] = useState(null)
  const [tab, setTab] = useState('modules')
  // 新手教程 —— 首次登录自动弹出 welcome；之后从入口卡手动触发
  const [tutorialOpen, setTutorialOpen] = useState(() => {
    try {
      const seen = localStorage.getItem('tutorial_seen')
      return !seen // 没看过就首次自动弹
    } catch { return false }
  })
  const tutorialProgress = getTutorialProgress()

  const { displayName } = useUser()

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
    setUploading(true); setUploadError(''); setHomeActionError(''); setHomeConfirmAction(null)
    try {
      const result = await modulesApi.upload(file)
      setModules(prev => [{ ...result, file_type: file.name.split('.').pop() }, ...prev])
      pollModuleStatus(result.id)
    } catch (err) { setUploadError(err.message) }
    finally { setUploading(false); e.target.value = '' }
  }

  const fileInputRef = useRef(null)
  const pollIntervalRef = useRef(null)
  useEffect(() => () => { if (pollIntervalRef.current) clearInterval(pollIntervalRef.current) }, [])

  const openUploadPicker = () => {
    fileInputRef.current?.click()
  }

  const handleUploadKeyDown = (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return
    e.preventDefault()
    openUploadPicker()
  }

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

  const handleDeleteModule = (id, e) => {
    e.stopPropagation()
    setHomeActionError('')
    setHomeConfirmAction({ type: 'delete-module', id })
  }

  const handleDeleteSession = (session, e) => {
    e.stopPropagation()
    if (session.is_multiplayer) {
      navigate(`/room/${session.id}`)
      return
    }
    setHomeActionError('')
    setHomeConfirmAction({ type: 'delete-session', id: session.id })
  }

  const cancelHomeConfirm = () => {
    setHomeConfirmAction(null)
  }

  const confirmHomeAction = async () => {
    const action = homeConfirmAction
    if (!action) return
    setHomeConfirmAction(null)
    setHomeActionError('')
    if (action.type === 'logout') {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      navigate('/login')
      return
    }

    try {
      if (action.type === 'delete-module') {
        await modulesApi.delete(action.id)
        setModules(prev => prev.filter(m => m.id !== action.id))
      } else if (action.type === 'delete-session') {
        await gameApi.deleteSession(action.id)
        setSessions(prev => prev.filter(s => s.id !== action.id))
      }
    } catch (err) {
      setHomeActionError(err?.message || 'Delete failed. Please try again.')
    }
  }

  const handleSelectModule = (m) => {
    if (m.parse_status !== 'done') return
    setSelectedModule(m)
    navigate(`/setup/${m.id}`)
  }

  const handleLogout = () => {
    setHomeActionError('')
    setHomeConfirmAction({ type: 'logout' })
  }

  const isLogoutConfirm = homeConfirmAction?.type === 'logout'
  const homeConfirmTitle = isLogoutConfirm
    ? '退出登录'
    : homeConfirmAction?.type === 'delete-module'
      ? '删除模组'
      : '删除存档'
  const homeConfirmDescription = isLogoutConfirm
    ? '你将返回登录页，当前本地登录状态会被清除。'
    : homeConfirmAction?.type === 'delete-module'
      ? '删除后需要重新上传并解析这个模组。'
      : '删除后无法恢复这个冒险进度。'
  const homeConfirmGroupLabel = isLogoutConfirm ? '退出登录确认操作' : '删除确认操作'
  const homeConfirmSubmitLabel = isLogoutConfirm ? '确认退出' : '确认删除'

  return (
    <div className="home-page">
      <header className="home-header">
        <div className="home-header-copy">
          <div className="eyebrow">❧ 英雄大厅 ❧</div>
          <div className="display-title home-title">欢迎归来，{displayName}</div>
        </div>
        <div className="home-header-actions">
          <button className="btn-ghost" onClick={() => navigate('/lobby')}>☰ 多人房间</button>
          <button className="btn-ghost" onClick={() => navigate('/gallery')}>❖ 职业图鉴</button>
          <button className="btn-ghost" onClick={handleLogout}>⎋ 退出</button>
        </div>
      </header>

      <Divider>⚜ 选择你的冒险 ⚜</Divider>

      {/* 新手教程入口卡 —— 已完成 4 章则收为一条轻提示 */}
      {tutorialProgress < 4 ? (
        <div className="home-tutorial-slot">
          <TutorialEntryCard
            progress={tutorialProgress}
            total={4}
            onOpen={() => setTutorialOpen(true)}
          />
        </div>
      ) : (
        <div className="home-tutorial-complete">
          <span>✓ 启蒙圣所已完成 · 所有章节已解锁</span>
          <button
            className="btn-ghost home-tutorial-replay"
            onClick={() => setTutorialOpen(true)}
          >重温教程</button>
        </div>
      )}

      {/* 标签栏 */}
      <div className="home-tabs" role="tablist" aria-label="大厅内容">
        {[
          { key: 'modules', label: '✦ 模组库' },
          { key: 'saves',   label: '❦ 存档档案' },
        ].map(t => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            data-active={tab === t.key ? 'true' : 'false'}
            className="home-tab"
            onClick={() => {
              setTab(t.key)
              setHomeActionError('')
              setHomeConfirmAction(null)
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {homeActionError && (
        <p className="home-action-error" role="alert">
          {homeActionError}
        </p>
      )}

      {homeConfirmAction && (
        <div
          className="home-confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="home-confirm-title"
          aria-describedby="home-confirm-desc"
        >
          <div className="home-confirm-panel">
            <h2 id="home-confirm-title">
              {homeConfirmTitle}
            </h2>
            <p id="home-confirm-desc">
              {homeConfirmDescription}
            </p>
            <div className="home-confirm-actions" role="group" aria-label={homeConfirmGroupLabel}>
              <button
                type="button"
                className="btn-ghost home-confirm-cancel"
                onClick={cancelHomeConfirm}
              >
                取消
              </button>
              <button
                type="button"
                className="btn-gold home-confirm-submit"
                onClick={confirmHomeAction}
              >
                {homeConfirmSubmitLabel}
              </button>
            </div>
          </div>
        </div>
      )}

      {tab === 'modules' && (
        <div>
          {/* 上传区 */}
          <div
            onClick={openUploadPicker}
            onKeyDown={handleUploadKeyDown}
            className="panel home-upload-panel"
            role="button"
            tabIndex={0}
            aria-label="上传新模组"
          >
            <input id="file-input" type="file" accept=".pdf,.docx,.doc,.md,.markdown,.txt"
              ref={fileInputRef}
              className="home-upload-input"
              onChange={handleFileUpload} />
            {uploading ? (
              <p className="home-upload-status" role="status">⏳ 上传中…</p>
            ) : (
              <>
                <div className="home-upload-icon" aria-hidden="true">✦</div>
                <p className="home-upload-title">点击上传新模组</p>
                <p className="home-upload-formats">支持 PDF · DOCX · Markdown · TXT</p>
              </>
            )}
          </div>

          {uploadError && (
            <p className="home-upload-error" role="alert">
              ⚠ {uploadError}
            </p>
          )}

          {modules.length === 0 ? (
            <div className="home-empty-state" role="status" aria-label="暂无模组">
              <div className="home-empty-icon" aria-hidden="true">📜</div>
              <p className="home-empty-text">
                还没有模组，上传一个开始冒险吧
              </p>
            </div>
          ) : (
            <div className="home-module-grid">
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
            <div className="home-empty-state" role="status" aria-label="暂无存档">
              <div className="home-empty-icon" aria-hidden="true">❦</div>
              <p className="home-empty-text">
                还没有存档，选择一个模组开始冒险吧
              </p>
            </div>
          ) : (
            <div className="home-save-grid">
              {sessions.map(s => (
                <div key={s.id} className="panel home-save-card" onClick={() => navigate(`/adventure/${s.id}`)}>
                  <Portrait cls={classKey(s.player_class)} size="sm" />
                  <div className="home-save-body">
                    <div className="home-save-title">
                      {s.save_name}
                    </div>
                    <div className="home-save-subtitle">
                      {s.player_name ? `${s.player_name} · ${s.player_race} ${s.player_class}` : s.module_name}
                    </div>
                    <div className="home-save-meta">
                      {s.is_multiplayer && (
                        <span className="home-save-room">
                          房间 {s.room_code || ''}
                        </span>
                      )}
                      <span className={`home-save-status ${s.combat_active ? 'combat' : 'explore'}`}>
                        {s.combat_active ? '⚔ 战斗中' : '🗺 探索中'}
                      </span>
                      <span className="home-save-date">
                        {s.updated_at ? new Date(s.updated_at).toLocaleString() : ''}
                      </span>
                    </div>
                  </div>
                  <button
                    className="home-save-action"
                    onClick={(e) => handleDeleteSession(s, e)}
                    title={s.is_multiplayer ? '返回房间' : '删除存档'}
                  >{s.is_multiplayer ? '↩' : '🗑'}</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 教程顶层容器 —— welcome → runner */}
      <TutorialHost
        open={tutorialOpen}
        onClose={() => {
          setTutorialOpen(false)
          try { localStorage.setItem('tutorial_seen', '1') } catch (e) {}
        }}
      />
    </div>
  )
}

/* ── 模组卡 ── */
function ModuleCard({ m, featured, onSelect, onDelete }) {
  const ready = m.parse_status === 'done'
  return (
    <div
      className={`panel-ornate home-module-card ${featured && ready ? 'is-featured' : ''}`}
      data-ready={ready ? 'true' : 'false'}
      onClick={ready ? onSelect : undefined}
    >
      {featured && ready && (
        <div className="home-module-featured">
          <span className="tag tag-gold home-module-featured-tag">★ 推荐</span>
        </div>
      )}
      <div className="home-module-body">
        <div className="home-module-icon" aria-hidden="true">📜</div>
        <div className="display-title home-module-title">{m.name}</div>
        {m.setting && (
          <div className="home-module-setting">
            {m.setting}
          </div>
        )}
      </div>
      <div className="home-module-meta">
        <StatusBadge status={m.parse_status} />
        {ready && m.level_min != null && (
          <span className="tag tag-info home-module-tag">Lv {m.level_min}-{m.level_max}</span>
        )}
        {ready && m.recommended_party_size != null && (
          <span className="tag tag-blue home-module-tag">{m.recommended_party_size} 人</span>
        )}
      </div>
      {ready && (
        <div className="home-card-actions">
          <button className="btn-gold">开始冒险 ►</button>
          <button
            className="btn-ghost home-module-delete"
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
    <span
      className={`tag ${s.cls} home-status-badge`}
      data-processing={status === 'processing' ? 'true' : 'false'}
    >
      {s.text}
    </span>
  )
}
