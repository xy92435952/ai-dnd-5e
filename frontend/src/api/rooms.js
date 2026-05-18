import { api } from './http'

export const roomsApi = {
  create: (moduleId, saveName, maxPlayers = 4) =>
    api.post('/game/rooms/create', { module_id: moduleId, save_name: saveName, max_players: maxPlayers }),
  join: (roomCode) =>
    api.post('/game/rooms/join', { room_code: roomCode }),
  leave: (sessionId) => api.post(`/game/rooms/${sessionId}/leave`),
  start: (sessionId) => api.post(`/game/rooms/${sessionId}/start`),
  kick: (sessionId, userId) =>
    api.post(`/game/rooms/${sessionId}/kick`, { user_id: userId }),
  transfer: (sessionId, newHostUserId) =>
    api.post(`/game/rooms/${sessionId}/transfer`, { new_host_user_id: newHostUserId }),
  claimChar: (sessionId, characterId) =>
    api.post(`/game/rooms/${sessionId}/claim-character`, { character_id: characterId }),
  fillAi: (sessionId) => api.post(`/game/rooms/${sessionId}/fill-ai`),
  joinGroup: (sessionId, groupId, groupName = null, location = null) =>
    api.post(`/game/rooms/${sessionId}/groups/join`, {
      group_id: groupId,
      group_name: groupName,
      location,
    }),
  submitGroupAction: (sessionId, groupId, actionText) =>
    api.post(`/game/rooms/${sessionId}/groups/actions`, {
      group_id: groupId,
      action_text: actionText,
    }),
  clearGroupActions: (sessionId, groupId) =>
    api.post(`/game/rooms/${sessionId}/groups/actions/clear`, { group_id: groupId }),
  setGroupReadiness: (sessionId, groupId, status) =>
    api.post(`/game/rooms/${sessionId}/groups/readiness`, { group_id: groupId, status }),
  focusGroup: (sessionId, groupId) =>
    api.post(`/game/rooms/${sessionId}/groups/focus`, { group_id: groupId }),
  get: (sessionId) => api.get(`/game/rooms/${sessionId}`),
  members: (sessionId) => api.get(`/game/rooms/${sessionId}/members`),
}
