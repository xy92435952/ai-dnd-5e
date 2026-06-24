#!/usr/bin/env node
import { existsSync, readFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, '..');
const VALID_EVIDENCE_TYPES = ['auto', 'feather-fall', 'multiplayer-load', 'postdeploy-healthcheck', 'local-http-smoke', 'public-browser-smoke'];

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

function validateEvidenceType(type) {
  if (!VALID_EVIDENCE_TYPES.includes(type)) {
    throw new Error(`--type must be one of: ${VALID_EVIDENCE_TYPES.join(', ')}.`);
  }
  return type;
}

function parseArgs(argv = process.argv.slice(2)) {
  const result = {
    files: [],
    type: 'auto',
    noFileCheck: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--type') {
      result.type = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--type=')) {
      result.type = requiredInlineOptionValue(arg.slice('--type='.length), '--type');
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
    if (arg.startsWith('--')) {
      throw new Error(`Unknown option: ${arg}`);
    }
    result.files.push(arg);
  }

  result.type = validateEvidenceType(result.type);
  return result;
}

function usage() {
  return [
    'Usage:',
    '  node scripts/verify_stage7_evidence.mjs [--type feather-fall|multiplayer-load|postdeploy-healthcheck|local-http-smoke|public-browser-smoke|auto] [--no-file-check] <json-file> [more-json-files...]',
    '',
    'Checks:',
    '  feather-fall       verifies browser smoke manifest fields and screenshot paths',
    '  multiplayer-load   verifies load smoke result fields and summary counts',
    '  postdeploy-healthcheck verifies post-deploy health URL and log scan results',
    '  local-http-smoke   verifies local HTTP health, login, Adventure, Combat, and skill-bar smoke results',
    '  public-browser-smoke verifies public-origin login, Adventure, Combat, and skill-bar browser smoke results',
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
  if (Array.isArray(data?.healthChecks) && Array.isArray(data?.logChecks) && Object.prototype.hasOwnProperty.call(data, 'healthReady')) {
    return 'postdeploy-healthcheck';
  }
  if (data?.mode === 'stage7-local-http-smoke') return 'local-http-smoke';
  if (data?.mode === 'stage7-public-browser-smoke') return 'public-browser-smoke';
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

function ensureNonNegativeNumber(value, message) {
  ensureNumber(value, message);
  ensure(value >= 0, message);
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
  ensure(typeof data.prompt?.dialogName === 'string' && data.prompt.dialogName.includes('Feather Fall'), `${filePath}: prompt.dialogName must include Feather Fall`);
  ensure(typeof data.prompt?.dialogDescription === 'string' && data.prompt.dialogDescription.includes(`Prevents ${data.assertions.fall_damage} fall damage`), `${filePath}: prompt.dialogDescription must include prevented fall damage`);
  ensure(data.prompt.dialogDescription.includes('Costs'), `${filePath}: prompt.dialogDescription must include reaction cost`);
  ensure(data.prompt.dialogDescription.includes(`Cast prevents ${data.assertions.fall_damage} fall damage`), `${filePath}: prompt.dialogDescription must include cast outcome`);
  ensure(data.prompt.dialogDescription.includes('Decline lets'), `${filePath}: prompt.dialogDescription must include decline outcome`);
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
  ensure(data.room_sizes.every(size => Number.isInteger(size) && size > 0), `${filePath}: room_sizes must contain positive integers`);
  ensure(data.room_sizes.every(size => size <= 4), `${filePath}: room_sizes must not exceed max_players=4`);
  const totalRoomUsers = data.room_sizes.reduce((sum, size) => sum + size, 0);
  ensure(totalRoomUsers === data.users, `${filePath}: room_sizes must sum to users`);
  ensure(data.websockets === data.users, `${filePath}: websockets must match users`);
  ensure(data.rooms === data.room_sizes.length, `${filePath}: rooms must match room_sizes length`);
  ensure(data.cleanup_ok === true, `${filePath}: cleanup_ok must be true`);
  ensure(data.cleanup_verification_ok === true, `${filePath}: cleanup_verification_ok must be true`);
  ensure(data.module_cleanup_ok === true, `${filePath}: module_cleanup_ok must be true`);
  ensure(data.seed_module_cleanup_ok === true, `${filePath}: seed_module_cleanup_ok must be true`);
  ensureNonNegativeNumber(data.elapsed_ms, `${filePath}: elapsed_ms missing`);
  ensure(data.timings && typeof data.timings === 'object', `${filePath}: timings missing`);

  const summaryKeys = ['register_ms', 'login_ms', 'create_room_ms', 'join_room_ms', 'ws_connect_ms', 'ws_ping_pong_ms'];
  const hasSummary = summaryKeys.some(key => Object.prototype.hasOwnProperty.call(data.timings, key));
  ensure(hasSummary, `${filePath}: timings summary missing expected keys`);
  for (const key of summaryKeys) {
    if (!Object.prototype.hasOwnProperty.call(data.timings, key)) continue;
    const summary = data.timings[key];
    ensure(summary && typeof summary === 'object', `${filePath}: timings.${key} must be an object`);
    ensure(Number.isInteger(summary.count) && summary.count > 0, `${filePath}: timings.${key}.count must be positive`);
    ensureNonNegativeNumber(summary.avg_ms, `${filePath}: timings.${key}.avg_ms missing`);
    ensureNonNegativeNumber(summary.p95_ms, `${filePath}: timings.${key}.p95_ms missing`);
    ensureNonNegativeNumber(summary.max_ms, `${filePath}: timings.${key}.max_ms missing`);
  }

  if (data.hold_observer) {
    ensure(typeof data.hold_observer.base_url === 'string', `${filePath}: hold_observer.base_url missing`);
    ensure(typeof data.hold_observer.frontend_url === 'string', `${filePath}: hold_observer.frontend_url missing`);
    ensure(typeof data.hold_observer.session_id === 'string', `${filePath}: hold_observer.session_id missing`);
    ensure(typeof data.hold_observer.username === 'string', `${filePath}: hold_observer.username missing`);
    ensure(typeof data.hold_observer.password === 'string', `${filePath}: hold_observer.password missing`);
    ensure(typeof data.hold_observer.room_code === 'string', `${filePath}: hold_observer.room_code missing`);
  }

  if (!noFileCheck) {
    if (data.result_json) {
      ensurePathExists(data.result_json, `${filePath}: result JSON`);
    }
  }
}

function verifyPostdeployHealthcheck(filePath, data) {
  ensure(data.ready === true, `${filePath}: ready must be true`);
  ensure(data.healthReady === true, `${filePath}: healthReady must be true`);
  ensure(data.logsReady === true, `${filePath}: logsReady must be true`);
  ensure(typeof data.generatedAt === 'string' && data.generatedAt.length > 0, `${filePath}: generatedAt missing`);
  ensure(Array.isArray(data.healthChecks) && data.healthChecks.length > 0, `${filePath}: healthChecks must include at least one URL`);
  ensure(Array.isArray(data.logChecks), `${filePath}: logChecks must be an array`);

  data.healthChecks.forEach((check, index) => {
    const label = `${filePath}: healthChecks[${index}]`;
    ensure(check && typeof check === 'object', `${label} must be an object`);
    ensure(typeof check.url === 'string' && check.url.length > 0, `${label}.url missing`);
    ensure(check.ok === true, `${label}.ok must be true`);
    ensure(check.statusOk === true, `${label}.statusOk must be true`);
    ensureNumber(check.status, `${label}.status missing`);
    ensure(check.status >= 200 && check.status < 300, `${label}.status must be HTTP 2xx`);
    ensure(check.body && check.body.status === 'ok', `${label}.body.status must be ok`);
    ensure(!check.error, `${label}.error must be empty`);
  });

  data.logChecks.forEach((check, index) => {
    const label = `${filePath}: logChecks[${index}]`;
    ensure(check && typeof check === 'object', `${label} must be an object`);
    ensure(typeof check.file === 'string' && check.file.length > 0, `${label}.file missing`);
    ensure(check.ok === true, `${label}.ok must be true`);
    ensure(Array.isArray(check.matches), `${label}.matches must be an array`);
    ensure(check.matches.length === 0, `${label}.matches must be empty`);
    ensure(!check.error, `${label}.error must be empty`);
  });
}

function ensureNoLogStopMarkers(filePath, logPath, label) {
  const fullLogPath = path.isAbsolute(logPath) ? logPath : path.resolve(root, logPath);
  ensurePathExists(fullLogPath, `${filePath}: ${label}`);
  const lines = readFileSync(fullLogPath, 'utf8').split(/\r?\n/);
  const matches = lines.filter(line => (
    /traceback/i.test(line)
    || /\berror\b/i.test(line)
    || /\b500\b/.test(line)
  ));
  ensure(matches.length === 0, `${filePath}: ${label} contains stop markers: ${matches.slice(0, 3).join(' | ')}`);
}

function verifyLocalHttpSmoke(filePath, data, { noFileCheck }) {
  ensure(data.ok === true, `${filePath}: ok must be true`);
  ensure(data.mode === 'stage7-local-http-smoke', `${filePath}: unexpected mode ${data.mode}`);
  ensure(typeof data.created_at === 'string' && data.created_at.length > 0, `${filePath}: created_at missing`);
  ensure(typeof data.base_url === 'string' && data.base_url.length > 0, `${filePath}: base_url missing`);
  ensure(data.health && data.health.status === 'ok', `${filePath}: health.status must be ok`);

  ensure(data.seed && typeof data.seed === 'object', `${filePath}: seed missing`);
  ensure(typeof data.seed.username === 'string' && data.seed.username.length > 0, `${filePath}: seed.username missing`);
  ensure(typeof data.seed.module_id === 'string' && data.seed.module_id.length > 0, `${filePath}: seed.module_id missing`);
  ensure(typeof data.seed.character_id === 'string' && data.seed.character_id.length > 0, `${filePath}: seed.character_id missing`);
  ensure(typeof data.seed.session_id === 'string' && data.seed.session_id.length > 0, `${filePath}: seed.session_id missing`);
  ensure(typeof data.seed.combat_state_id === 'string' && data.seed.combat_state_id.length > 0, `${filePath}: seed.combat_state_id missing`);

  const checks = data.checks || {};
  ensure(checks.login_token_present === true, `${filePath}: checks.login_token_present must be true`);
  ensure(checks.session_combat_active === true, `${filePath}: checks.session_combat_active must be true`);
  ensure(checks.current_scene_present === true, `${filePath}: checks.current_scene_present must be true`);
  ensure(checks.session_id === data.seed.session_id, `${filePath}: checks.session_id must match seed.session_id`);
  ensure(checks.combat_session_id === data.seed.session_id, `${filePath}: checks.combat_session_id must match seed.session_id`);
  ensure(checks.skill_bar_entity_id === data.seed.character_id, `${filePath}: checks.skill_bar_entity_id must match seed.character_id`);
  ensureNumber(checks.combat_round, `${filePath}: checks.combat_round missing`);
  ensure(checks.combat_round >= 1, `${filePath}: checks.combat_round must be at least 1`);
  ensureNumber(checks.combat_turn_order_count, `${filePath}: checks.combat_turn_order_count missing`);
  ensure(checks.combat_turn_order_count >= 2, `${filePath}: checks.combat_turn_order_count must include player and enemies`);
  ensureNumber(checks.combat_entities_count, `${filePath}: checks.combat_entities_count missing`);
  ensure(checks.combat_entities_count >= 2, `${filePath}: checks.combat_entities_count must include player and enemies`);
  ensureNumber(checks.skill_bar_count, `${filePath}: checks.skill_bar_count missing`);
  ensure(checks.skill_bar_count > 0, `${filePath}: checks.skill_bar_count must be positive`);

  const assertions = data.assertions || {};
  for (const key of ['health_ok', 'login_ok', 'adventure_session_loaded', 'combat_loaded', 'skill_bar_loaded']) {
    ensure(assertions[key] === true, `${filePath}: assertions.${key} must be true`);
  }

  if (!noFileCheck) {
    ensure(typeof data.logs?.stdout === 'string' && data.logs.stdout.length > 0, `${filePath}: logs.stdout missing`);
    ensure(typeof data.logs?.stderr === 'string' && data.logs.stderr.length > 0, `${filePath}: logs.stderr missing`);
    ensureNoLogStopMarkers(filePath, data.logs.stdout, 'stdout log');
    ensureNoLogStopMarkers(filePath, data.logs.stderr, 'stderr log');
  }
}

function verifyPublicBrowserSmoke(filePath, data, { noFileCheck }) {
  ensure(data.ok === true, `${filePath}: ok must be true`);
  ensure(data.mode === 'stage7-public-browser-smoke', `${filePath}: unexpected mode ${data.mode}`);
  ensure(typeof data.created_at === 'string' && data.created_at.length > 0, `${filePath}: created_at missing`);
  ensure(typeof data.frontend_origin === 'string' && /^https?:\/\//.test(data.frontend_origin), `${filePath}: frontend_origin must be an http(s) origin`);
  ensure(typeof data.session_id === 'string' && data.session_id.length > 0, `${filePath}: session_id missing`);
  ensure(typeof data.username === 'string' && data.username.length > 0, `${filePath}: username missing`);

  const checks = data.checks || {};
  ensure(checks.login_token_present === true, `${filePath}: checks.login_token_present must be true`);
  ensure(checks.login_path && checks.login_path !== '/login', `${filePath}: checks.login_path must leave /login`);
  const adventureRouteReady = checks.adventure_loaded === true
    || checks.adventure_redirected_to_combat === true
    || checks.adventure_route_ready === true;
  ensure(
    adventureRouteReady,
    `${filePath}: checks.adventure_loaded or checks.adventure_redirected_to_combat must be true`,
  );
  ensure(checks.session_api_ok === true, `${filePath}: checks.session_api_ok must be true`);
  ensure(checks.session_id_matches === true, `${filePath}: checks.session_id_matches must be true`);
  ensure(checks.session_combat_active === true, `${filePath}: checks.session_combat_active must be true`);
  ensure(checks.current_scene_present === true, `${filePath}: checks.current_scene_present must be true`);
  ensure(checks.combat_loaded === true, `${filePath}: checks.combat_loaded must be true`);
  ensure(checks.combat_api_ok === true, `${filePath}: checks.combat_api_ok must be true`);
  ensureNumber(checks.combat_round, `${filePath}: checks.combat_round missing`);
  ensure(checks.combat_round >= 1, `${filePath}: checks.combat_round must be at least 1`);
  ensureNumber(checks.combat_turn_order_count, `${filePath}: checks.combat_turn_order_count missing`);
  ensure(checks.combat_turn_order_count >= 2, `${filePath}: checks.combat_turn_order_count must include player and enemies`);
  ensureNumber(checks.combat_entities_count, `${filePath}: checks.combat_entities_count missing`);
  ensure(checks.combat_entities_count >= 2, `${filePath}: checks.combat_entities_count must include player and enemies`);
  ensureNumber(checks.skill_bar_count, `${filePath}: checks.skill_bar_count missing`);
  ensure(checks.skill_bar_count > 0, `${filePath}: checks.skill_bar_count must be positive`);
  ensureNumber(checks.skill_bar_dom_count, `${filePath}: checks.skill_bar_dom_count missing`);
  ensure(checks.skill_bar_dom_count > 0, `${filePath}: checks.skill_bar_dom_count must be positive`);

  const assertions = data.assertions || {};
  for (const key of ['login_ok', 'adventure_loaded', 'combat_loaded', 'combat_session_active', 'skill_bar_loaded', 'no_browser_errors']) {
    ensure(assertions[key] === true, `${filePath}: assertions.${key} must be true`);
  }
  ensure(Array.isArray(data.browser?.errors), `${filePath}: browser.errors must be an array`);
  ensure(data.browser.errors.length === 0, `${filePath}: browser.errors must be empty`);

  if (!noFileCheck) {
    ensure(typeof data.screenshots?.adventure === 'string' && data.screenshots.adventure.length > 0, `${filePath}: screenshots.adventure missing`);
    ensure(typeof data.screenshots?.combat === 'string' && data.screenshots.combat.length > 0, `${filePath}: screenshots.combat missing`);
    ensurePathExists(path.isAbsolute(data.screenshots.adventure) ? data.screenshots.adventure : path.resolve(root, data.screenshots.adventure), `${filePath}: screenshots.adventure`);
    ensurePathExists(path.isAbsolute(data.screenshots.combat) ? data.screenshots.combat : path.resolve(root, data.screenshots.combat), `${filePath}: screenshots.combat`);
  }
}

async function main() {
  const args = parseArgs();
  if (args.help) {
    console.log(usage());
    return 0;
  }
  if (args.files.length === 0) {
    fail('At least one Stage 7 evidence file is required.');
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
    if (type === 'postdeploy-healthcheck') {
      verifyPostdeployHealthcheck(fullPath, data, args);
      continue;
    }
    if (type === 'local-http-smoke') {
      verifyLocalHttpSmoke(fullPath, data, args);
      continue;
    }
    if (type === 'public-browser-smoke') {
      verifyPublicBrowserSmoke(fullPath, data, args);
      continue;
    }
    fail(`${fullPath}: could not infer evidence type; pass --type feather-fall, --type multiplayer-load, --type postdeploy-healthcheck, --type local-http-smoke, or --type public-browser-smoke`);
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
