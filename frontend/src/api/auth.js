import { api } from './http'

export const authApi = {
  register: (username, password, displayName) =>
    api.post('/auth/register', { username, password, display_name: displayName }),
  login: (username, password) =>
    api.post('/auth/login', { username, password }),
}
