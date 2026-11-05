"""Transactional resource dispatch for approved requests; reservations last until closure."""
import json
from .priority import machine_compatibility_for, priority_for
from .catalog import terms
from .employment import normalize


def dispatch(db):
    machines = [dict(r) for r in db.execute('SELECT * FROM machines WHERE is_demo=0')]
    workers = [dict(r) for r in db.execute("SELECT * FROM employment_listings WHERE kind='worker' AND status='active' AND is_demo=0")]
    reserved = {(r['resource_kind'], r['resource_id']) for r in db.execute('SELECT * FROM request_allocations WHERE active=1')}
    entries = terms(db)
    waiting = []
    for row in db.execute("SELECT * FROM requests WHERE status='approved' AND allocation_state!='allocated'"):
        data = json.loads(row['payload'])
        fit, _, _ = machine_compatibility_for(data, machines, entries)
        score, _ = priority_for(data, row['created_at'], machine_fit=fit)
        waiting.append((score, dict(row), data))
    for _, row, data in sorted(waiting, key=lambda x: (-x[0], x[1]['created_at'], x[1]['id'])):
        kind = 'worker' if data.get('resource_kind') == 'worker' else 'machine'
        available = [m for m in machines if ('machine', m['id']) not in reserved]
        if kind == 'machine':
            fit, _, matches = machine_compatibility_for(data, available, entries)
            candidates = matches if fit == 'local' else []
        else:
            candidates = [w for w in workers if ('worker', w['id']) not in reserved
                          and normalize(w['location']) == normalize(data.get('location', ''))
                          and normalize(data.get('operation', '')) == normalize(w['work'])]
        if candidates:
            resource = sorted(candidates, key=lambda r: r['id'])[0]
            db.execute('INSERT INTO request_allocations(request_id,resource_kind,resource_id,resource_name) VALUES (?,?,?,?)',
                       (row['id'], kind, resource['id'], resource['name']))
            reserved.add((kind, resource['id']))
            state = 'allocated'
        else:
            state = 'waiting'
        db.execute('UPDATE requests SET allocation_state=?,updated_at=CURRENT_TIMESTAMP WHERE id=?', (state, row['id']))


def details(db, row):
    item = dict(row)
    item.pop('tracking_hash', None)
    item['payload'] = json.loads(item['payload'])
    item['notification'] = next((dict(r) for r in db.execute('SELECT id,state,error,sent_at FROM whatsapp_notifications WHERE request_id=? ORDER BY id DESC LIMIT 1',(row['id'],))),None)
    from .document_checklist import message
    item['document_checklist'] = message(row['id'])
    item['documents'] = [dict(r) for r in db.execute('SELECT id,name,mime,assessment,note,created_at FROM request_documents WHERE request_id=?', (row['id'],))]
    item['reviews'] = [dict(r) for r in db.execute('SELECT decision,note,created_at FROM request_reviews WHERE request_id=? ORDER BY id', (row['id'],))]
    item['allocation'] = next((dict(r) for r in db.execute('SELECT resource_kind,resource_id,resource_name FROM request_allocations WHERE request_id=? AND active=1', (row['id'],))), None)
    return item
