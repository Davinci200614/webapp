"""Durable inbound work, drained in receipt order by one application worker."""
import asyncio
import json
from .db import connect
from .service import handle_message
from .diagnostics import event

_drain_lock = asyncio.Lock()


def enqueue(messages):
    with connect() as db:
        for message in messages:
            if isinstance(message, dict) and message.get('id') and message.get('from'):
                db.execute('INSERT OR IGNORE INTO webhook_inbox(id,phone,payload) VALUES (?,?,?)',
                           (message['id'], message['from'], json.dumps(message, ensure_ascii=False)))


async def drain():
    async with _drain_lock:
        with connect() as db:
            # Do not let later messages from a phone overtake an undelivered reply.
            rows = db.execute("""SELECT * FROM webhook_inbox i WHERE state='pending'
                AND next_attempt_at <= CURRENT_TIMESTAMP AND NOT EXISTS (
                SELECT 1 FROM webhook_inbox older WHERE older.phone=i.phone
                AND older.rowid<i.rowid AND older.state IN ('pending','running','failed'))
                ORDER BY rowid LIMIT 50""").fetchall()
        if rows:
            event('inbox.processing', outcome='started', message_count=len(rows))
        async def process(row):
            with connect() as db:
                db.execute("UPDATE webhook_inbox SET state='running',attempts=attempts+1 WHERE id=?", (row['id'],))
            try:
                await handle_message(json.loads(row['payload']))
                with connect() as db:
                    message = db.execute('SELECT status FROM messages WHERE id=?', (row['id'],)).fetchone()
                if not message or message['status'] != 'processed':
                    raise RuntimeError('message_incomplete')
            except Exception as exc:
                attempts = row['attempts'] + 1
                with connect() as db:
                    db.execute("""UPDATE webhook_inbox SET state=?,error=?,
                        next_attempt_at=datetime('now',?) WHERE id=?""",
                        ('failed' if attempts >= 5 else 'pending', type(exc).__name__,
                         f'+{min(300, 2 ** attempts)} seconds', row['id']))
                event('inbox.retry', outcome='error', exception_type=type(exc).__name__)
            else:
                with connect() as db:
                    db.execute("UPDATE webhook_inbox SET state='done',error=NULL WHERE id=?", (row['id'],))
                event('inbox.processed', outcome='ok')

        await asyncio.gather(*(process(row) for row in rows))


async def run():
    while True:
        try:
            await drain()
            from . import notifications
            await notifications.drain()
        except Exception as exc:
            event('inbox.worker', outcome='error', exception_type=type(exc).__name__)
        await asyncio.sleep(1)
