/**
 * API 响应类型的便捷别名（从 OpenAPI 生成的 api.d.ts 里挑出来）。
 *
 * 使用方式：
 *   \@typedef {import('../types/api-responses').SessionDetail} SessionDetail
 *   const data = await gameApi.getSession(id)   // data: SessionDetail
 *
 * 如果某个 API 响应还是 `unknown`（后端没配 response_model），
 * 在后端给该端点加 `response_model=YourSchema` 后重跑：
 *   cd backend && python scripts/export_openapi.py
 *   cd frontend && npm run types:api
 */
import type { components } from './api'

type Schemas = components['schemas']

// ─── Game 端 ────────────────────────────────────────────
export type SessionListItem      = Schemas['SessionListItem']
export type SessionDetail        = Schemas['SessionDetail']
export type PlayerActionResponse = Schemas['PlayerActionResponse']
export type CharacterBrief       = Schemas['CharacterBrief']
export type GameLogEntry         = Schemas['GameLogEntry']

// ─── 检定 / 休息 ────────────────────────────────────────
export type SkillCheckResult     = Schemas['SkillCheckResult']
export type RestResponse         = Schemas['RestResponse']
export type CharacterRestResult  = Schemas['CharacterRestResult']

// ─── 战斗 ───────────────────────────────────────────────
export type CombatStateResponse  = Schemas['CombatStateResponse']
export type EntitySnapshot       = Schemas['EntitySnapshot']
export type SkillBarResponse     = Schemas['SkillBarResponse']
export type SkillBarItem         = Schemas['SkillBarItem']

// ─── 创角 / 角色 ────────────────────────────────────────
export type CreateSessionResponse    = Schemas['CreateSessionResponse']
export type CharacterDetail          = Schemas['CharacterDetail']
export type CharacterOptionsResponse = Schemas['CharacterOptionsResponse']
export type GeneratePartyResponse    = Schemas['GeneratePartyResponse']

// ─── 模组 ───────────────────────────────────────────────
export type ModuleListItem      = Schemas['ModuleListItem']
export type ModuleDetail        = Schemas['ModuleDetail']
export type ModuleUploadResponse = Schemas['ModuleUploadResponse']

// ─── 用户 ───────────────────────────────────────────────
export type MeResponse = Schemas['MeResponse']
export type TokenResponse = Schemas['TokenResponse']
