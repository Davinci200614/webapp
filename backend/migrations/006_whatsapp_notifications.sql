CREATE TABLE whatsapp_notifications (
 id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES requests(id),
 phone TEXT NOT NULL, body TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','sending','sent','waiting_for_client','failed')),
 attempts INTEGER NOT NULL DEFAULT 0, error TEXT,
 next_attempt_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, sent_at TEXT
);
CREATE INDEX whatsapp_notifications_due ON whatsapp_notifications(state,next_attempt_at);
