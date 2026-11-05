CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS farmers (
    phone TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    farmer_phone TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT,
    media_id TEXT,
    status TEXT NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'processed', 'error', 'ai_error', 'needs_text')),
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_phone) REFERENCES farmers(phone)
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_phone TEXT NOT NULL,
    payload TEXT NOT NULL CHECK (json_valid(payload)),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'pending_review', 'approved', 'rejected', 'completed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_phone) REFERENCES farmers(phone)
);

CREATE TABLE IF NOT EXISTS conversations (
    farmer_phone TEXT PRIMARY KEY,
    payload TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(payload)),
    history TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(history)),
    last_question_field TEXT,
    last_question TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    awaiting_confirmation INTEGER NOT NULL DEFAULT 0 CHECK (awaiting_confirmation IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_phone) REFERENCES farmers(phone)
);

CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_phone TEXT NOT NULL,
    message_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'context')),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (message_id, role),
    FOREIGN KEY (farmer_phone) REFERENCES farmers(phone),
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

CREATE TABLE IF NOT EXISTS machines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    machine_type TEXT NOT NULL CHECK (length(trim(machine_type)) > 0),
    location TEXT,
    hourly_rate REAL CHECK (hourly_rate IS NULL OR hourly_rate >= 0),
    available INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
    owner_type TEXT NOT NULL DEFAULT 'company'
        CHECK (owner_type IN ('company', 'partner')),
    reserved_for_own_use INTEGER NOT NULL DEFAULT 0
        CHECK (reserved_for_own_use IN (0, 1)),
    available_from TEXT,
    available_to TEXT,
    compatibility_notes TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    CHECK (available_from IS NULL OR available_to IS NULL OR available_from <= available_to)
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    machine_id INTEGER NOT NULL,
    start_at TEXT,
    end_at TEXT,
    status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'confirmed', 'cancelled', 'completed')),
    FOREIGN KEY (request_id) REFERENCES requests(id),
    FOREIGN KEY (machine_id) REFERENCES machines(id)
);

CREATE INDEX IF NOT EXISTS messages_farmer_created
    ON messages(farmer_phone, created_at);
CREATE INDEX IF NOT EXISTS requests_status_created
    ON requests(status, created_at);
CREATE INDEX IF NOT EXISTS conversation_turns_phone
    ON conversation_turns(farmer_phone, id);
CREATE INDEX IF NOT EXISTS machines_type_location
    ON machines(machine_type, location);
