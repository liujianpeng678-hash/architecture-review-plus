CREATE TABLE IF NOT EXISTS invites (
  code_hash TEXT PRIMARY KEY,
  label TEXT NOT NULL DEFAULT '',
  max_uses INTEGER NOT NULL DEFAULT 1,
  used_count INTEGER NOT NULL DEFAULT 0,
  expires_at INTEGER,
  revoked INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  subject TEXT NOT NULL,
  device_id TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audits (
  id TEXT PRIMARY KEY,
  subject TEXT NOT NULL,
  project_hash TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS repair_jobs (
  id TEXT PRIMARY KEY,
  subject TEXT NOT NULL,
  audit_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  status TEXT NOT NULL,
  tasks_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS repair_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  task_id TEXT,
  status TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_subject ON sessions(subject);
CREATE INDEX IF NOT EXISTS idx_audits_subject ON audits(subject);
CREATE INDEX IF NOT EXISTS idx_jobs_subject ON repair_jobs(subject);
CREATE INDEX IF NOT EXISTS idx_events_job ON repair_events(job_id, id);
