import { api } from './http'

export const charactersApi = {
  options: () => api.get('/characters/options'),
  create: (data) => api.post('/characters/create', data),
  generateParty: (data) => api.post('/characters/generate-party', data),
  get: (id) => api.get(`/characters/${id}`),
  prepareSpells: (id, preparedSpells) =>
    api.patch(`/characters/${id}/prepared-spells`, { prepared_spells: preparedSpells }),
  updateEquipment: (charId, equipment) =>
    api.patch(`/characters/${charId}/equipment-bulk`, { equipment }),
  equipItem: (charId, itemName, itemCategory, equip = true) =>
    api.patch(`/characters/${charId}/equipment`, {
      item_name: itemName,
      item_category: itemCategory,
      equip,
    }),
  getShopInventory: () => api.get('/characters/shop/inventory'),
  buyItem: (charId, itemName, itemCategory, quantity = 1) =>
    api.post(`/characters/${charId}/shop/buy`, {
      item_name: itemName,
      item_category: itemCategory,
      quantity,
    }),
  sellItem: (charId, itemName, itemCategory, itemIndex = 0) =>
    api.post(`/characters/${charId}/shop/sell`, {
      item_name: itemName,
      item_category: itemCategory,
      item_index: itemIndex,
    }),
  transferItem: (charId, targetCharacterId, itemName, itemCategory, itemIndex = 0) =>
    api.post(`/characters/${charId}/transfer-item`, {
      target_character_id: targetCharacterId,
      item_name: itemName,
      item_category: itemCategory,
      item_index: itemIndex,
    }),
  useItem: (charId, itemName, options = {}) =>
    api.post(`/characters/${charId}/use-item`, { item_name: itemName, ...options }),
  levelUp: (charId, choices = {}) =>
    api.post(`/characters/${charId}/level-up`, choices),
  updateGold: (charId, amount, reason = '') =>
    api.patch(`/characters/${charId}/gold`, { amount, reason }),
  updateExhaustion: (charId, change = 1) =>
    api.patch(`/characters/${charId}/exhaustion`, { change }),
  updateAmmo: (charId, weaponName, change = -1) =>
    api.patch(`/characters/${charId}/ammo`, { weapon_name: weaponName, change }),
}
