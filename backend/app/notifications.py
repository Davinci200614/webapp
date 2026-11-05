"""Durable WhatsApp admin notifications; Meta acceptance is not delivery proof."""
import asyncio
from . import config
from .db import connect
from .whatsapp import send_text,send_template
from .diagnostics import event

_lock=asyncio.Lock()

def enqueue(db,request_id,phone,body):
    return db.execute('INSERT INTO whatsapp_notifications(request_id,phone,body) VALUES (?,?,?)',(request_id,phone.lstrip('+'),body)).lastrowid

async def drain():
    async with _lock:
        with connect() as db:
            rows=db.execute("SELECT * FROM whatsapp_notifications WHERE state IN ('pending','waiting_for_client') AND next_attempt_at<=CURRENT_TIMESTAMP ORDER BY id LIMIT 20").fetchall()
        for row in rows:
            with connect() as db:
                recent=db.execute("SELECT 1 FROM messages WHERE ltrim(farmer_phone,'+')=? AND created_at>datetime('now','-23 hours','-50 minutes') LIMIT 1",(row['phone'],)).fetchone()
                if not recent and not config.WHATSAPP_DOCUMENT_TEMPLATE:
                    db.execute("UPDATE whatsapp_notifications SET state='waiting_for_client',error='template_required',next_attempt_at=datetime('now','+30 seconds') WHERE id=?",(row['id'],))
                    continue
                claimed=db.execute("UPDATE whatsapp_notifications SET state='sending',attempts=attempts+1 WHERE id=? AND state IN ('pending','waiting_for_client')",(row['id'],))
                if not claimed.rowcount:continue
            try:
                if recent:
                    await send_text(row['phone'],row['body'])
                else:
                    await send_template(row['phone'],config.WHATSAPP_DOCUMENT_TEMPLATE,config.WHATSAPP_TEMPLATE_LANGUAGE,[str(row['request_id']),row['body']])
            except Exception as exc:
                error=getattr(exc,'code',type(exc).__name__)
                with connect() as db:
                    db.execute("UPDATE whatsapp_notifications SET state=?,error=?,next_attempt_at=datetime('now',?) WHERE id=?",('failed' if row['attempts']>=4 else 'pending',str(error)[:120],f'+{min(300,2**(row["attempts"]+1))} seconds',row['id']))
                event('whatsapp.notification',outcome='error',error_code=str(error)[:120])
            else:
                with connect() as db:
                    db.execute("UPDATE whatsapp_notifications SET state='sent',sent_at=CURRENT_TIMESTAMP,error=NULL WHERE id=?",(row['id'],))
                event('whatsapp.notification',outcome='accepted')

def wake(phone):
    with connect() as db:
        db.execute("UPDATE whatsapp_notifications SET state='pending',next_attempt_at=CURRENT_TIMESTAMP WHERE phone=? AND state='waiting_for_client'",(phone.lstrip('+'),))
