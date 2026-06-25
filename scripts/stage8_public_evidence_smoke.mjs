#!/usr/bin/env node
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, '..');

const DEFAULT_TIMEOUT_MS = 120_000;
const DEFAULT_MODULE_POLL_MS = 180_000;
const DEFAULT_SHOP_SETUP_GOLD = 100;
const DEFAULT_COMBAT_ACTION_TEXT = 'We enter the training yard together and engage the sentries in combat.';
const SMOKE_MODULE_TEXT = `Stage 8 Public Evidence Module

Name: The Clockwork Gatehouse
Setting: A compact roadside keep with a practice yard, a small market stall, and a guarded planar gate.
Tone: Practical heroic fantasy with clear tactical stakes.
Recommended party size: 2
Level range: 1-3

Scene 1: The party meets a gate warden beside a map table and a modest merchant stall.
Scene 2: The adventurers can inspect the gate, talk through a plan, and prepare equipment.
Scene 3: If training begins, two brass sentries step into the practice yard.

NPCs:
- Keeper Mara, cautious gate warden, wants the crossing stabilized.

Monsters:
- Brass Sentry, CR 1/4, armor class 13, hit points 11, speed 30 ft, attack: spear +3 to hit for 1d6+1 piercing damage.

Reward: A gate token worth 25 gp and safe passage through the keep.
`;

export const STAGE8_PUBLIC_EVIDENCE_ASSERTIONS = {
  'fresh-character-create': 'fresh_character_create',
  'gold-or-shop-economy': 'gold_or_shop_economy',
  'two-browser-room-join': 'two_browser_room_join',
  'speak-turn-handoff': 'speak_turn_handoff',
  'combat-sync-or-blocker': 'combat_sync',
};

class SmokeError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'SmokeError';
    this.details = details;
  }
}

function requiredOptionValue(argv, index, optionName) {
  const value = argv[index + 1] || '';
  if (!value || value.startsWith('--')) {
    throw new Error(`${optionName} requires a value.`);
  }
  return value;
}

function requiredInlineOptionValue(value, optionName) {
  if (!value) {
    throw new Error(`${optionName} requires a value.`);
  }
  return value;
}

function parsePositiveMs(value, optionName) {
  const timeoutMs = Number(value);
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error(`${optionName} must be a positive number.`);
  }
  return timeoutMs;
}

function parseInteger(value, optionName) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed)) {
    throw new Error(`${optionName} must be an integer.`);
  }
  return parsed;
}

function parseBooleanOption(value, optionName) {
  const normalized = String(value || '').trim().toLowerCase();
  if (['1', 'true', 'yes', 'y', 'on'].includes(normalized)) return true;
  if (['0', 'false', 'no', 'n', 'off'].includes(normalized)) return false;
  throw new Error(`${optionName} must be true or false.`);
}

function todayTag() {
  const now = new Date();
  return [
    String(now.getFullYear()),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('');
}

function safeTagPart(value) {
  return String(value || '')
    .trim()
    .replace(/[^A-Za-z0-9_.-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
}

function normalizeArtifactTag(value) {
  const tag = safeTagPart(value);
  if (!tag) {
    throw new Error(`Unsupported artifact tag "${value}".`);
  }
  return tag;
}

export function normalizeBaseUrl(value, optionName = 'URL') {
  const raw = String(value || '').trim();
  if (!raw) return '';
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`${optionName} must be an http(s) URL, got "${value}".`);
  }
  if (!/^https?:$/.test(parsed.protocol)) {
    throw new Error(`${optionName} must be an http(s) URL, got "${value}".`);
  }
  parsed.hash = '';
  parsed.search = '';
  const pathname = parsed.pathname.replace(/\/+$/, '');
  return `${parsed.origin}${pathname === '/' ? '' : pathname}`;
}

export function defaultApiOrigin(frontendOrigin) {
  const origin = normalizeBaseUrl(frontendOrigin, '--frontend-origin');
  return origin ? `${origin}/api` : '';
}

export function defaultOutputPath(artifactTag) {
  return path.resolve(root, 'artifacts', `stage8-public-evidence-${artifactTag}.json`);
}

export function parseArgs(argv = process.argv.slice(2), env = process.env) {
  const args = {
    allowCombatSyncBlocker: env.STAGE8_PUBLIC_ALLOW_COMBAT_SYNC_BLOCKER
      ? parseBooleanOption(env.STAGE8_PUBLIC_ALLOW_COMBAT_SYNC_BLOCKER, 'STAGE8_PUBLIC_ALLOW_COMBAT_SYNC_BLOCKER')
      : false,
    apiOrigin: env.STAGE8_PUBLIC_API_ORIGIN || '',
    artifactTag: env.STAGE8_PUBLIC_ARTIFACT_TAG || todayTag(),
    attemptCombatSync: env.STAGE8_PUBLIC_ATTEMPT_COMBAT_SYNC
      ? parseBooleanOption(env.STAGE8_PUBLIC_ATTEMPT_COMBAT_SYNC, 'STAGE8_PUBLIC_ATTEMPT_COMBAT_SYNC')
      : false,
    combatActionText: env.STAGE8_PUBLIC_COMBAT_ACTION_TEXT || DEFAULT_COMBAT_ACTION_TEXT,
    frontendOrigin: env.STAGE8_PUBLIC_FRONTEND_ORIGIN || '',
    guestPassword: env.STAGE8_PUBLIC_GUEST_PASSWORD || 'stage8pass',
    guestUsername: env.STAGE8_PUBLIC_GUEST_USERNAME || '',
    help: false,
    moduleId: env.STAGE8_PUBLIC_MODULE_ID || '',
    modulePollMs: env.STAGE8_PUBLIC_MODULE_POLL_MS
      ? parsePositiveMs(env.STAGE8_PUBLIC_MODULE_POLL_MS, 'STAGE8_PUBLIC_MODULE_POLL_MS')
      : DEFAULT_MODULE_POLL_MS,
    output: env.STAGE8_PUBLIC_OUTPUT || '',
    password: env.STAGE8_PUBLIC_PASSWORD || '',
    shopSetupGold: env.STAGE8_PUBLIC_SHOP_SETUP_GOLD
      ? parseInteger(env.STAGE8_PUBLIC_SHOP_SETUP_GOLD, 'STAGE8_PUBLIC_SHOP_SETUP_GOLD')
      : DEFAULT_SHOP_SETUP_GOLD,
    timeoutMs: env.STAGE8_PUBLIC_TIMEOUT_MS
      ? parsePositiveMs(env.STAGE8_PUBLIC_TIMEOUT_MS, 'STAGE8_PUBLIC_TIMEOUT_MS')
      : DEFAULT_TIMEOUT_MS,
    username: env.STAGE8_PUBLIC_USERNAME || '',
    wsApiBase: env.STAGE8_PUBLIC_WS_API_BASE || '',
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
      continue;
    }
    if (arg === '--frontend-origin') {
      args.frontendOrigin = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--frontend-origin=')) {
      args.frontendOrigin = requiredInlineOptionValue(arg.slice('--frontend-origin='.length), '--frontend-origin');
      continue;
    }
    if (arg === '--api-origin') {
      args.apiOrigin = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--api-origin=')) {
      args.apiOrigin = requiredInlineOptionValue(arg.slice('--api-origin='.length), '--api-origin');
      continue;
    }
    if (arg === '--ws-api-base') {
      args.wsApiBase = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--ws-api-base=')) {
      args.wsApiBase = requiredInlineOptionValue(arg.slice('--ws-api-base='.length), '--ws-api-base');
      continue;
    }
    if (arg === '--username') {
      args.username = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--username=')) {
      args.username = requiredInlineOptionValue(arg.slice('--username='.length), '--username');
      continue;
    }
    if (arg === '--password') {
      args.password = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--password=')) {
      args.password = requiredInlineOptionValue(arg.slice('--password='.length), '--password');
      continue;
    }
    if (arg === '--module-id') {
      args.moduleId = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--module-id=')) {
      args.moduleId = requiredInlineOptionValue(arg.slice('--module-id='.length), '--module-id');
      continue;
    }
    if (arg === '--guest-username') {
      args.guestUsername = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--guest-username=')) {
      args.guestUsername = requiredInlineOptionValue(arg.slice('--guest-username='.length), '--guest-username');
      continue;
    }
    if (arg === '--guest-password') {
      args.guestPassword = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--guest-password=')) {
      args.guestPassword = requiredInlineOptionValue(arg.slice('--guest-password='.length), '--guest-password');
      continue;
    }
    if (arg === '--artifact-tag') {
      args.artifactTag = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--artifact-tag=')) {
      args.artifactTag = requiredInlineOptionValue(arg.slice('--artifact-tag='.length), '--artifact-tag');
      continue;
    }
    if (arg === '--output') {
      args.output = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--output=')) {
      args.output = requiredInlineOptionValue(arg.slice('--output='.length), '--output');
      continue;
    }
    if (arg === '--timeout-ms') {
      args.timeoutMs = parsePositiveMs(requiredOptionValue(argv, index, arg), arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--timeout-ms=')) {
      args.timeoutMs = parsePositiveMs(requiredInlineOptionValue(arg.slice('--timeout-ms='.length), '--timeout-ms'), '--timeout-ms');
      continue;
    }
    if (arg === '--module-poll-ms') {
      args.modulePollMs = parsePositiveMs(requiredOptionValue(argv, index, arg), arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--module-poll-ms=')) {
      args.modulePollMs = parsePositiveMs(requiredInlineOptionValue(arg.slice('--module-poll-ms='.length), '--module-poll-ms'), '--module-poll-ms');
      continue;
    }
    if (arg === '--shop-setup-gold') {
      args.shopSetupGold = parseInteger(requiredOptionValue(argv, index, arg), arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--shop-setup-gold=')) {
      args.shopSetupGold = parseInteger(requiredInlineOptionValue(arg.slice('--shop-setup-gold='.length), '--shop-setup-gold'), '--shop-setup-gold');
      continue;
    }
    if (arg === '--combat-action-text') {
      args.combatActionText = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--combat-action-text=')) {
      args.combatActionText = requiredInlineOptionValue(arg.slice('--combat-action-text='.length), '--combat-action-text');
      continue;
    }
    if (arg === '--attempt-combat-sync') {
      args.attemptCombatSync = true;
      continue;
    }
    if (arg === '--allow-combat-sync-blocker') {
      args.allowCombatSyncBlocker = true;
      continue;
    }
    throw new Error(`Unknown option: ${arg}`);
  }

  if (args.help) return args;
  args.frontendOrigin = normalizeBaseUrl(args.frontendOrigin, '--frontend-origin');
  args.apiOrigin = normalizeBaseUrl(args.apiOrigin || defaultApiOrigin(args.frontendOrigin), '--api-origin');
  args.wsApiBase = normalizeBaseUrl(args.wsApiBase || args.apiOrigin, '--ws-api-base');
  args.artifactTag = normalizeArtifactTag(args.artifactTag);
  if (!args.output) args.output = defaultOutputPath(args.artifactTag);
  args.output = path.isAbsolute(args.output) ? args.output : path.resolve(root, args.output);
  args.moduleId = String(args.moduleId || '').trim();
  args.username = String(args.username || '').trim();
  args.password = String(args.password || '').trim();
  args.guestUsername = String(args.guestUsername || '').trim();
  args.guestPassword = String(args.guestPassword || '').trim();
  args.combatActionText = String(args.combatActionText || '').trim() || DEFAULT_COMBAT_ACTION_TEXT;
  return args;
}

export function usage() {
  return [
    'Usage:',
    '  node scripts/stage8_public_evidence_smoke.mjs --frontend-origin <url> --username <user> --password <pass> [--module-id <id>] [--output <json>]',
    '',
    'Runs public Stage 8 API/WebSocket evidence checks for fresh character creation, shop economy, room join, and speak-turn handoff.',
    '',
    'Options:',
    '  --api-origin <url>                 API base URL. Defaults to <frontend-origin>/api.',
    '  --ws-api-base <url>                WebSocket API base. Defaults to --api-origin.',
    '  --module-id <id>                   Reuse a parsed module. Otherwise the script picks the newest parsed module or uploads a tiny txt module.',
    '  --guest-username <user>            Optional reusable guest account. Omitted means a short disposable account is registered.',
    '  --guest-password <pass>            Guest password. Defaults to stage8pass.',
    '  --attempt-combat-sync              Try a real multiplayer combat trigger through /game/action.',
    '  --allow-combat-sync-blocker        Let the artifact finish with a documented combat-sync blocker when no deterministic public combat sync is available.',
  ].join('\n');
}

function validateRequiredArgs(args) {
  const missing = [];
  if (!args.frontendOrigin) missing.push('--frontend-origin');
  if (!args.apiOrigin) missing.push('--api-origin');
  if (!args.username) missing.push('--username');
  if (!args.password) missing.push('--password');
  if (!args.wsApiBase) missing.push('--ws-api-base');
  if (!args.output) missing.push('--output');
  if (missing.length) {
    throw new Error(`Missing required option(s): ${missing.join(', ')}`);
  }
}

function uniqueSuffix() {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).slice(2, 7);
  return `${timestamp}${random}`;
}

function authHeaders(token) {
  return token ? { authorization: `Bearer ${token}` } : {};
}

function apiUrl(apiOrigin, urlPath) {
  const cleanPath = String(urlPath || '').startsWith('/') ? urlPath : `/${urlPath}`;
  return `${apiOrigin.replace(/\/+$/, '')}${cleanPath}`;
}

async function readResponseBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function requestJson({
  apiOrigin,
  body = undefined,
  headers = {},
  method = 'GET',
  timeoutMs,
  token = '',
  urlPath,
}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(apiUrl(apiOrigin, urlPath), {
      method,
      headers: {
        accept: 'application/json',
        ...(body === undefined ? {} : { 'content-type': 'application/json' }),
        ...authHeaders(token),
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const responseBody = await readResponseBody(response);
    if (!response.ok) {
      throw new SmokeError(`${method} ${urlPath} failed with HTTP ${response.status}`, {
        body: responseBody,
        status: response.status,
        url: apiUrl(apiOrigin, urlPath),
      });
    }
    return {
      body: responseBody,
      ok: true,
      status: response.status,
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function postForm({
  apiOrigin,
  form,
  timeoutMs,
  token,
  urlPath,
}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(apiUrl(apiOrigin, urlPath), {
      method: 'POST',
      headers: {
        accept: 'application/json',
        ...authHeaders(token),
      },
      body: form,
      signal: controller.signal,
    });
    const responseBody = await readResponseBody(response);
    if (!response.ok) {
      throw new SmokeError(`POST ${urlPath} failed with HTTP ${response.status}`, {
        body: responseBody,
        status: response.status,
        url: apiUrl(apiOrigin, urlPath),
      });
    }
    return {
      body: responseBody,
      ok: true,
      status: response.status,
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function waitFor(label, fn, timeoutMs, intervalMs = 250) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() <= deadline) {
    try {
      const value = await fn();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
  const suffix = lastError ? ` Last error: ${lastError.message || String(lastError)}` : '';
  throw new SmokeError(`${label} timed out after ${timeoutMs}ms.${suffix}`);
}

async function login(apiOrigin, username, password, timeoutMs) {
  const response = await requestJson({
    apiOrigin,
    body: { username, password },
    method: 'POST',
    timeoutMs,
    urlPath: '/auth/login',
  });
  const body = response.body || {};
  if (!body.token || !body.user_id) {
    throw new SmokeError('Login response did not include token and user_id.', { body });
  }
  return body;
}

async function registerOrLogin(apiOrigin, username, password, timeoutMs) {
  try {
    const response = await requestJson({
      apiOrigin,
      body: { username, password, display_name: username },
      method: 'POST',
      timeoutMs,
      urlPath: '/auth/register',
    });
    return {
      ...response.body,
      registered: true,
    };
  } catch (error) {
    if (error instanceof SmokeError && error.details?.status === 409) {
      const user = await login(apiOrigin, username, password, timeoutMs);
      return {
        ...user,
        registered: false,
      };
    }
    throw error;
  }
}

async function uploadSmokeModule(apiOrigin, token, timeoutMs) {
  const form = new FormData();
  form.append('file', new Blob([SMOKE_MODULE_TEXT], { type: 'text/plain' }), `stage8-public-${uniqueSuffix()}.txt`);
  const response = await postForm({
    apiOrigin,
    form,
    timeoutMs,
    token,
    urlPath: '/modules/upload',
  });
  if (!response.body?.id) {
    throw new SmokeError('Module upload response did not include id.', { body: response.body });
  }
  return response.body.id;
}

async function ensureParsedModule({
  apiOrigin,
  moduleId,
  modulePollMs,
  timeoutMs,
  token,
}) {
  if (moduleId) {
    const response = await requestJson({
      apiOrigin,
      timeoutMs,
      token,
      urlPath: `/modules/${encodeURIComponent(moduleId)}`,
    });
    if (response.body?.parse_status !== 'done') {
      throw new SmokeError(`Module ${moduleId} is not parsed yet.`, { module: response.body });
    }
    return {
      id: response.body.id,
      name: response.body.name,
      source: 'provided',
    };
  }

  const modulesResponse = await requestJson({
    apiOrigin,
    timeoutMs,
    token,
    urlPath: '/modules/',
  });
  const modules = Array.isArray(modulesResponse.body) ? modulesResponse.body : [];
  const readyModule = modules.find(item => item?.id && item?.parse_status === 'done');
  if (readyModule) {
    return {
      id: readyModule.id,
      name: readyModule.name,
      source: 'existing',
    };
  }

  const uploadedId = await uploadSmokeModule(apiOrigin, token, timeoutMs);
  const parsed = await waitFor('Stage 8 smoke module parsing', async () => {
    const response = await requestJson({
      apiOrigin,
      timeoutMs,
      token,
      urlPath: `/modules/${encodeURIComponent(uploadedId)}`,
    });
    if (response.body?.parse_status === 'done') return response.body;
    if (response.body?.parse_status === 'failed') {
      throw new SmokeError('Uploaded smoke module parsing failed.', { module: response.body });
    }
    return null;
  }, modulePollMs, 1000);
  return {
    id: parsed.id,
    name: parsed.name,
    source: 'uploaded',
  };
}

function characterPayload(moduleId, name, equipmentChoice = 0) {
  return {
    module_id: moduleId,
    name,
    race: 'Human',
    char_class: 'Fighter',
    level: 1,
    ability_scores: {
      str: 14,
      dex: 12,
      con: 13,
      int: 10,
      wis: 10,
      cha: 10,
    },
    proficient_skills: ['\u8fd0\u52a8', '\u611f\u77e5'],
    equipment_choice: equipmentChoice,
  };
}

async function createCharacter(apiOrigin, token, moduleId, name, timeoutMs) {
  const response = await requestJson({
    apiOrigin,
    body: characterPayload(moduleId, name),
    method: 'POST',
    timeoutMs,
    token,
    urlPath: '/characters/create',
  });
  if (!response.body?.id) {
    throw new SmokeError('Character create response did not include id.', { body: response.body });
  }
  return response.body;
}

function preferredShopItem(inventory, maxCost = DEFAULT_SHOP_SETUP_GOLD) {
  const gear = inventory?.gear || {};
  if (gear['Healing Potion']) {
    return {
      category: 'gear',
      cost: Number(gear['Healing Potion'].cost || 50),
      name: 'Healing Potion',
    };
  }
  const candidates = [];
  for (const category of ['gear', 'weapon', 'armor']) {
    const items = inventory?.[category === 'weapon' ? 'weapons' : category] || {};
    for (const [name, data] of Object.entries(items)) {
      const cost = Number(data?.cost || 0);
      if (Number.isFinite(cost) && cost > 0 && cost <= maxCost) {
        candidates.push({ category, cost, name });
      }
    }
  }
  candidates.sort((a, b) => a.cost - b.cost || a.name.localeCompare(b.name));
  return candidates[0] || null;
}

async function runCharacterAndEconomy({
  apiOrigin,
  moduleId,
  shopSetupGold = DEFAULT_SHOP_SETUP_GOLD,
  timeoutMs,
  token,
}) {
  const suffix = uniqueSuffix();
  const character = await createCharacter(apiOrigin, token, moduleId, `Stage8 Hero ${suffix}`, timeoutMs);
  const detail = await requestJson({
    apiOrigin,
    timeoutMs,
    token,
    urlPath: `/characters/${encodeURIComponent(character.id)}`,
  });
  const goldPatch = await requestJson({
    apiOrigin,
    body: {
      amount: shopSetupGold,
      reason: 'stage8 public economy smoke setup',
    },
    method: 'PATCH',
    timeoutMs,
    token,
    urlPath: `/characters/${encodeURIComponent(character.id)}/gold`,
  });
  const inventory = await requestJson({
    apiOrigin,
    timeoutMs,
    token,
    urlPath: `/characters/shop/inventory?character_id=${encodeURIComponent(character.id)}`,
  });
  const item = preferredShopItem(inventory.body, shopSetupGold);
  if (!item) {
    throw new SmokeError('Could not find an affordable shop item for the Stage 8 economy smoke.', {
      inventory: inventory.body,
    });
  }
  const buy = await requestJson({
    apiOrigin,
    body: {
      item_name: item.name,
      item_category: item.category,
      quantity: 1,
    },
    method: 'POST',
    timeoutMs,
    token,
    urlPath: `/characters/${encodeURIComponent(character.id)}/shop/buy`,
  });
  const sell = await requestJson({
    apiOrigin,
    body: {
      item_name: item.name,
      item_category: item.category,
      item_index: 0,
    },
    method: 'POST',
    timeoutMs,
    token,
    urlPath: `/characters/${encodeURIComponent(character.id)}/shop/sell`,
  });

  return {
    character: {
      id: character.id,
      name: character.name,
      detail_ok: detail.body?.id === character.id,
      hp_current: detail.body?.hp_current,
      hp_max: detail.body?.hp_max,
    },
    economy: {
      buy_cost: buy.body?.cost,
      buy_gold_remaining: buy.body?.gold_remaining,
      gold_after_patch: goldPatch.body?.gold,
      item_category: item.category,
      item_name: item.name,
      sell_gold_remaining: sell.body?.gold_remaining,
      sell_price: sell.body?.sell_price,
      shop_inventory_ok: inventory.ok === true,
    },
    checks: {
      character_detail_ok: detail.body?.id === character.id,
      fresh_character_create_ok: Boolean(character.id && detail.body?.id === character.id),
      gold_patch_ok: typeof goldPatch.body?.gold === 'number',
      gold_decreased_on_buy: Number(buy.body?.gold_remaining) < Number(goldPatch.body?.gold),
      gold_increased_on_sell: Number(sell.body?.gold_remaining) > Number(buy.body?.gold_remaining),
      shop_buy_ok: buy.body?.bought === item.name,
      shop_inventory_ok: inventory.ok === true && Boolean(item.name),
      shop_sell_ok: sell.body?.sold === item.name,
    },
  };
}

function wsUrl(wsApiBase, sessionId, token) {
  const parsed = new URL(wsApiBase);
  parsed.protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
  parsed.pathname = `${parsed.pathname.replace(/\/+$/, '')}/ws/sessions/${encodeURIComponent(sessionId)}`;
  parsed.search = `?token=${encodeURIComponent(token)}`;
  return parsed.toString();
}

function parseWsData(data) {
  if (typeof data === 'string') return JSON.parse(data);
  if (data instanceof ArrayBuffer) return JSON.parse(Buffer.from(data).toString('utf8'));
  if (ArrayBuffer.isView(data)) return JSON.parse(Buffer.from(data.buffer, data.byteOffset, data.byteLength).toString('utf8'));
  return JSON.parse(String(data));
}

async function connectWsClient({ label, sessionId, timeoutMs, token, wsApiBase }) {
  const events = [];
  const url = wsUrl(wsApiBase, sessionId, token);
  const ws = new WebSocket(url);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      try { ws.close(); } catch {}
      reject(new SmokeError(`${label} WebSocket did not open within ${timeoutMs}ms.`, { url }));
    }, timeoutMs);
    ws.addEventListener('open', () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
    ws.addEventListener('error', event => {
      clearTimeout(timer);
      reject(new SmokeError(`${label} WebSocket failed to connect.`, { event: String(event), url }));
    }, { once: true });
  });
  ws.addEventListener('message', event => {
    try {
      events.push(parseWsData(event.data));
    } catch (error) {
      events.push({
        type: 'parse_error',
        message: error.message || String(error),
      });
    }
  });
  return {
    close() {
      try { ws.close(); } catch {}
    },
    events,
    label,
    send(payload) {
      ws.send(JSON.stringify(payload));
    },
    url,
    ws,
  };
}

async function waitForWsEvent(client, label, predicate, timeoutMs) {
  return waitFor(label, () => client.events.find(predicate), timeoutMs, 100);
}

function roomMember(room, userId) {
  return (room?.members || []).find(member => member?.user_id === userId);
}

async function runOptionalCombatSync({
  apiOrigin,
  combatActionText,
  guest,
  guestWs,
  host,
  hostWs,
  sessionId,
  timeoutMs,
}) {
  const actionResponse = await requestJson({
    apiOrigin,
    body: {
      action_source: 'human_input',
      action_text: combatActionText,
      idempotency_key: `stage8-combat-sync-${uniqueSuffix()}`,
      session_id: sessionId,
    },
    method: 'POST',
    timeoutMs,
    token: guest.token,
    urlPath: '/game/action',
  });
  const combatTriggered = actionResponse.body?.combat_triggered === true;
  if (!combatTriggered) {
    return {
      attempted: true,
      combat_sync: false,
      reason: 'The deployed DM action did not trigger combat for the public multiplayer room.',
      response_type: actionResponse.body?.type || '',
    };
  }
  await waitForWsEvent(hostWs, 'host combat-trigger broadcast', event => {
    return event?.type === 'dm_responded' && event?.combat_triggered === true;
  }, timeoutMs);
  await waitForWsEvent(guestWs, 'guest combat-trigger broadcast', event => {
    return event?.type === 'dm_responded' && event?.combat_triggered === true;
  }, timeoutMs);
  const hostCombat = await requestJson({
    apiOrigin,
    timeoutMs,
    token: host.token,
    urlPath: `/game/combat/${encodeURIComponent(sessionId)}`,
  });
  const guestCombat = await requestJson({
    apiOrigin,
    timeoutMs,
    token: guest.token,
    urlPath: `/game/combat/${encodeURIComponent(sessionId)}`,
  });
  return {
    attempted: true,
    combat_active_host: Boolean(hostCombat.body?.active || hostCombat.body?.combat_active || hostCombat.body?.entities),
    combat_active_guest: Boolean(guestCombat.body?.active || guestCombat.body?.combat_active || guestCombat.body?.entities),
    combat_sync: Boolean(hostCombat.body?.entities && guestCombat.body?.entities),
    response_type: actionResponse.body?.type || '',
  };
}

async function runMultiplayer({
  apiOrigin,
  attemptCombatSync,
  combatActionText,
  moduleId,
  timeoutMs,
  token,
  user,
  wsApiBase,
  guestPassword,
  guestUsername,
}) {
  const suffix = uniqueSuffix();
  const guestName = guestUsername || `s8g_${suffix}`.slice(0, 30);
  const guest = await registerOrLogin(apiOrigin, guestName, guestPassword, timeoutMs);
  const hostCharacter = await createCharacter(apiOrigin, token, moduleId, `Stage8 Host ${suffix}`, timeoutMs);
  const guestCharacter = await createCharacter(apiOrigin, token, moduleId, `Stage8 Guest ${suffix}`, timeoutMs);
  const roomCreate = await requestJson({
    apiOrigin,
    body: {
      max_players: 2,
      module_id: moduleId,
      save_name: `Stage8 Evidence ${suffix}`,
    },
    method: 'POST',
    timeoutMs,
    token,
    urlPath: '/game/rooms/create',
  });
  const sessionId = roomCreate.body?.session_id;
  const roomCode = roomCreate.body?.room_code;
  if (!sessionId || !roomCode) {
    throw new SmokeError('Room create response did not include session_id and room_code.', { body: roomCreate.body });
  }
  const join = await requestJson({
    apiOrigin,
    body: { room_code: roomCode },
    method: 'POST',
    timeoutMs,
    token: guest.token,
    urlPath: '/game/rooms/join',
  });
  await requestJson({
    apiOrigin,
    body: { character_id: hostCharacter.id },
    method: 'POST',
    timeoutMs,
    token,
    urlPath: `/game/rooms/${encodeURIComponent(sessionId)}/claim-character`,
  });
  await requestJson({
    apiOrigin,
    body: { character_id: guestCharacter.id },
    method: 'POST',
    timeoutMs,
    token: guest.token,
    urlPath: `/game/rooms/${encodeURIComponent(sessionId)}/claim-character`,
  });
  await requestJson({
    apiOrigin,
    body: { ready: true },
    method: 'POST',
    timeoutMs,
    token,
    urlPath: `/game/rooms/${encodeURIComponent(sessionId)}/start-ready`,
  });
  await requestJson({
    apiOrigin,
    body: { ready: true },
    method: 'POST',
    timeoutMs,
    token: guest.token,
    urlPath: `/game/rooms/${encodeURIComponent(sessionId)}/start-ready`,
  });
  const start = await requestJson({
    apiOrigin,
    method: 'POST',
    timeoutMs,
    token,
    urlPath: `/game/rooms/${encodeURIComponent(sessionId)}/start`,
  });

  const hostWs = await connectWsClient({
    label: 'host',
    sessionId,
    timeoutMs,
    token,
    wsApiBase,
  });
  const guestWs = await connectWsClient({
    label: 'guest',
    sessionId,
    timeoutMs,
    token: guest.token,
    wsApiBase,
  });

  try {
    hostWs.send({ type: 'ping' });
    guestWs.send({ type: 'ping' });
    await waitForWsEvent(hostWs, 'host ping/pong', event => event?.type === 'pong', timeoutMs);
    await waitForWsEvent(guestWs, 'guest ping/pong', event => event?.type === 'pong', timeoutMs);

    const onlineRoom = await waitFor('both multiplayer members online', async () => {
      const room = await requestJson({
        apiOrigin,
        timeoutMs,
        token,
        urlPath: `/game/rooms/${encodeURIComponent(sessionId)}`,
      });
      const body = room.body || {};
      const hostMember = roomMember(body, user.user_id);
      const guestMember = roomMember(body, guest.user_id);
      return hostMember?.is_online && guestMember?.is_online ? body : null;
    }, timeoutMs, 500);

    if (onlineRoom.current_speaker_user_id !== user.user_id) {
      throw new SmokeError('Expected the host to be the initial current speaker.', {
        current_speaker_user_id: onlineRoom.current_speaker_user_id,
        host_user_id: user.user_id,
      });
    }

    hostWs.send({ type: 'speak_done' });
    const handoffRoom = await waitFor('speak turn handoff to guest', async () => {
      const room = await requestJson({
        apiOrigin,
        timeoutMs,
        token,
        urlPath: `/game/rooms/${encodeURIComponent(sessionId)}`,
      });
      return room.body?.current_speaker_user_id === guest.user_id ? room.body : null;
    }, timeoutMs, 500);
    await waitForWsEvent(guestWs, 'guest speak-turn websocket event', event => {
      return event?.type === 'dm_speak_turn' && event?.user_id === guest.user_id;
    }, timeoutMs);

    const combatSync = attemptCombatSync
      ? await runOptionalCombatSync({
          apiOrigin,
          combatActionText,
          guest,
          guestWs,
          host: { ...user, token },
          hostWs,
          sessionId,
          timeoutMs,
        })
      : {
          attempted: false,
          combat_sync: false,
          reason: 'No deterministic public multiplayer combat seed was provided to this API/WS smoke.',
        };

    return {
      checks: {
        game_started_ok: start.body?.started === true,
        guest_joined_ok: join.body?.session_id === sessionId,
        host_ws_pong_ok: hostWs.events.some(event => event?.type === 'pong'),
        guest_ws_pong_ok: guestWs.events.some(event => event?.type === 'pong'),
        two_browser_room_join_ok: Boolean(roomMember(onlineRoom, user.user_id) && roomMember(onlineRoom, guest.user_id)),
        websocket_online_ok: roomMember(onlineRoom, user.user_id)?.is_online === true
          && roomMember(onlineRoom, guest.user_id)?.is_online === true,
        speak_turn_handoff_ok: handoffRoom.current_speaker_user_id === guest.user_id,
        combat_sync_ok: combatSync.combat_sync === true,
      },
      combat_sync: combatSync,
      guest: {
        registered: guest.registered === true,
        user_id: guest.user_id,
        username: guest.username,
      },
      room: {
        current_speaker_after_handoff: handoffRoom.current_speaker_user_id,
        current_speaker_initial: onlineRoom.current_speaker_user_id,
        guest_character_id: guestCharacter.id,
        host_character_id: hostCharacter.id,
        member_count: Array.isArray(onlineRoom.members) ? onlineRoom.members.length : 0,
        room_code: roomCode,
        session_id: sessionId,
      },
      websocket: {
        guest_event_count: guestWs.events.length,
        host_event_count: hostWs.events.length,
      },
    };
  } finally {
    hostWs.close();
    guestWs.close();
  }
}

function buildBlockers({ allowCombatSyncBlocker, multiplayer }) {
  const blockers = [];
  if (multiplayer?.checks?.two_browser_room_join_ok !== true) {
    blockers.push({
      accepted: false,
      covers: ['two-browser-room-join'],
      next_action: 'Fix the deployed WebSocket proxy and rerun scripts/stage8_public_evidence_smoke.mjs until host and guest clients both connect to the same room.',
      reason: multiplayer?.error?.message || 'Public two-client room join over WebSocket was not verified.',
    });
  }
  if (multiplayer?.checks?.speak_turn_handoff_ok !== true) {
    blockers.push({
      accepted: false,
      covers: ['speak-turn-handoff'],
      next_action: 'After WebSocket connectivity is restored, rerun the Stage 8 public evidence smoke and confirm speak turn advances from host to guest.',
      reason: multiplayer?.error?.message || 'Public speak-turn handoff over WebSocket was not verified.',
    });
  }
  if (multiplayer?.combat_sync?.combat_sync !== true) {
    blockers.push({
      accepted: allowCombatSyncBlocker === true,
      covers: ['combat-sync-or-blocker'],
      next_action: 'Run a deterministic public multiplayer combat seed or rerun this smoke with --attempt-combat-sync after confirming the deployed DM action reliably enters combat.',
      reason: multiplayer?.combat_sync?.reason || 'Public multiplayer combat sync was not verified by this API/WS smoke.',
    });
  }
  return blockers;
}

export function buildArtifact({
  allowCombatSyncBlocker,
  apiOrigin,
  characterEconomy,
  createdAt = new Date().toISOString(),
  frontendOrigin,
  module,
  multiplayer,
  username,
  user,
  wsApiBase,
}) {
  const blockers = buildBlockers({ allowCombatSyncBlocker, multiplayer });
  const checks = {
    login_ok: Boolean(user?.token && user?.user_id),
    module_ready_ok: Boolean(module?.id),
    ...(characterEconomy?.checks || {}),
    ...(multiplayer?.checks || {}),
    combat_sync_blocker_documented: blockers.some(blocker => blocker.covers?.includes('combat-sync-or-blocker')
      && blocker.reason
      && blocker.next_action),
  };
  const assertions = {
    combat_sync: checks.combat_sync_ok === true,
    fresh_character_create: checks.fresh_character_create_ok === true && checks.character_detail_ok === true,
    gold_or_shop_economy: checks.gold_patch_ok === true
      && checks.shop_inventory_ok === true
      && checks.shop_buy_ok === true
      && checks.shop_sell_ok === true
      && checks.gold_decreased_on_buy === true
      && checks.gold_increased_on_sell === true,
    speak_turn_handoff: checks.speak_turn_handoff_ok === true,
    two_browser_room_join: checks.two_browser_room_join_ok === true && checks.websocket_online_ok === true,
  };
  const ok = assertions.fresh_character_create
    && assertions.gold_or_shop_economy
    && assertions.two_browser_room_join
    && assertions.speak_turn_handoff
    && (assertions.combat_sync || (allowCombatSyncBlocker && checks.combat_sync_blocker_documented));
  return {
    ok,
    mode: 'stage8-public-evidence-smoke',
    created_at: createdAt,
    frontend_origin: frontendOrigin,
    api_origin: apiOrigin,
    ws_api_base: wsApiBase,
    username,
    user_id: user?.user_id || '',
    module,
    checks,
    assertions,
    character_create: characterEconomy?.character || null,
    economy: characterEconomy?.economy || null,
    multiplayer: multiplayer ? {
      combat_sync: multiplayer.combat_sync,
      error: multiplayer.error || null,
      guest: multiplayer.guest,
      room: multiplayer.room,
      websocket: multiplayer.websocket,
    } : null,
    blockers,
  };
}

async function writeJsonArtifact(filePath, value) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

export async function runStage8PublicEvidenceSmoke(args) {
  validateRequiredArgs(args);
  const user = await login(args.apiOrigin, args.username, args.password, args.timeoutMs);
  const module = await ensureParsedModule({
    apiOrigin: args.apiOrigin,
    moduleId: args.moduleId,
    modulePollMs: args.modulePollMs,
    timeoutMs: args.timeoutMs,
    token: user.token,
  });
  const characterEconomy = await runCharacterAndEconomy({
    apiOrigin: args.apiOrigin,
    moduleId: module.id,
    shopSetupGold: args.shopSetupGold,
    timeoutMs: args.timeoutMs,
    token: user.token,
  });
  let multiplayer;
  try {
    multiplayer = await runMultiplayer({
      apiOrigin: args.apiOrigin,
      attemptCombatSync: args.attemptCombatSync,
      combatActionText: args.combatActionText,
      guestPassword: args.guestPassword,
      guestUsername: args.guestUsername,
      moduleId: module.id,
      timeoutMs: args.timeoutMs,
      token: user.token,
      user,
      wsApiBase: args.wsApiBase,
    });
  } catch (error) {
    multiplayer = {
      checks: {
        combat_sync_ok: false,
        speak_turn_handoff_ok: false,
        two_browser_room_join_ok: false,
        websocket_online_ok: false,
      },
      combat_sync: {
        attempted: args.attemptCombatSync,
        combat_sync: false,
        reason: 'Multiplayer WebSocket evidence did not complete.',
      },
      error: {
        details: error.details || {},
        message: error.message || String(error),
      },
      guest: null,
      room: null,
      websocket: null,
    };
  }
  const artifact = buildArtifact({
    allowCombatSyncBlocker: args.allowCombatSyncBlocker,
    apiOrigin: args.apiOrigin,
    characterEconomy,
    frontendOrigin: args.frontendOrigin,
    module,
    multiplayer,
    username: args.username,
    user,
    wsApiBase: args.wsApiBase,
  });
  await writeJsonArtifact(args.output, artifact);
  return {
    artifact,
    output: args.output,
  };
}

async function main() {
  const args = parseArgs();
  if (args.help) {
    console.log(usage());
    return 0;
  }
  try {
    const result = await runStage8PublicEvidenceSmoke(args);
    console.log(JSON.stringify({
      ok: result.artifact.ok,
      output: result.output,
      assertions: result.artifact.assertions,
      blockers: result.artifact.blockers,
    }, null, 2));
    return result.artifact.ok ? 0 : 1;
  } catch (error) {
    const failure = {
      ok: false,
      error: error.message || String(error),
      details: error.details || {},
    };
    if (args.output) {
      await writeJsonArtifact(args.output, {
        ...failure,
        mode: 'stage8-public-evidence-smoke',
        created_at: new Date().toISOString(),
        frontend_origin: args.frontendOrigin || '',
        api_origin: args.apiOrigin || '',
        ws_api_base: args.wsApiBase || '',
        assertions: {},
        checks: {},
        blockers: [],
      }).catch(() => {});
    }
    console.error(JSON.stringify(failure, null, 2));
    return 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().then(
    code => {
      process.exitCode = code;
    },
    error => {
      console.error(error.stack || error.message || String(error));
      process.exitCode = 1;
    },
  );
}
