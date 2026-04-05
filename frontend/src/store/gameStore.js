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

  // 重置游戏状态
  resetGame: () => set({
    playerCharacter: null,
    companions: [],
    sessionId: null,
    logs: [],
    combatActive: false,
    combatState: null,
  }),
}))
