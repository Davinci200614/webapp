"""Attach client-supplied WhatsApp evidence to that sender's pending request."""
import re
from .db import connect
from . import config


def pending_request(db, phone, text, needs_information=False):
    # Meta sender numbers have no plus prefix; web forms accept either representation.
    clauses="status='pending_review' AND ltrim(farmer_phone,'+')=?"
    values=[phone.lstrip('+')]
    match=re.search(r'#(\d+)\b',text)
    if match:
        clauses+=' AND id=?';values.append(int(match.group(1)))
    if needs_information:
        clauses+=" AND review_state='needs_information'"
    rows=db.execute('SELECT * FROM requests WHERE '+clauses,values).fetchall()
    return rows[0] if len(rows)==1 else None, rows


async def document_reply(msg, phone, download):
    if not config.MUTATIONS_ENABLED:
        return 'تسجيل الوثائق موقف مؤقتا. عاود حاول من بعد.'
    media=msg.get(msg['type'],{})
    caption=media.get('caption','')
    with connect() as db:
        row,rows=pending_request(db,phone,caption)
    if not row:
        return 'عندك عدة طلبات. زيد رقم الطلب فالوصف، مثلا #123.' if rows else 'ما لقيناش طلب قيد المراجعة بهاد الرقم. أكد طلبك أولا، ومن بعد صيفط الوثائق مع رقم الطلب مثلا #123.'
    if not media.get('id'):
        return 'ما قدرناش نقراو الوثيقة. عاود صيفطها PDF أو صورة.'
    content=await download(media['id'])
    if len(content)>5*1024*1024:
        return 'الوثيقة كبيرة. صيفط ملف أقل من 5 ميغا.'
    mime='application/pdf' if content.startswith(b'%PDF-') else 'image/png' if content.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if content.startswith(b'\xff\xd8\xff') else None
    if not mime:
        return 'صيفط الوثيقة بصيغة PDF أو JPEG أو PNG.'
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        fresh=db.execute("SELECT status FROM requests WHERE id=?",(row['id'],)).fetchone()
        if fresh['status']!='pending_review':
            return 'هاد الطلب ما بقاش مفتوح لإضافة الوثائق.'
        if db.execute('SELECT count(*) FROM request_documents WHERE request_id=?',(row['id'],)).fetchone()[0]>=10:
            return 'وصلتي للحد ديال 10 وثائق لهاد الطلب.'
        if not db.execute('SELECT 1 FROM request_documents WHERE request_id=? AND content=?',(row['id'],content)).fetchone():
            db.execute('INSERT INTO request_documents(request_id,name,mime,content) VALUES (?,?,?,?)',
                       (row['id'],str(media.get('filename') or 'WhatsApp document')[:160],mime,content))
        db.execute("UPDATE requests SET review_state='pending',updated_at=CURRENT_TIMESTAMP WHERE id=?",(row['id'],))
    return f"تسجلات الوثيقة مع الطلب #{row['id']}. الإدارة غادي تراجعها قبل الموافقة."


def information_reply(phone,text):
    if not config.MUTATIONS_ENABLED: return None
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row,rows=pending_request(db,phone,text,needs_information=True)
        if not row:
            if rows: return 'عندك عدة طلبات خاصها معلومات إضافية. زيد رقم الطلب مثلا #123 مع الجواب.'
            return None
        information=re.sub(r'#\d+\b','',text).strip()
        if not information: return 'زيد المعلومات المطلوبة مع رقم الطلب.'
        if len(information)>3000: return 'المعلومات طويلة. صيفط جواب أقل من 3000 حرف.'
        db.execute("INSERT INTO request_reviews(request_id,decision,note) VALUES (?,'applicant_information',?)",(row['id'],information))
        db.execute("UPDATE requests SET review_state='pending',updated_at=CURRENT_TIMESTAMP WHERE id=?",(row['id'],))
    return f"تسجل الجواب ديالك مع الطلب #{row['id']}. الإدارة غادي تراجعو."


def status_reply(phone,text):
    if text.strip().casefold() not in {'status','statut','mes demandes','طلباتي','حالة طلبي'}:
        return None
    with connect() as db:
        rows=db.execute("SELECT id,status,review_note,review_state,allocation_state FROM requests WHERE ltrim(farmer_phone,'+')=? ORDER BY id DESC LIMIT 5",(phone.lstrip('+'),)).fetchall()
    if not rows: return 'ما عندك حتى طلب مسجل دابا.'
    labels={'pending_review':'قيد المراجعة','approved':'مقبول','rejected':'مرفوض','completed':'مكتمل','draft':'مسودة'}
    result=[]
    for row in rows:
        line=f"#{row['id']} · {labels.get(row['status'],row['status'])}"
        if row['review_state']=='needs_information': line+=' · خاص معلومات أو وثائق إضافية: '+row['review_note']
        if row['allocation_state']=='waiting': line+=' · فلائحة الانتظار حسب الأولوية'
        if row['allocation_state']=='allocated': line+=' · تخصص ليك مورد، التعاونية غادي تنسق معاك'
        result.append(line)
    return '\n'.join(result)
