import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Login from './pages/Login'
import Home from './pages/Home'
import CharacterCreate from './pages/CharacterCreate'
import Adventure from './pages/Adventure'
import Combat from './pages/Combat'
import CharacterSheet from './pages/CharacterSheet'
import RoomLobby from './pages/RoomLobby'
import Room from './pages/Room'
import ClassGallery from './pages/ClassGallery'
import AtmosphereBG from './components/AtmosphereBG'

// design v0.10 视觉系统（按依赖顺序加载：tokens 必须最先）
import './styles/tokens.css'
import './styles/ornaments.css'
import './styles/components.css'
import './styles/bg3.css'
import './styles/gamefeel.css'
import './styles/juice.css'
import './styles/create.css'
import './styles/tutorial.css'
import './styles/compat.css'

// 引入 juice.js 让 JuiceAudio / JuiceShake 挂到 window，
// 方便 DiceRollerOverlay 等非 React 组件直接调用
import './juice'

// 路由守卫
function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  return children
}

/**
 * 不同路由对背景层透明度做微调：
 * - 战斗 / 对话冒险页面：背景较弱（核心交互区，避免分散注意力）
 * - 其他页面：背景全开
 */
function ScenicBackdrop() {
  const { pathname } = useLocation()
  const isCore = pathname.startsWith('/adventure/') || pathname.startsWith('/combat/')
  return (
    <div style={{
      opacity: isCore ? 0.45 : 1,
      transition: 'opacity .6s ease',
    }}>
      <AtmosphereBG embers={true} />
    </div>
  )
}

export default function App() {
  // 默认主题：BG3
  useEffect(() => {
    if (!document.body.getAttribute('data-theme')) {
      document.body.setAttribute('data-theme', 'bg3')
    }
  }, [])

  return (
    <BrowserRouter>
      <ScenicBackdrop />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
        <Route path="/setup/:moduleId" element={<ProtectedRoute><CharacterCreate /></ProtectedRoute>} />
        <Route path="/adventure/:sessionId" element={<ProtectedRoute><Adventure /></ProtectedRoute>} />
        <Route path="/combat/:sessionId" element={<ProtectedRoute><Combat /></ProtectedRoute>} />
        <Route path="/character/:characterId" element={<ProtectedRoute><CharacterSheet /></ProtectedRoute>} />
        <Route path="/gallery" element={<ProtectedRoute><ClassGallery /></ProtectedRoute>} />
        {/* 多人联机 */}
        <Route path="/lobby" element={<ProtectedRoute><RoomLobby /></ProtectedRoute>} />
        <Route path="/room/:sessionId" element={<ProtectedRoute><Room /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  )
}
