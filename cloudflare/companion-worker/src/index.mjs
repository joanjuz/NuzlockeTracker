/** Soul Link companion snapshots. Only HTTPS bearer-token requests; no public reads. */
const GEN6_GAMES = new Set(['Pokémon X 1.0', 'Pokémon Y 1.0', 'Omega Ruby 1.0', 'Alpha Sapphire 1.0']);
const GAMES = new Set([...GEN6_GAMES, 'Ultra Sun 1.0', 'Ultra Moon 1.0']);
const MAX_SNAPSHOT = 700000;
const safeHeaders = {
  'Content-Type': 'application/json; charset=utf-8',
  'Cache-Control': 'no-store',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
};
const reply = (status, obj) => new Response(JSON.stringify(obj), { status, headers: safeHeaders });
const random = (bytes=24) => {
  const buf = new Uint8Array(bytes);
  crypto.getRandomValues(buf);
  return Array.from(buf, b => b.toString(16).padStart(2, '0')).join('');
};
const digest = async token => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token)))).map(x => x.toString(16).padStart(2, '0')).join('');
// Same rule as the Python client: at least one visible character.
const nameOK = name => typeof name === 'string' && name.trim().length >= 1 && name.length <= 32 && !/[<>\x00-\x1f]/.test(name);
const textOK = (s, n=100) => typeof s === 'string' && s.length <= n && !/[<>\x00-\x1f]/.test(s);

async function input(req, max=2048) {
  if ((req.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() !== 'application/json')
    throw new Error('Se requiere application/json');
  const length = Number(req.headers.get('Content-Length') || 0);
  if (length > max) throw new Error('Solicitud demasiado grande');
  const raw = await req.text();
  if (new TextEncoder().encode(raw).length > max) throw new Error('Solicitud demasiado grande');
  const obj = JSON.parse(raw);
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) throw new Error('JSON inválido');
  return obj;
}
// Same shapes and ranges as companion/snapshot.py (tracker/pokemon.py output).
// Older clients (v0.24/v0.25) only send these keys, so the allowlist is compatible.
const isObj = v => Boolean(v) && typeof v === 'object' && !Array.isArray(v);
const intOK = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;
const intList = (lo, hi, max, exact) => v => Array.isArray(v) && v.length <= max &&
  (exact === undefined || v.length === exact) && v.every(x => intOK(x, lo, hi));
const textList = (n, max) => v => Array.isArray(v) && v.length <= max && v.every(x => textOK(x, n));
const nullable = check => v => v === null || check(v);
const statDict = hi => nullable(v => isObj(v) && Object.keys(v).length <= 8 &&
  Object.entries(v).every(([k, x]) => /^[A-Za-z_]{1,8}$/.test(k) && intOK(x, 0, hi)));
const EVO_INTS = { target: [1, 1025], target_form: [-1, 255], form: [-1, 255], sprite_id: [1, 65535], level: [0, 100] };
const EVO_TEXT = new Set(['target_name', 'method', 'raw_method', 'source', 'item']);
const evolutionOK = e => isObj(e) && Object.keys(e).length <= 24 && Object.entries(e).every(([k, v]) =>
  v === null || (k in EVO_INTS ? intOK(v, ...EVO_INTS[k]) : EVO_TEXT.has(k) ? textOK(v, 200) :
    // Unknown evolution keys are tolerated only as inert scalars.
    typeof v === 'boolean' || Number.isFinite(v) || textOK(v, 200)));
const FIELD_CHECKS = {
  species: v => textOK(v, 100), nickname: v => textOK(v, 40), ability: v => textOK(v, 100),
  item: v => textOK(v, 100), nature: v => textOK(v, 100), met_location: v => textOK(v, 180),
  egg_location: v => textOK(v, 180), type_source: v => textOK(v, 60),
  move_names: textList(100, 4), types: textList(30, 3),
  slot: v => intOK(v, 0, 255), level: nullable(v => intOK(v, 1, 100)),
  hp: nullable(v => intOK(v, 0, 999)), max_hp: nullable(v => intOK(v, 0, 999)),
  met_level: v => intOK(v, 0, 127), form: v => intOK(v, 0, 255), origin_version: v => intOK(v, 0, 255),
  encryption_constant: v => intOK(v, 0, 0xFFFFFFFF), ability_id: v => intOK(v, 0, 65535),
  item_id: v => intOK(v, 0, 65535), met_location_id: v => intOK(v, 0, 65535), egg_location_id: v => intOK(v, 0, 65535),
  moves: intList(0, 65535, 4), move_pp: intList(0, 255, 4), move_pp_ups: intList(0, 255, 4),
  iv: intList(0, 31, 6, 6), ev: intList(0, 255, 6, 6),
  stats: statDict(999), base_stats: statDict(255),
  met_date: nullable(v => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)),
  egg: v => typeof v === 'boolean',
  evolutions: v => Array.isArray(v) && v.length <= 64 && v.every(evolutionOK),
};
function pokemonOK(p, maxSpecies=1025) {
  if (p === null) return true;
  if (!isObj(p)) return false;
  if (!intOK(p.species_id, 1, maxSpecies)) return false;
  for (const [k, v] of Object.entries(p))
    if (k !== 'species_id' && !(Object.hasOwn(FIELD_CHECKS, k) && FIELD_CHECKS[k](v))) return false;
  return true;
}
const ROUTE_KEY = /^[0-9]{1,3}:[0-9]{1,10}$/;
const ORIGINS = new Set(['route', 'fossil', 'gift', 'egg', 'trade']);
function progressOK(progress, validPokemon) {
  if (!isObj(progress) || !isObj(progress.deaths)) return false;
  if (!Array.isArray(progress.missed_routes) || progress.missed_routes.length > 200 ||
      !progress.missed_routes.every(r => textOK(r, 20))) return false;
  const deaths = Object.entries(progress.deaths);
  if (deaths.length > 500 || !deaths.every(([k, d]) => textOK(k, 70) && isObj(d) && validPokemon(d.pokemon) &&
      (!('recorded_at' in d) || textOK(d.recorded_at, 40)) &&
      (!('source' in d) || d.source === 'soullink-response'))) return false;
  if ('death_count' in progress && !intOK(progress.death_count, 0, 100000)) return false;
  if ('origins' in progress) {
    const o = progress.origins;
    if (!isObj(o) || Object.keys(o).length > 1200 ||
        !Object.entries(o).every(([k, v]) => ROUTE_KEY.test(k) && ORIGINS.has(v))) return false;
  }
  if ('route_marks' in progress) {
    const m = progress.route_marks;
    if (!isObj(m) || Object.keys(m).length > 1200 || !Object.entries(m).every(([k, v]) =>
        ROUTE_KEY.test(k) && isObj(v) && (v.kind === 'trade' || v.kind === 'fossil') &&
        v.pokemon !== null && validPokemon(v.pokemon))) return false;
  }
  if ('traded_routes' in progress) {
    const t = progress.traded_routes;
    if (!Array.isArray(t) || t.length > 200 || !t.every(r => typeof r === 'string' && /^\d{1,10}$/.test(r))) return false;
  }
  return true;
}
function snapshotOK(s, game) {
  if (!s || typeof s !== 'object' || Array.isArray(s) || s.schema_version !== 1 || s.game !== game || !GAMES.has(game))
    return false;
  const maxBoxes = GEN6_GAMES.has(game) ? 31 : 32;
  const maxSpecies = GEN6_GAMES.has(game) ? 721 : 807;
  const validPokemon = p => pokemonOK(p, maxSpecies);
  if (!Array.isArray(s.party) || s.party.length !== 6 || !s.party.every(validPokemon)) return false;
  if (!s.boxes || typeof s.boxes !== 'object' || Array.isArray(s.boxes)) return false;
  const keys = Object.keys(s.boxes);
  if (keys.length > maxBoxes || !keys.every(k => /^(?:[1-9]|[12]\d|3[012])$/.test(k) && Number(k) <= maxBoxes && Array.isArray(s.boxes[k]) && s.boxes[k].length === 30 && s.boxes[k].every(validPokemon))) return false;
  if (!progressOK(s.progress, validPokemon)) return false;
  return typeof s.battle_hp === 'boolean';
}
// Constant-time comparison: hash both values so length and content never
// leak through early exits, then compare the fixed-size digests bitwise.
async function sameSecret(supplied, expected) {
  if (typeof supplied !== 'string' || typeof expected !== 'string') return false;
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([crypto.subtle.digest('SHA-256', enc.encode(supplied)),
                                    crypto.subtle.digest('SHA-256', enc.encode(expected))]);
  const x = new Uint8Array(a), y = new Uint8Array(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}
const STALE_PAIR_MS = 7 * 86400000;
// Deterministic order + LIMIT keeps each cleanup bounded and identical for both DELETEs.
const STALE_PAIRS = `SELECT p.id FROM pairs p WHERE p.invite_expires < ? AND p.created_at < ?
  AND NOT EXISTS (SELECT 1 FROM members m WHERE m.pair_id = p.id AND m.slot = 2)
  ORDER BY p.created_at, p.id LIMIT 50`;
async function memberOf(req, db) {
  const bearer = req.headers.get('Authorization') || '';
  if (!/^Bearer [a-f0-9]{48}$/.test(bearer)) return null;
  return db.prepare('SELECT id, pair_id, slot, name, game FROM members WHERE token_hash = ?')
    .bind(await digest(bearer.slice(7))).first();
}

export default {
  async fetch(req, env) {
    const path = new URL(req.url).pathname;
    if (req.method === 'GET' && path === '/health') return reply(200, { ok: true, service: 'companion-v1' });
    if (!env.DB || !env.CREATE_KEY || env.CREATE_KEY.length < 16)
      return reply(503, { error: 'Configura D1 y el secreto CREATE_KEY primero' });
    if (req.method === 'OPTIONS') return reply(405, { error: 'No se permite acceso directo entre sitios' });
    try {
      if (req.method === 'POST' && path === '/v1/pairs') {
        if (!(await sameSecret(req.headers.get('X-Setup-Key'), env.CREATE_KEY))) return reply(403, { error: 'Clave de creación incorrecta' });
        const data = await input(req);
        if (!nameOK(data.name) || !GAMES.has(data.game)) return reply(400, { error: 'Jugador o juego incorrecto' });
        const pairId = crypto.randomUUID(), memberId = crypto.randomUUID();
        const token = random(), inviteCode = random(16), now = Date.now();
        await env.DB.batch([
          // Opportunistic, bounded cleanup: pairs nobody joined whose invitation
          // expired and that were created more than a week ago. Members are
          // removed explicitly so it does not depend on FK cascade settings.
          env.DB.prepare(`DELETE FROM members WHERE pair_id IN (${STALE_PAIRS})`).bind(now, now - STALE_PAIR_MS),
          env.DB.prepare(`DELETE FROM pairs WHERE id IN (${STALE_PAIRS})`).bind(now, now - STALE_PAIR_MS),
          env.DB.prepare('INSERT INTO pairs (id,invite_hash,invite_expires,created_at) VALUES (?,?,?,?)').bind(pairId, await digest(inviteCode), now + 86400000, now),
          env.DB.prepare('INSERT INTO members (id,pair_id,slot,token_hash,name,game) VALUES (?,?,?,?,?,?)').bind(memberId, pairId, 1, await digest(token), data.name, data.game),
        ]);
        return reply(201, { pair_id: pairId, token, invite_code: inviteCode });
      }
      if (req.method === 'POST' && path === '/v1/pairs/join') {
        const data = await input(req);
        if (!nameOK(data.name) || !GAMES.has(data.game) || !/^[a-f0-9]{32}$/.test(data.invite_code || ''))
          return reply(400, { error: 'Invitación, nombre o juego inválido' });
        const pair = await env.DB.prepare('SELECT id,invite_expires FROM pairs WHERE invite_hash = ?').bind(await digest(data.invite_code)).first();
        if (!pair || pair.invite_expires < Date.now()) return reply(404, { error: 'Invitación incorrecta o vencida (24 h)' });
        const first = await env.DB.prepare('SELECT id FROM members WHERE pair_id = ? AND slot = 1').bind(pair.id).first();
        if (!first) return reply(409, { error: 'La pareja no está disponible' });
        const token = random(), id = crypto.randomUUID();
        try {
          await env.DB.prepare('INSERT INTO members (id,pair_id,slot,token_hash,name,game) VALUES (?,?,?,?,?,?)')
            .bind(id, pair.id, 2, await digest(token), data.name, data.game).run();
        } catch (_) { return reply(409, { error: 'Este código ya fue utilizado' }); }
        return reply(201, { pair_id: pair.id, token });
      }
      if (path === '/v1/state' && req.method === 'PUT') {
        const member = await memberOf(req, env.DB);
        if (!member) return reply(401, { error: 'Credenciales inválidas' });
        const data = await input(req, MAX_SNAPSHOT + 80000);
        if (!snapshotOK(data.state, member.game)) return reply(400, { error: 'Estado de Pokémon incompatible' });
        const raw = JSON.stringify(data.state);
        if (new TextEncoder().encode(raw).length > MAX_SNAPSHOT) return reply(413, { error: 'Sesión demasiado grande' });
        const now = Date.now();
        await env.DB.prepare('UPDATE members SET snapshot = ?, updated_at = ? WHERE id = ?')
          .bind(raw, now, member.id).run();
        return reply(200, { ok: true, updated_at: now });
      }
      if (path === '/v1/partner' && req.method === 'GET') {
        const member = await memberOf(req, env.DB);
        if (!member) return reply(401, { error: 'Credenciales inválidas' });
        const partner = await env.DB.prepare('SELECT name,game,snapshot,updated_at FROM members WHERE pair_id = ? AND id != ?')
          .bind(member.pair_id, member.id).first();
        return reply(200, { partner_joined: Boolean(partner), partner: partner ?
          { name: partner.name, game: partner.game, state: partner.snapshot ? JSON.parse(partner.snapshot) : null,
            updated_at: partner.updated_at } : null });
      }
      if (path === '/v1/leave' && req.method === 'POST') {
        await input(req);
        const member = await memberOf(req, env.DB);
        if (!member) return reply(401, { error: 'Credenciales inválidas' });
        // Revokes both accounts and deletes all shared snapshots. No dangling access.
        await env.DB.batch([
          env.DB.prepare('DELETE FROM members WHERE pair_id = ?').bind(member.pair_id),
          env.DB.prepare('DELETE FROM pairs WHERE id = ?').bind(member.pair_id),
        ]);
        return reply(200, { ok: true });
      }
      return reply(404, { error: 'Ruta no encontrada' });
    } catch (err) {
      if (err instanceof SyntaxError) return reply(400, { error: 'JSON inválido' });
      if (err instanceof Error && /Solicitud demasiado grande/.test(err.message)) return reply(413, { error: 'Solicitud demasiado grande' });
      if (err instanceof Error && /Se requiere application\/json|JSON inválido/.test(err.message)) return reply(400, { error: err.message });
      return reply(500, { error: 'Error interno del servicio' });
    }
  }
};
