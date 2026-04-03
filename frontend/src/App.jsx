import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Home from './pages/Home'
import CharacterCreate from './pages/CharacterCreate'
import Adventure from './pages/Adventure'
import Combat from './pages/Combat'
import CharacterSheet from './pages/CharacterSheet'

// 路由守卫：未登录跳转到 /login
function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
        <Route path="/setup/:moduleId" element={<ProtectedRoute><CharacterCreate /></ProtectedRoute>} />
        <Route path="/adventure/:sessionId" element={<ProtectedRoute><Adventure /></ProtectedRoute>} />
        <Route path="/combat/:sessionId" element={<ProtectedRoute><Combat /></ProtectedRoute>} />
        <Route path="/character/:characterId" element={<ProtectedRoute><CharacterSheet /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  )
}
