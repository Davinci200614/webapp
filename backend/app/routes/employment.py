from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from ..auth import Role, current_role
from .. import config
from ..db import connect
from ..request_workflow import dispatch
from ..employment import normalize

router = APIRouter(prefix='/api/employment', tags=['employment'])

@router.get('')
def listings(kind: Literal['worker','job'] | None = None, q: str = Query('',max_length=160),
             location: str = Query('',max_length=100)):
    # Only fields explicitly confirmed for publication are public. Never expose owner_phone.
    with connect() as db:
        rows = [dict(r) for r in db.execute("""SELECT id,kind,name,location,work,details,contact,is_demo,created_at
            FROM employment_listings WHERE status='active' ORDER BY is_demo,id DESC""")]
    return [r for r in rows if (not kind or r['kind']==kind)
            and normalize(location) in normalize(r['location'])
            and normalize(q) in normalize(' '.join(str(r[k]) for k in ('name','work','details','location')))]

class ListingStatus(BaseModel):
    status: Literal['active','inactive']

@router.patch('/{listing_id}')
def moderate(listing_id: int, payload: ListingStatus, _: Role = Depends(current_role)):
    if not config.MUTATIONS_ENABLED:
        raise HTTPException(503,'Mutations are disabled')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        result=db.execute('UPDATE employment_listings SET status=? WHERE id=?',(payload.status,listing_id))
        if not result.rowcount: raise HTTPException(404,'Listing not found')
        dispatch(db)
    return {'id':listing_id,'status':payload.status}
