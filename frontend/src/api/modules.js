import { api } from './http'

export const modulesApi = {
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/modules/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: () => api.get('/modules/'),
  get: (id) => api.get(`/modules/${id}`),
  delete: (id) => api.delete(`/modules/${id}`),
}
