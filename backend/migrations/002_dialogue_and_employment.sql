CREATE TABLE IF NOT EXISTS catalog_terms (
    kind TEXT NOT NULL,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(aliases)),
    PRIMARY KEY (kind, code)
);

CREATE TABLE IF NOT EXISTS dialogue_audit (
    message_id TEXT PRIMARY KEY,
    task TEXT,
    route TEXT,
    error_code TEXT,
    duration_ms REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

CREATE TABLE IF NOT EXISTS dialogue_outgoing (
    message_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL CHECK (json_valid(payload)),
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

CREATE TABLE IF NOT EXISTS dialogue_context (
    phone TEXT PRIMARY KEY,
    payload TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(payload)),
    FOREIGN KEY (phone) REFERENCES farmers(phone)
);

CREATE TABLE IF NOT EXISTS dialogue_drafts (
    phone TEXT NOT NULL,
    task TEXT NOT NULL,
    payload TEXT NOT NULL CHECK (json_valid(payload)),
    pending TEXT,
    PRIMARY KEY (phone, task),
    FOREIGN KEY (phone) REFERENCES farmers(phone)
);

CREATE TABLE IF NOT EXISTS dialogue_sessions (
    phone TEXT PRIMARY KEY,
    task TEXT NOT NULL DEFAULT 'none',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_reply TEXT,
    repeats INTEGER NOT NULL DEFAULT 0 CHECK (repeats >= 0),
    FOREIGN KEY (phone) REFERENCES farmers(phone)
);

CREATE TABLE IF NOT EXISTS dialogue_confirmations (
    phone TEXT NOT NULL,
    task TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    armed INTEGER NOT NULL DEFAULT 0 CHECK (armed IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (phone, task),
    FOREIGN KEY (phone) REFERENCES farmers(phone)
);

CREATE TABLE IF NOT EXISTS employment_drafts (
    phone TEXT PRIMARY KEY,
    payload TEXT NOT NULL CHECK (json_valid(payload)),
    pending TEXT NOT NULL,
    awaiting_confirmation INTEGER NOT NULL DEFAULT 0
        CHECK (awaiting_confirmation IN (0, 1)),
    FOREIGN KEY (phone) REFERENCES farmers(phone)
);

CREATE TABLE IF NOT EXISTS employment_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_phone TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('worker', 'job')),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    location TEXT NOT NULL CHECK (length(trim(location)) > 0),
    work TEXT NOT NULL,
    details TEXT NOT NULL,
    contact TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (owner_phone, kind),
    FOREIGN KEY (owner_phone) REFERENCES farmers(phone)
);

CREATE INDEX IF NOT EXISTS employment_search
    ON employment_listings(kind, status, location);
CREATE INDEX IF NOT EXISTS dialogue_audit_route
    ON dialogue_audit(route, created_at);
