import { create } from 'zustand'

export const useGameStore = create((set, get) => ({
  // 当前选中的模组
  selectedModule: null,
  setSelectedModule: (module) => set({ selectedModule: module }),

  // 玩家角色
  playerCharacter: null,
  setPlayerCharacter: (char) => set({ playerCharacter: char }),

  // AI队友列表
  companions: [],
  setCompanions: (companions) => set({ companions }),

  // 当前会话
  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),

  // 游戏日志
  logs: [],
  addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
  setLogs: (logs) => set({ logs }),

  // 战斗状态
  combatActive: false,
  combatState: null,
  setCombatActive: (active) => set({ combatActive: active }),
  setCombatState: (state) => set({ combatState: state }),

  // AI响应加载状态
  isLoading: false,
  setIsLoading: (loading) => set({ isLoading: loading }),

  // 骰子动画状态
  diceRoll: null,      // { faces, result, label, _ts } — 结果展示覆盖层
  dicePrompt: null,    // { faces, count } — "点击投掷"提示状态
  showDice: (roll) => set({ diceRoll: { ...roll, _ts: Date.now() } }),
  showDicePrompt: (config) => set({ dicePrompt: { ...config, _ts: Date.now() } }),
  hideDice: () => set({ diceRoll: null }),
  hideDicePrompt: () => set({ dicePrompt: null }),

  // ── 多人联机状态（v0.9）──
  isMultiplayer: false,
  roomCode: null,
  hostUserId: null,
  members: [],          // [{user_id, username, display_name, role, character_id, character_name, is_online}]
  currentSpeakerUserId: null,  // 探索阶段：当前发言权
  myUserId: null,
  setMultiplayer: (info) => set({
    isMultiplayer: !!info?.isMultiplayer,
    roomCode: info?.roomCode || null,
    hostUserId: info?.hostUserId || null,
  }),
  setMembers: (members) => set({ members: members || [] }),
  setCurrentSpeaker: (uid) => set({ currentSpeakerUserId: uid }),
  setMyUserId: (uid) => set({ myUserId: uid }),
  // 工具方法
  isMyTurn: () => {
    const s = get()
    if (!s.isMultiplayer) return true
    if (s.combatActive) {
      const cs = s.combatState
      if (!cs?.turn_order?.length) return true
      const cur = cs.turn_order[cs.current_turn_index || 0]
      const myChar = s.members.find(m => m.user_id === s.myUserId)?.character_id
      return cur?.character_id === myChar
    }
    return s.currentSpeakerUserId === s.myUserId
  },

  // 重置游戏状态
  resetGame: () => set({
    playerCharacter: null,
    companions: [],
    sessionId: null,
    logs: [],
    combatActive: false,
    combatState: null,
    isMultiplayer: false,
    roomCode: null,
    hostUserId: null,
    members: [],
    currentSpeakerUserId: null,
  }),
}))
