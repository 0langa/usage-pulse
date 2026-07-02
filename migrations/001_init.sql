CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  host_session_id TEXT,
  provider TEXT NOT NULL,
  model_id TEXT,
  cwd TEXT,
  git_branch TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  prompt_count INTEGER NOT NULL DEFAULT 0,
  input_tokens_est INTEGER NOT NULL DEFAULT 0,
  tool_call_count INTEGER NOT NULL DEFAULT 0,
  tool_success_count INTEGER NOT NULL DEFAULT 0,
  tool_failure_count INTEGER NOT NULL DEFAULT 0,
  tool_duration_ms INTEGER NOT NULL DEFAULT 0,
  tool_output_bytes INTEGER NOT NULL DEFAULT 0,
  web_search_count INTEGER NOT NULL DEFAULT 0,
  file_read_count INTEGER NOT NULL DEFAULT 0,
  file_edit_count INTEGER NOT NULL DEFAULT 0,
  file_write_count INTEGER NOT NULL DEFAULT 0,
  unique_paths_json TEXT NOT NULL DEFAULT '[]',
  mcp_call_count INTEGER NOT NULL DEFAULT 0,
  subagent_count INTEGER NOT NULL DEFAULT 0,
  compaction_count INTEGER NOT NULL DEFAULT 0,
  hook_fire_count INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  timestamp TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  char_count INTEGER NOT NULL,
  token_estimate INTEGER NOT NULL,
  privacy_sensitive INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  timestamp TEXT NOT NULL,
  completed_at TEXT,
  provider TEXT NOT NULL,
  name TEXT NOT NULL,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  success INTEGER,
  input_bytes INTEGER NOT NULL DEFAULT 0,
  output_bytes INTEGER NOT NULL DEFAULT 0,
  error TEXT
);

CREATE TABLE IF NOT EXISTS hook_fires (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  timestamp TEXT NOT NULL,
  provider TEXT NOT NULL,
  event TEXT NOT NULL,
  payload_bytes INTEGER NOT NULL DEFAULT 0,
  success INTEGER NOT NULL DEFAULT 1,
  error TEXT
);

CREATE TABLE IF NOT EXISTS file_ops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  timestamp TEXT NOT NULL,
  operation TEXT NOT NULL,
  path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mcp_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  timestamp TEXT NOT NULL,
  provider TEXT NOT NULL,
  server TEXT NOT NULL,
  tool TEXT NOT NULL,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  success INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS compactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  timestamp TEXT NOT NULL,
  trigger TEXT,
  token_count INTEGER
);

CREATE TABLE IF NOT EXISTS web_searches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  timestamp TEXT NOT NULL,
  query_hash TEXT NOT NULL,
  result_count INTEGER
);

CREATE TABLE IF NOT EXISTS subagents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  timestamp TEXT NOT NULL,
  name TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prompts_session_timestamp ON prompts(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session_timestamp ON tool_calls(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_hook_fires_session_timestamp ON hook_fires(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_file_ops_session_timestamp ON file_ops(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_mcp_calls_session_timestamp ON mcp_calls(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_compactions_session_timestamp ON compactions(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sessions_provider_timestamp ON sessions(provider, started_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_provider_timestamp ON tool_calls(provider, timestamp);
CREATE INDEX IF NOT EXISTS idx_mcp_calls_provider_timestamp ON mcp_calls(provider, timestamp);
