# Frontend — AI 跑团平台

React 19 + Vite 8 前端。当前主要页面包括登录、首页、角色创建、冒险剧场、战斗地图、多人房间和角色卡。

## 启动

```bash
cd frontend
npm install
npm run dev
```

开发服务器默认：

- 前端：`http://127.0.0.1:3000`
- `/api` 代理：`http://localhost:8002`

后端本地启动示例：

```bash
cd ../backend
source .venv/bin/activate
python -m uvicorn main:app --host 127.0.0.1 --port 8002
```

## 脚本

```bash
npm test          # Vitest
npm run build    # 生产构建到 dist/
npm run lint     # ESLint，当前仍含历史 lint 噪声，不作为发布门禁
npm run types:api
```

## 目录结构

```text
src/
├── App.jsx
├── api/client.js
├── pages/
│   ├── Home.jsx
│   ├── Login.jsx
│   ├── CharacterCreate.jsx
│   ├── Adventure.jsx
│   ├── Combat.jsx
│   ├── CharacterSheet.jsx
│   ├── RoomLobby.jsx
│   └── Room.jsx
├── components/
│   ├── adventure/              Adventure 页面拆分组件
│   ├── combat/                 Combat 页面拆分组件
│   ├── character-create/       角色创建步骤组件
│   └── 通用组件
├── hooks/
│   ├── useAdventure*.js
│   ├── useCombat*.js
│   ├── useDialogue*.js
│   ├── useSkillCheck.js
│   ├── useUser.js
│   └── useWebSocket.js
├── utils/
│   ├── combat.js
│   ├── combatSession.js
│   ├── combatSkillActions.js
│   ├── skillCheck.js
│   └── dialogue.js
├── data/
│   ├── dnd5e.js
│   └── combat.js
└── test/setup.js
```

## Adventure 页面拆分

页面入口：[src/pages/Adventure.jsx](/Users/qft/Desktop/ai-dnd-5e/frontend/src/pages/Adventure.jsx)

主要组件：

- `AdventureTopBar`
- `AdventureStage`
- `DialoguePanel`
- `DialogueChoices`
- `DialogueFreeSpeak`
- `DialogueLogList`
- `DialoguePendingCheck`
- `AdventureBottomHud`
- `MultiplayerSpeakBar`

主要 hooks：

- `useAdventureSession`
- `useAdventureActions`
- `useAdventureMultiplayer`
- `useDialogueFlow`
- `useDialogueWsSync`
- `useSkillCheck`

AI 选项点击会通过 `action_source: 'ai_generated_choice'` 发给后端，后端会校验该文本是否来自上一轮 `player_choices`。

## Combat 页面拆分

页面入口：[src/pages/Combat.jsx](/Users/qft/Desktop/ai-dnd-5e/frontend/src/pages/Combat.jsx)

主要组件：

- `CombatStage`
- `IsoBattlefield`
- `IsoUnit`
- `CombatHud`
- `CombatHudSkillBar`
- `InitiativeRibbon`
- `SpellModal*`
- `ReactionPrompt`
- `SmitePrompt`
- `TurnBanner`

主要 hooks：

- `useCombatLoader`
- `useCombatDerivedState`
- `useCombatPlayerActions`
- `useCombatAttackFlow`
- `useCombatSpellFlow`
- `useCombatAiTurns`
- `useCombatTurnControls`
- `useCombatSkillBar`
- `useCombatPrediction`
- `useCombatRoom`

## 测试

```bash
npm test
```

当前覆盖：

- Adventure smoke
- Combat smoke
- combat hooks
- adventure hooks
- skillCheck / dialogue / combat utils
- useUser localStorage 行为

Node 25 下可能出现 `--localstorage-file` warning，但测试应通过。`src/test/setup.js` 提供了内存版 `localStorage/sessionStorage`，避免测试环境差异导致 hook 测试失败。

## 构建和部署

```bash
npm run build
```

产物位于 `frontend/dist/`，已被 `.gitignore` 忽略。服务器 nginx 直接读取 `dist/` 时，重新构建后通常不需要重启 nginx。

当前构建可能出现两个非阻塞 warning：

- 部分 dice / world chunk 超过 500KB。
- CSS `@import` 顺序 warning。

## 已知技术债

- `npm run lint` 会扫描 `public/design-preview-*` 旧设计稿和部分 React Compiler 风格规则，当前不作为发布门禁。
- Dice / world 相关 chunk 偏大，适合后续动态加载。
- 无效 session 下 Adventure / Combat 当前多为加载态，后续应统一错误页。
