# 视觉设计 v0.10 归档（含战斗/对话冒险待重设计版本）

**日期：** 2026-04-17
**来源：** claude.ai/design handoff 包
**状态：**
- ✅ 已实装：背景层 + 全局视觉系统 + Login / Home / RoomLobby / Room / CharacterCreate / CharacterSheet / 职业纹章图鉴
- ⏸️ 待重设计：Adventure（对话冒险）+ Combat（战斗面板）—— 用户将出完整版设计后再迁移

---

## 1. 设计意图（来自原型作者与用户的对话）

针对 v0.9 提出的痛点：
1. **战斗面板** 信息层级混乱，缺乏游戏感
2. **对话框** 没有戏剧/电影感
3. **职业头像** 用通用图标无辨识度

设计师产出方案：
- BG3 风格（深石板 + 青绿 arcane 辉光）作为默认主题
- 龙与史诗（金棕英雄）+ 古籍魔典（紫罗兰秘术）作为可切换变体
- 12 个职业各一个 SVG 纹章 + 专属配色
- 大气背景：5 道神圣光束 + 双圈反向旋转符文阵 + 漂浮尘埃 + 余烬粒子
- "去底板"策略：除战斗 / 对话冒险外的所有页面让背景穿透

## 2. 用户的关键反馈（按时间序）

| 轮次 | 用户诉求 | 设计师响应 |
|---|---|---|
| 1 | "想优化所有前端页面让它更漂亮更魔幻" | 出 BG3 + 龙与史诗 + 古籍魔典 三套主题 |
| 2 | "再酷炫一点，仿照博德之门 3 设计" | 加深石板边框、青绿宝石按钮、肖像同心环 |
| 3 | "背景有点无聊，特效不能支持这个背景" | 加 god-rays + 双圈符文阵 + 60 颗尘埃 + 暗角 |
| 4 | "除对话与冒险外把底板去掉，看背景" | 6 个页面去掉底板透明化 |
| 5 | "深度优化战斗与对话冒险，可改布局" | 新方案进行中（剧本式叙事 + 战术战斗）—— **未完成** |

## 3. 原型预览

完整原型已部署到 `frontend/public/design-preview/`，访问：

```
http://localhost:3000/design-preview/index.html
```

包含 8 个场景（顶栏切换）+ 3 套主题（右下 Tweaks 切换）。

## 4. 已实装到生产代码的部分

### 4.1 视觉系统（全局）

| 文件 | 用途 |
|---|---|
| `frontend/src/styles/tokens.css` | 三套主题的 CSS 变量（颜色、字体、动效） |
| `frontend/src/styles/ornaments.css` | 装饰元素（分隔饰带、符文环、徽章等） |
| `frontend/src/styles/components.css` | 通用组件（按钮、面板、输入框、HP 条等） |
| `frontend/src/styles/bg3.css` | BG3 主题特有样式 |

默认主题：`bg3`（在 `App.jsx` 给 `<body>` 设 `data-theme="bg3"`）

### 4.2 共享组件

| 组件 | 路径 | 用途 |
|---|---|---|
| `<AtmosphereBG />` | `components/AtmosphereBG.jsx` | BG3 大气背景层（god-rays / 符文圈 / dust / embers） |
| `<Portrait cls=... size=... />` | `components/Portrait.jsx` | 职业纹章肖像 |
| `<Crest />` 12 种 | `components/Crests.jsx` | 12 个职业的 SVG 纹章 |
| `<Divider />` | `components/Ornaments.jsx` | 装饰分隔线 |
| `<HpBar />` | `components/Ornaments.jsx` | HP 条（高/中/低三档颜色） |

### 4.3 已迁移页面

| 生产页面 | 设计来源 | 备注 |
|---|---|---|
| `pages/Login.jsx` | LoginScene | 羊皮纸登录卡 + 符文环 |
| `pages/Home.jsx` | HomeScene | 模组卡 + 存档列表 |
| `pages/RoomLobby.jsx` | （新建/加入房间样式） | 沿用新视觉系统 |
| `pages/Room.jsx` | RoomScene | 成员卡 + 在线徽章 + 房间码大字展示 |
| `pages/CharacterCreate.jsx` | CreateScene | 12 职业网格 + 右侧预览 |
| `pages/CharacterSheet.jsx` | CharacterSheet | 左肖像 + 右能力/法术/装备/特性 |
| `pages/ClassGallery.jsx`（新增） | ClassGallery | 12 职业纹章图鉴页 |

### 4.4 暂未迁移

| 生产页面 | 原因 |
|---|---|
| `pages/Adventure.jsx` | 用户标记为"将出完整版设计后再改" |
| `pages/Combat.jsx` | 同上 |

这两个页面**保留 v0.9 现有视觉**，只在 `App.jsx` 加载新 CSS 后会得到一些样式收益（按钮、HP 条等 token），但布局不动。

## 5. 主题切换机制

```jsx
// App.jsx
useEffect(() => {
  document.body.setAttribute('data-theme', 'bg3')   // bg3 / dragon / grimoire
}, [])
```

后续若做主题选择器，给一个全局 setter 即可。CSS 变量已自动响应。

## 6. 后续衔接（用户出战斗/对话冒险设计后）

迁移路径：
1. 把新 design 包放到 `frontend/public/design-preview-v2/`
2. 读取新设计的 Adventure / Combat scene
3. 直接替换 `pages/Adventure.jsx` + `pages/Combat.jsx` 内部 JSX
4. 保留所有 hooks / API 调用 / WebSocket 集成
5. 共享组件（Portrait / Divider / HpBar）和背景层无需重做

## 7. 字体依赖

CSS 头部 `@import url('https://fonts.googleapis.com/css2?...')`

加载：
- Cinzel Decorative / Cinzel
- Cormorant Garamond
- Noto Serif SC（中文）
- UnifrakturCook / MedievalSharp / Pirata One
- IM Fell English
- JetBrains Mono

生产环境若网络受限可改为本地字体或下沉到 self-hosted。

---

**完成度**：6/8 页面 + 全部视觉基础设施 + 完整 prototype 留档可访问。
