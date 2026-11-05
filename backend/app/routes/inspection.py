from fastapi import APIRouter, Depends, HTTPException, Request
from ..auth import require_admin
from ..db import connect
from .. import config
router = APIRouter()

@router.get('/api/debug/snapshot')
def database_snapshot(request: Request, phone: str | None = None, _: str = Depends(require_admin)):
    if not config.INSPECTOR_ENABLED:
        raise HTTPException(403, "Inspector is disabled")
    if phone and len(phone) > 64:
        raise HTTPException(400, 'Invalid phone filter')
    from ..db import database_path, SCHEMA_VERSION
    with connect() as con:
        counts = {name: con.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                  for name in ('messages','requests','employment_listings','machines','conversations','dialogue_drafts')}
        condition, params = ('WHERE m.farmer_phone=?', [phone]) if phone else ('', [])
        messages = [dict(row) for row in con.execute(f'''SELECT m.id,m.farmer_phone,m.kind,m.text,m.status,m.error,m.created_at,
            a.route,a.error_code,a.duration_ms,t.text AS reply
            FROM messages m LEFT JOIN dialogue_audit a ON a.message_id=m.id
            LEFT JOIN conversation_turns t ON t.message_id=m.id AND t.role='assistant'
            {condition} ORDER BY m.rowid DESC LIMIT 50''', params)]
        where, values = ('WHERE phone=?', [phone]) if phone else ('', [])
        drafts = [dict(row) for row in con.execute(f'SELECT phone,task,pending,payload FROM dialogue_drafts {where}', values)]
        where_machine = 'WHERE farmer_phone=?' if phone else ''
        drafts += [dict(phone=row['farmer_phone'],task='machine',pending=row['last_question_field'],payload=row['payload'])
                   for row in con.execute(f'SELECT * FROM conversations {where_machine}', values)]
        from ..contacts import valid_contact
        records = [{**dict(row), 'contact_format_valid':bool(valid_contact(row['contact']))} for row in con.execute('SELECT id,kind,name,location,work,details,contact,status,is_demo,owner_phone FROM employment_listings ORDER BY is_demo,id DESC LIMIT 100')]
        equipment = [dict(row) for row in con.execute('SELECT * FROM machines ORDER BY is_demo,id DESC LIMIT 100')]
        saved = [dict(row) for row in con.execute('SELECT id,farmer_phone,payload,status,created_at FROM requests ORDER BY id DESC LIMIT 50')]
        from ..catalog import terms as catalog_terms
        terms = catalog_terms(con)
    return {'database_path': str(database_path()), 'schema_version': SCHEMA_VERSION, 'counts': counts,
            'messages': messages, 'drafts': drafts, 'listings': records, 'machines': equipment,
            'requests': saved, 'catalog': terms}

@router.get('/api/debug/inbox')
def inbox_rows(_: str = Depends(require_admin)):
    if not config.INSPECTOR_ENABLED:
        raise HTTPException(403, 'Inspector is disabled')
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT id,state,attempts,error,created_at FROM webhook_inbox ORDER BY rowid DESC LIMIT 100')]

@router.post('/api/debug/inbox/{message_id}/retry')
def retry(message_id: str, _: str = Depends(require_admin)):
    if not config.INSPECTOR_ENABLED or not config.MUTATIONS_ENABLED:
        raise HTTPException(403, 'Retries are disabled')
    with connect() as db:
        result=db.execute("UPDATE webhook_inbox SET state='pending',attempts=0,next_attempt_at=CURRENT_TIMESTAMP WHERE id=? AND state='failed'",(message_id,))
        if not result.rowcount: raise HTTPException(404,'Failed message not found')
    return {'ok':True}
