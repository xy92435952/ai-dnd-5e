# 视觉设计原型 — v0.10 候选

来源：`claude.ai/design` 的 handoff 包（2026-04-17）。
原型作者：Design Assistant 与用户多轮对话产出。

## 如何查看

启动前端 dev server 后访问：

```
http://localhost:3000/design-preview/index.html
```

或生产环境（Nginx）：

```
https://<你的域名>/design-preview/index.html
```

## 包含的场景（顶栏切换）

| 场景 | 对应生产页面 | 说明 |
|------|-------------|------|
| 对话冒险 | `pages/Adventure.jsx` | DM 羊皮纸卷轴 + 蜡封；玩家蓝水晶气泡；剧本式叙事 |
| 战斗面板 | `pages/Combat.jsx` | 三栏：先攻条 + 战场地图 + 行动配额；命中预测 |
| 职业纹章图鉴 | （新增） | 12 种职业 SVG 纹章 + 专属配色 |
| 角色卡 | `pages/CharacterSheet.jsx` | 英雄详情、能力、法术、装备 |
| 主页 | `pages/Home.jsx` | 模组库 + 存档 |
| 创建角色 | `pages/CharacterCreate.jsx` | 职业选择预览 |
| 多人房间 | `pages/Room.jsx` + `RoomLobby.jsx` | 联机大厅（v0.9 新增功能） |
| 登录 | `pages/Login.jsx` | 入口门面 |

## 主题（右下 Tweaks 切换）

- **BG3 风格（默认）** — 深石板 + 青绿 arcane 辉光 + god-rays + 旋转符文阵
- **龙与史诗** — 温暖金棕、英雄纹章
- **古籍魔典** — 紫罗兰秘术、烫金花饰

## 技术栈说明

原型用 React 18 UMD + Babel-in-browser 加载 JSX，方便直接放到 `public/` 即可访问，不需要参与 Vite 构建。性能足够预览，不适合生产。

## 后续迁移路线（待用户确认）

将原型样式迁移到生产 React 组件：

1. 复制 `styles/{tokens,ornaments,components,bg3}.css` 到 `frontend/src/styles/`
2. 在 `App.jsx` 引入这些 CSS + 加 `<body data-theme="bg3">`
3. 把 BG3 大气背景层（god-rays / 符文圈 / dust）抽成 `components/AtmosphereBG.jsx`
4. 按场景顺序逐个改写：Adventure → Combat → 其他
5. 12 个职业纹章拆成 `components/Crests/` 并替换原 Icons.jsx 通用图标

预计工时 5-7 天（一个场景约半天到一天）。
