/** Soul Link companion snapshots. Only HTTPS bearer-token requests; no public reads. */
const GAMES = new Set(['Ultra Sun 1.0', 'Ultra Moon 1.0']);
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
const nameOK = name => typeof name === 'string' && name.length >= 1 && name.length <= 32 && !/[<>\x00-\x1f]/.test(name);
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
function pokemonOK(p) {
  if (p === null) return true;
  if (!p || typeof p !== 'object' || Array.isArray(p)) return false;
  if (!Number.isInteger(p.species_id) || p.species_id < 1 || p.species_id > 1025) return false;
  for(const k of ['species', 'nickname', 'ability', 'item', 'nature', 'met_location'])
    if (k in p && !textOK(p[k], 180)) return false;
  if ('level' in p && p.level !== null && (!Number.isInteger(p.level) || p.level < 1 || p.level > 100)) return false;
  return true;
}
function snapshotOK(s, game) {
  if (!s || typeof s !== 'object' || Array.isArray(s) || s.schema_version !== 1 || s.game !== game)
    return false;
  if (!Array.isArray(s.party) || s.party.length !== 6 || !s.party.every(pokemonOK)) return false;
  if (!s.boxes || typeof s.boxes !== 'object' || Array.isArray(s.boxes)) return false;
  const keys = Object.keys(s.boxes);
  if (keys.length > 32 || !keys.every(k => /^(?:[1-9]|[12]\d|3[012])$/.test(k) && Array.isArray(s.boxes[k]) && s.boxes[k].length === 30 && s.boxes[k].every(pokemonOK))) return false;
  if (!s.progress || typeof s.progress !== 'object' || !s.progress.deaths || typeof s.progress.deaths !== 'object' || Array.isArray(s.progress.deaths)) return false;
  if (!Array.isArray(s.progress.missed_routes) || s.progress.missed_routes.length > 200) return false;
  const deaths = Object.values(s.progress.deaths);
  if (deaths.length > 500 || !deaths.every(d => d && typeof d === 'object' && pokemonOK(d.pokemon))) return false;
  return typeof s.battle_hp === 'boolean';
}
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
        if (req.headers.get('X-Setup-Key') !== env.CREATE_KEY) return reply(403, { error: 'Clave de creación incorrecta' });
        const data = await input(req);
        if (!nameOK(data.name) || !GAMES.has(data.game)) return reply(400, { error: 'Jugador o juego incorrecto' });
        const pairId = crypto.randomUUID(), memberId = crypto.randomUUID();
        const token = random(), inviteCode = random(16), now = Date.now();
        await env.DB.batch([
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
        const first = await env.DB.prepare('SELECT game FROM members WHERE pair_id = ? AND slot = 1').bind(pair.id).first();
        if (!first || first.game === data.game) return reply(409, { error: 'La pareja debe usar el otro juego (Ultra Sol ↔ Ultra Luna)' });
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
        await env.DB.prepare('DELETE FROM members WHERE pair_id = ?').bind(member.pair_id).run();
        await env.DB.prepare('DELETE FROM pairs WHERE id = ?').bind(member.pair_id).run();
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
