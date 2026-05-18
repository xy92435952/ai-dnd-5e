import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(normalizeApiError(err))
  },
)

export function normalizeApiError(err) {
  const message = err.response?.data?.detail || err.message || '请求失败'
  const error = new Error(message)
  error.status = err.response?.status
  error.detail = err.response?.data
  return error
}
