ALTER TABLE requests ADD COLUMN tracking_hash TEXT;
ALTER TABLE requests ADD COLUMN review_state TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE requests ADD COLUMN review_note TEXT NOT NULL DEFAULT '';
ALTER TABLE requests ADD COLUMN allocation_state TEXT NOT NULL DEFAULT 'none';
CREATE TABLE request_documents (
 id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES requests(id),
 name TEXT NOT NULL, mime TEXT NOT NULL, content BLOB NOT NULL,
 assessment TEXT NOT NULL DEFAULT 'unreviewed' CHECK(assessment IN ('unreviewed','accepted','rejected')),
 note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE request_allocations (
 id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES requests(id),
 resource_kind TEXT NOT NULL CHECK(resource_kind IN ('machine','worker')),
 resource_id INTEGER NOT NULL, resource_name TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX active_resource ON request_allocations(resource_kind,resource_id) WHERE active=1;
CREATE UNIQUE INDEX active_request ON request_allocations(request_id) WHERE active=1;
CREATE TABLE request_reviews (
 id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES requests(id),
 decision TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
