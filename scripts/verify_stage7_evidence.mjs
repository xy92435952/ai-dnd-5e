#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, '..');

function parseArgs(argv = process.argv.slice(2)) {
  const result = {
    files: [],
    type: 'auto',
    noFileCheck: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--type') {
      result.type = argv[index + 1] || '';
      index += 1;
      continue;
    }
    if (arg.startsWith('--type=')) {
      result.type = arg.slice('--type='.length);
      continue;
    }
    if (arg === '--no-file-check') {
      result.noFileCheck = true;
      continue;
    }
    if (arg === '--help' || arg === '-h') {
      result.help = true;
      continue;
    }
    result.files.push(arg);
  }

  return result;
}

function usage() {
  return [
    'Usage:',
    '  node scripts/verify_stage7_evidence.mjs [--type feather-fall|multiplayer-load|auto] [--no-file-check] <json-file> [more-json-files...]',
    '',
    'Checks:',
    '  feather-fall       verifies browser smoke manifest fields and screenshot paths',
    '  multiplayer-load   verifies load smoke result fields and summary counts',
    '  auto               infers the type from the JSON payload',
  ].join('\n');
}

function fail(message) {
  throw new Error(message);
}

async function loadJson(filePath) {
  const fullPath = path.isAbsolute(filePath) ? filePath : path.resolve(root, filePath);
  const raw = (await readFile(fullPath, 'utf8')).replace(/^\uFEFF/, '');
  return { fullPath, data: JSON.parse(raw) };
}

function inferType(data) {
  if (data?.mode === 'feather-fall-adventure-browser-smoke') return 'feather-fall';
  if (data?.base_url && Array.isArray(data?.room_sizes) && Object.prototype.hasOwnProperty.call(data, 'cleanup_ok')) {
    return 'multiplayer-load';
  }
  return 'unknown';
}

function ensure(condition, message) {
  if (!condition) fail(message);
}

function ensurePathExists(targetPath, label) {
  ensure(existsSync(targetPath), `${label} missing: ${targetPath}`);
}

function ensureNumber(value, message) {
  ensure(typeof value === 'number' && Number.isFinite(value), message);
}

function verifyFeatherFall(filePath, data, { noFileCheck }) {
  ensure(data.ok === true, `${filePath}: ok must be true`);
  ensure(data.mode === 'feather-fall-adventure-browser-smoke', `${filePath}: unexpected mode ${data.mode}`);
  ensure(data.decision === 'accept' || data.decision === 'decline', `${filePath}: decision must be accept or decline`);
  const expectedReactionType = data.decision === 'decline' ? 'decline' : 'feather_fall';
  ensure(data.reaction_type === expectedReactionType, `${filePath}: reaction_type must be ${expectedReactionType}`);
  ensure(typeof data.artifact_tag === 'string' && data.artifact_tag.length > 0, `${filePath}: artifact_tag missing`);
  ensure(data.assertions?.pending_cleared === true, `${filePath}: pending_cleared must be true`);
  ensureNumber(data.assertions?.fall_damage, `${filePath}: fall_damage missing`);
  ensureNumber(data.assertions?.before_hp, `${filePath}: before_hp missing`);
  ensureNumber(data.assertions?.expected_hp, `${filePath}: expected_hp missing`);
  ensureNumber(data.assertions?.actual_hp, `${filePath}: actual_hp missing`);
  ensureNumber(data.assertions?.hp_max, `${filePath}: hp_max missing`);
  ensureNumber(data.assertions?.expected_caster_1st_slots, `${filePath}: expected_caster_1st_slots missing`);
  ensureNumber(data.assertions?.actual_caster_1st_slots, `${filePath}: actual_caster_1st_slots missing`);
  ensure(data.assertions.actual_hp === data.assertions.expected_hp, `${filePath}: actual_hp must match expected_hp`);
  ensure(
    data.assertions.actual_caster_1st_slots === data.assertions.expected_caster_1st_slots,
    `${filePath}: actual_caster_1st_slots must match expected_caster_1st_slots`,
  );
  const expectedHpFromDecision = data.decision === 'decline'
    ? Math.max(0, data.assertions.before_hp - data.assertions.fall_damage)
    : data.assertions.before_hp;
  ensure(data.assertions.expected_hp === expectedHpFromDecision, `${filePath}: expected_hp does not match ${data.decision} semantics`);
  ensure(data.resolved?.pending_cleared === true, `${filePath}: resolved.pending_cleared must be true`);
  ensure(data.resolved?.hp_current === data.assertions.actual_hp, `${filePath}: resolved.hp_current must match actual_hp`);
  ensure(data.resolved?.caster_slots?.['1st'] === data.assertions.actual_caster_1st_slots, `${filePath}: resolved caster 1st slot must match actual_caster_1st_slots`);
  ensure(data.screenshots?.prompt, `${filePath}: prompt screenshot path missing`);
  ensure(data.screenshots?.resolved, `${filePath}: resolved screenshot path missing`);
  ensure(typeof data.manifest === 'string' && data.manifest.length > 0, `${filePath}: manifest path missing`);

  if (!noFileCheck) {
    ensurePathExists(data.manifest, `${filePath}: manifest file`);
    ensurePathExists(data.screenshots.prompt, `${filePath}: prompt screenshot`);
    ensurePathExists(data.screenshots.resolved, `${filePath}: resolved screenshot`);
  }
}

function verifyMultiplayerLoad(filePath, data, { noFileCheck }) {
  ensure(data.ok === true, `${filePath}: ok must be true`);
  ensure(typeof data.base_url === 'string' && data.base_url.length > 0, `${filePath}: base_url missing`);
  ensure(Array.isArray(data.room_sizes) && data.room_sizes.length === 13, `${filePath}: room_sizes must list 13 rooms`);
  ensure(data.users === 50, `${filePath}: users must be 50`);
  ensure(data.rooms === 13, `${filePath}: rooms must be 13`);
  ensure(data.websockets === 50, `${filePath}: websockets must be 50`);
  ensure(data.cleanup_ok === true, `${filePath}: cleanup_ok must be true`);
  ensure(data.cleanup_verification_ok === true, `${filePath}: cleanup_verification_ok must be true`);
  ensure(data.module_cleanup_ok === true, `${filePath}: module_cleanup_ok must be true`);
  ensure(data.seed_module_cleanup_ok === true, `${filePath}: seed_module_cleanup_ok must be true`);
  ensure(data.timings && typeof data.timings === 'object', `${filePath}: timings missing`);

  const summaryKeys = ['register_ms', 'login_ms', 'create_room_ms', 'join_room_ms', 'ws_connect_ms', 'ws_ping_pong_ms'];
  const hasSummary = summaryKeys.some(key => Object.prototype.hasOwnProperty.call(data.timings, key));
  ensure(hasSummary, `${filePath}: timings summary missing expected keys`);

  if (data.hold_observer) {
    ensure(typeof data.hold_observer.username === 'string', `${filePath}: hold_observer.username missing`);
    ensure(typeof data.hold_observer.room_code === 'string', `${filePath}: hold_observer.room_code missing`);
  }

  if (!noFileCheck) {
    if (data.result_json) {
      ensurePathExists(data.result_json, `${filePath}: result JSON`);
    }
  }
}

async function main() {
  const args = parseArgs();
  if (args.help || args.files.length === 0) {
    console.log(usage());
    return 0;
  }

  for (const file of args.files) {
    const { fullPath, data } = await loadJson(file);
    const inferred = inferType(data);
    const type = args.type === 'auto' ? inferred : args.type;

    if (type === 'feather-fall') {
      verifyFeatherFall(fullPath, data, args);
      continue;
    }
    if (type === 'multiplayer-load') {
      verifyMultiplayerLoad(fullPath, data, args);
      continue;
    }
    fail(`${fullPath}: could not infer evidence type; pass --type feather-fall or --type multiplayer-load`);
  }

  console.log(`Verified ${args.files.length} Stage 7 evidence file(s).`);
  return 0;
}

main().then(
  code => process.exitCode = code,
  error => {
    console.error(error.stack || error.message || String(error));
    process.exitCode = 1;
  },
);
