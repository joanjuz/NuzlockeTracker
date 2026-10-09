CREATE TABLE IF NOT EXISTS pairs (
  id TEXT PRIMARY KEY,
  invite_hash TEXT NOT NULL UNIQUE,
  invite_expires INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
  id TEXT PRIMARY KEY,
  pair_id TEXT NOT NULL REFERENCES pairs(id) ON DELETE CASCADE,
  slot INTEGER NOT NULL CHECK(slot IN (1, 2)),
  token_hash TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  game TEXT NOT NULL,
  snapshot TEXT,
  updated_at INTEGER NOT NULL DEFAULT 0,
  UNIQUE(pair_id, slot)
);
CREATE INDEX IF NOT EXISTS members_pair_idx ON members(pair_id, slot);
