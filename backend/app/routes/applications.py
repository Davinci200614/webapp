import hashlib
import json
import secrets
from urllib.parse import unquote
from datetime import date
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator
from ..auth import Role, require_admin
from ..db import connect
from ..request_workflow import details, dispatch
from .. import notifications
from ..document_checklist import message as checklist_message
from .requests import _mutations_enabled

router = APIRouter(prefix='/api')

class Application(BaseModel):
    whatsapp_updates: bool = False
    name: str = Field(min_length=1,max_length=120)
    phone: str = Field(pattern=r'^\+?[0-9]{8,15}$')
    resource_kind: Literal['machine','worker'] = 'machine'
    machine_type: str = Field(default='',max_length=120)
    operation: str = Field(min_length=1,max_length=120)
    location: str = Field(min_length=1,max_length=160)
    preferred_date: date
    area_hectares: float | None = Field(default=None,gt=0,allow_inf_nan=False)
    urgency_level: Literal['normal','urgent','critical'] = 'normal'
    notes: str = Field(default='',max_length=3000)

    @field_validator('name','operation','location')
    @classmethod
    def text(cls,value):
        if not value.strip(): raise ValueError('Required field')
        return value.strip()

    @model_validator(mode='after')
    def valid(self):
        if self.resource_kind == 'machine' and not self.machine_type.strip():
            raise ValueError('Machine type is required')
        if self.preferred_date < date.today(): raise ValueError('Choose today or a future date')
        return self


def owner(db, request_id, token):
    row = db.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
    if not row or not token or not row['tracking_hash'] or not secrets.compare_digest(row['tracking_hash'], hashlib.sha256(token.encode()).hexdigest()):
        raise HTTPException(404,'Request not found or tracking code invalid')
    return row

@router.post('/applications',status_code=201)
def create(payload: Application, tasks: BackgroundTasks):
    _mutations_enabled()
    token = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO farmers(phone) VALUES (?)',(payload.phone,))
        cursor = db.execute("INSERT INTO requests(farmer_phone,payload,status,tracking_hash) VALUES (?,?,'pending_review',?)",
                            (payload.phone,json.dumps(payload.model_dump(mode='json'),ensure_ascii=False),hashlib.sha256(token.encode()).hexdigest()))
        if payload.whatsapp_updates:
            notifications.enqueue(db,cursor.lastrowid,payload.phone,checklist_message(cursor.lastrowid))
        result={'id':cursor.lastrowid,'tracking_code':token,'document_checklist':checklist_message(cursor.lastrowid)}
    tasks.add_task(notifications.drain)
    return result

@router.get('/applications/{request_id}')
def track(request_id:int,x_request_token:str|None=Header(default=None)):
    with connect() as db: return details(db,owner(db,request_id,x_request_token))

class Supplement(BaseModel):
    information: str = Field(min_length=1,max_length=3000)

@router.post('/applications/{request_id}/information')
def supplement(request_id:int,payload:Supplement,x_request_token:str|None=Header(default=None)):
    _mutations_enabled()
    if not payload.information.strip(): raise HTTPException(422,'Information is required')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=owner(db,request_id,x_request_token)
        if row['status']!='pending_review': raise HTTPException(409,'Request is closed for changes')
        db.execute("INSERT INTO request_reviews(request_id,decision,note) VALUES (?,'applicant_information',?)",(request_id,payload.information))
        db.execute("UPDATE requests SET review_state='pending',updated_at=CURRENT_TIMESTAMP WHERE id=?",(request_id,))
    return {'ok':True}

@router.post('/applications/{request_id}/documents',status_code=201)
async def upload(request_id:int,request:Request,x_request_token:str|None=Header(default=None),x_filename:str=Header(default='document')):
    _mutations_enabled()
    with connect() as db:
        row=owner(db,request_id,x_request_token)
        if row['status']!='pending_review': raise HTTPException(409,'Request is closed for changes')
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>5*1024*1024: raise HTTPException(413,'Maximum document size is 5 MB')
    raw=bytes(content)
    mime = 'application/pdf' if raw.startswith(b'%PDF-') else 'image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if raw.startswith(b'\xff\xd8\xff') else None
    if not mime: raise HTTPException(415,'Upload a PDF, PNG or JPEG document')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=owner(db,request_id,x_request_token)
        if row['status']!='pending_review': raise HTTPException(409,'Request is closed for changes')
        if db.execute('SELECT count(*) FROM request_documents WHERE request_id=?',(request_id,)).fetchone()[0]>=10: raise HTTPException(409,'Maximum 10 documents per request')
        cursor=db.execute('INSERT INTO request_documents(request_id,name,mime,content) VALUES (?,?,?,?)',(request_id,unquote(x_filename)[:160],mime,raw))
    return {'id':cursor.lastrowid}

@router.get('/request-documents/{document_id}')
def download(document_id:int,_:Role=Depends(require_admin)):
    with connect() as db: row=db.execute('SELECT * FROM request_documents WHERE id=?',(document_id,)).fetchone()
    if not row: raise HTTPException(404,'Document not found')
    return Response(bytes(row['content']),media_type=row['mime'],headers={'Content-Disposition':'attachment; filename="document"','X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

class Assessment(BaseModel):
    assessment: Literal['accepted','rejected','unreviewed']
    note: str = Field(default='',max_length=2000)

@router.patch('/request-documents/{document_id}')
def assess(document_id:int,payload:Assessment,_:Role=Depends(require_admin)):
    _mutations_enabled()
    with connect() as db:
        result=db.execute('UPDATE request_documents SET assessment=?,note=? WHERE id=?',(payload.assessment,payload.note,document_id))
        if not result.rowcount: raise HTTPException(404,'Document not found')
    return {'ok':True}

class Review(BaseModel):
    note: str = Field(min_length=1,max_length=2000)

@router.post('/requests/{request_id}/more-information')
def more_information(request_id:int,payload:Review,tasks:BackgroundTasks,_:Role=Depends(require_admin)):
    _mutations_enabled()
    if not payload.note.strip(): raise HTTPException(422,'Describe the information or documents needed')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT status,farmer_phone,payload,tracking_hash FROM requests WHERE id=?',(request_id,)).fetchone()
        if not row: raise HTTPException(404,'Request not found')
        if row['status']!='pending_review': raise HTTPException(409,'Only pending requests can be reviewed')
        db.execute("UPDATE requests SET review_state='needs_information',review_note=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(payload.note,request_id))
        db.execute("INSERT INTO request_reviews(request_id,decision,note) VALUES (?,'needs_information',?)",(request_id,payload.note))
        # Supersede an undelivered older instruction for this same request.
        db.execute("UPDATE whatsapp_notifications SET state='failed',error='superseded' WHERE request_id=? AND state IN ('pending','waiting_for_client')",(request_id,))
        wants_updates=row['tracking_hash'] is None or json.loads(row['payload']).get('whatsapp_updates',False)
        notification_id=notifications.enqueue(db,request_id,row['farmer_phone'],f"الإدارة طلبات معلومات أو وثائق إضافية للطلب #{request_id}:\n{payload.note}\nصيفط الجواب أو الوثائق هنا فالواتساب مع #{request_id} فالوصف. الإدارة هي اللي كتراجعهم.") if wants_updates else None
    tasks.add_task(notifications.drain)
    return {'ok':True,'notification_id':notification_id,'notification_status':'queued' if notification_id else 'not_requested'}

@router.post('/requests/dispatch')
def retry(_:Role=Depends(require_admin)):
    _mutations_enabled()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        dispatch(db)
    return {'ok':True}

@router.delete('/applications/{request_id}/documents/{document_id}')
def remove_document(request_id:int,document_id:int,x_request_token:str|None=Header(default=None)):
    _mutations_enabled()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=owner(db,request_id,x_request_token)
        if row['status']!='pending_review': raise HTTPException(409,'Request is closed for changes')
        document=db.execute('SELECT name,assessment FROM request_documents WHERE id=? AND request_id=?',(document_id,request_id)).fetchone()
        if not document: raise HTTPException(404,'Document not found')
        if document['assessment']=='accepted': raise HTTPException(409,'An accepted document cannot be removed')
        db.execute("INSERT INTO request_reviews(request_id,decision,note) VALUES (?,'document_removed',?)",(request_id,document['name']+' ('+document['assessment']+')'))
        db.execute('DELETE FROM request_documents WHERE id=?',(document_id,))
    return {'ok':True}

@router.post('/requests/{request_id}/notifications/retry')
def retry_notification(request_id:int,tasks:BackgroundTasks,_:Role=Depends(require_admin)):
    _mutations_enabled()
    with connect() as db:
        row=db.execute('SELECT id FROM whatsapp_notifications WHERE request_id=? ORDER BY id DESC LIMIT 1',(request_id,)).fetchone()
        if not row:raise HTTPException(404,'No notification to retry')
        db.execute("UPDATE whatsapp_notifications SET state='pending',attempts=0,error=NULL,next_attempt_at=CURRENT_TIMESTAMP WHERE id=? AND state IN ('failed','waiting_for_client')",(row['id'],))
    tasks.add_task(notifications.drain)
    return {'ok':True}
