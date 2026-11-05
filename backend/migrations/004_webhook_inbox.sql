CREATE TABLE webhook_inbox (
    id TEXT PRIMARY KEY,
    phone TEXT NOT NULL,
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','done','failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    error TEXT
);
CREATE INDEX inbox_pending ON webhook_inbox(state,next_attempt_at);
