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

  // 骰子动画状态（Phase 3）
  diceRoll: null,   // { faces: 20, result: 17, label: '攻击检定' } | null
  showDice: (roll) => set({ diceRoll: roll }),
  hideDice: () => set({ diceRoll: null }),

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
