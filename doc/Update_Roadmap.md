# 更新路线图

**项目：** AI 跑团平台（DnD 5e）
**文档更新时间：** 2026-05-07
**当前状态：** v0.11-dev，结构化拆分与 DM Agent 重构阶段。

## 当前路线图

```text
v0.10                 v0.11-dev                         v1.0
视觉重写 / 多人 MVP → 结构拆分 / DM 四层 / 测试补强 → 可公开测试版本
```

## 2026-05 当前完成内容

### 1. Adventure / Combat 前端拆分

Adventure：

- 页面保留业务装配，UI 组件拆到 `frontend/src/components/adventure/`。
- 行动、检定、多人发言、对话播放拆到 hooks：
  - `useAdventureSession`
  - `useAdventureActions`
  - `useAdventureMultiplayer`
  - `useDialogueFlow`
  - `useDialogueWsSync`
  - `useSkillCheck`

Combat：

- 地图、单位、HUD、技能栏、回合条、弹窗拆到 `frontend/src/components/combat/`。
- 加载、派生状态、玩家动作、攻击、施法、AI 回合、回合控制拆到 `useCombat*` hooks。
- 补充 Combat smoke 和 hooks 单元测试。

### 2. 后端 combat 包继续拆分

`backend/api/combat/` 从历史大文件继续拆成职责模块：

- 攻击：`attack_rolls` / `attack_damage` / `attack_targeting` / `attack_modifiers` / `attack_actions`
- 法术：`spell_rolls` / `spell_effects` / `spell_targets` / `spell_catalog` / `pending_spells`
- AI 回合：`ai_turn_context` / `ai_turn_actions` / `ai_turn_attack` / `ai_turn_spell` / `ai_turn_utils` / `ai_end`
- 特殊动作：`class_features` / `grapples` / `maneuvers` / `smites`

### 3. DM Agent 四层化

DM Agent 现在按四层维护：

- **输入层**：识别输入来源，区分玩家输入、AI 选项、系统动作、AI 代演。
- **规则层**：处理规则合法性、检定需求、战斗触发和拦截。
- **叙事层**：生成探索 / 战斗叙事。
- **记忆层**：整合 GameLog、campaign_state、LangGraph checkpoint、RAG。

已修复：

- 合理的“优势骰 / 激励骰 / 帮助动作”等术语不再被误拦截。
- 与游戏无关、注入、明显作弊内容会被拦截。
- AI 生成选项只有在后端确认匹配上一轮 `player_choices` 时才按 `ai_generated_choice` 放行。

### 4. 自然语言战斗体验修复

问题：

- 玩家输入“我向最近的骷髅移动并用长剑攻击它”时，如果距离过远，旧逻辑会移动后仍尝试攻击，造成“像是攻击失败”的错觉。

修复：

- `action_parser` 本地解析常见移动 + 近战攻击意图。
- 如果本回合移动后仍不可达，只生成 `move`，不生成假 `attack`。
- `api.game` 根据实际执行动作给 `combat_narrator` 传 `move` / `attack` / `creative` / `out_of_range`。

测试：

- `backend/tests/unit/test_action_parser.py`
- `backend/tests/integration/test_combat_endpoints.py::test_natural_language_unreachable_melee_moves_without_fake_attack`

### 5. 发布前验证补强

当前验证命令：

```bash
cd frontend
npm test
npm run build

cd ..
backend/.venv-codex/bin/pytest \
  backend/tests/unit/test_action_parser.py \
  backend/tests/integration/test_combat_endpoints.py \
  backend/tests/smoke/test_imports.py -q
```

最近一次验证：

- `scripts/check.sh`：通过。
- 后端 pytest：315 passed。
- 前端 Vitest：32 files / 141 tests passed。
- 前端 Vite build：成功。

## 下一阶段优先级

### P0：稳定可部署

- [ ] 继续用真实模组跑探索 + 战斗 + 多人一轮完整冒烟。
- [ ] 清理 `npm run lint` 中的历史噪声，至少把 `public/design-preview-*` 排除或降级。
- [ ] 把服务器 `update_server.sh` 和实际 systemd 服务名统一。
- [ ] 确认生产 `.env` 中 `LLM_MODEL`、`LLM_BASE_URL`、`CORS_ALLOW_ORIGINS` 和服务端口一致。

### P1：DM 可维护性

- [x] 将 DM prompt 拆为独立模板文件：`dm_agent_prompts.py`。
- [x] 将 DM Agent 节点、state、LLM 用户消息、骰池/响应包装、checkpoint、Campaign State 拆出主图文件。
- [x] 将 DM Agent 输入元数据、规则上下文、记忆上下文、输出归一化从 `dm_agent_utils.py` 继续拆分。
- [x] 将规则拦截 policy 和本地关键词规则提取为独立模块，并按 PatternGroup 结构化。
- [x] 给 DM Agent 四层增加更细的单元测试：输入源、规则拦截、LLM 消息组装、运行时响应包装。
- [x] 继续补 DM Agent parse fallback 和输出归一化的边界测试。
- [x] 继续补 DM Agent 记忆上下文和 Campaign State 合并边界测试。
- [x] 为 RAG 检索结果加入更明确的“只可参考，不可覆盖规则”约束。
- [x] 新增 Living Campaign State：`campaign_delta` 归一化、任务/NPC/线索/关键决定/世界 flag 合并，并在 Adventure HUD 显示最近记忆摘要。
- [x] 新增 `scripts/check.sh` 一键门禁，统一运行后端测试、前端测试和前端构建。

### P1.5：DM 体验升级

- [x] `campaign_delta` 输出契约接入探索 prompt。
- [x] `StateApplicator` 将 `campaign_delta` 写入 `session.campaign_state` 和 `session.game_state.scene_vibe`。
- [x] Adventure HUD 显示最近任务、线索、NPC 关系和关键决定。
- [ ] 卷宗 / Journal 面板升级：按任务、线索、NPC、关键决定分栏浏览。
- [ ] 为 NPC 关系变化增加更明确的前端提示或日志条目。
- [ ] 给真实 LLM 冒险测试增加 campaign memory 断言。

### P2：战斗体验

- [x] Adventure 页面继续拆出多人房间 hook、UI state hook、session 恢复工具与对话队列纯函数。
- [x] Combat 页面继续拆出页面常量、可选副作用工具、页面状态 hook、导航动作 hook 和 runtime 接线 hook。
- [ ] 自然语言战斗支持更多动作：撤离、冲刺、帮助、躲避、掩体、指定坐标。
- [ ] 移动后不可达时前端提示“已靠近，下一回合可继续攻击”。
- [ ] 战斗日志中区分机械结果和 DM 叙事，便于玩家理解。
- [ ] 法术 AOE 和目标选择前端继续补强。

### P3：前端结构

- [ ] CharacterCreate 继续拆 hook，降低页面状态密度。
- [ ] Dice / world 大 chunk 动态加载。
- [ ] 统一 Adventure / Combat 错误态和 loading 态，避免无效 session 长时间只显示加载。
- [ ] 给新增组件补齐 smoke / interaction 测试。

### P4：多人和部署

- [ ] WebSocket 房间状态横向扩容方案：Redis pub/sub 或外部消息层。
- [ ] 离线玩家自动跳过 / AI 代演策略可配置。
- [ ] 房主控制：跳过、重骰、长休、补 AI 队友。
- [ ] 部署脚本区分本地 SQLite、生产 PostgreSQL、Docker 三条路径。

## 历史里程碑

| 版本 | 里程碑 |
|------|--------|
| v0.1 | 项目启动，基础架构设计 |
| v0.2 | 模组解析、角色创建、AI 队友、探索循环、基础战斗 |
| v0.3 | 网格战斗、法术系统、RAG 检索、5e 规则、条件系统 |
| v0.4 | Dify → LangGraph 迁移 |
| v0.5 | 5e 角色特性、用户认证、E2E 验证 |
| v0.6 | AI 战斗决策、子职业效果、3D 骰子、金币、开场白 |
| v0.7 | 前端驱动骰子、反应 UI、控制法术、短休资源、AI 队友施法 |
| v0.8 | PostgreSQL、Docker、SSL、自定义域名 |
| v0.9 | 自然语言战斗、Action Parser、AI 队友行为大改 |
| v0.10 | BG3 风格视觉重写、像素精灵、多人联机 MVP、腾讯云部署 |
| v0.10.1 | 多人角色创建流程、房主一键补 AI 队友 |
| v0.10.2 | Agent prompt 加固、输入审核层 |
| v0.11-dev | Adventure / Combat / DM Agent 结构化拆分和测试补强 |

## 当前已知限制

- 许多 5e 高级规则仍是近似实现，尤其召唤物、部分子职业细节和复杂反应窗口。
- `npm run lint` 当前不是发布门禁，存在历史设计稿和 React Compiler 风格规则噪声。
- 多人 WebSocket 为进程内管理，暂不适合多后端实例横向扩容。
- DM prompt 仍有进一步模块化空间。
- 生产和本地端口在不同脚本中可能出现 8000 / 8002 差异，部署时以 nginx 和 systemd 实际配置为准。
