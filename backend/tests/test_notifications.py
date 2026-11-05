import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from fastapi.testclient import TestClient
from app import config,db,notifications
from app.main import app
from app.document_checklist import message

class NotificationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        settings=patch.multiple(config,DB_PATH=str(Path(temp.name)/'db'),WHATSAPP_DOCUMENT_TEMPLATE='',ADMIN_API_KEY='admin-test',MUTATIONS_ENABLED=True)
        settings.start();self.addCleanup(settings.stop);db.init_db()
        with db.connect() as con:
            con.execute("INSERT INTO farmers(phone) VALUES ('+212600000001')")
            con.execute("INSERT INTO requests(farmer_phone,payload,status) VALUES ('+212600000001','{}','pending_review')")
        self.send=AsyncMock()
        p=patch.object(notifications,'send_text',self.send);p.start();self.addCleanup(p.stop)

    def recent(self):
        with db.connect() as con:
            con.execute("INSERT INTO messages(id,farmer_phone,kind) VALUES ('inbound','+212600000001','text')")

    async def test_admin_request_notifies_client_with_exact_note(self):
        self.recent()
        with TestClient(app,backend='asyncio',backend_options={'use_uvloop':True}) as client:
            response=client.post('/api/requests/1/more-information',headers={'Authorization':'Bearer admin-test'},json={'note':'تصريح بمكان الأشغال'})
        self.assertEqual(response.status_code,200,response.text)
        self.send.assert_awaited_once()
        self.assertEqual(self.send.call_args.args[0],'212600000001')
        self.assertIn('تصريح بمكان الأشغال',self.send.call_args.args[1])
        self.assertIn('#1',self.send.call_args.args[1])
        with db.connect() as con:self.assertEqual(con.execute('SELECT state FROM whatsapp_notifications').fetchone()[0],'sent')

    async def test_closed_window_waits_then_sends_on_client_message(self):
        with db.connect() as con:notifications.enqueue(con,1,'+212600000001','Admin needs a document')
        await notifications.drain();self.send.assert_not_awaited()
        with db.connect() as con:self.assertEqual(con.execute('SELECT state FROM whatsapp_notifications').fetchone()[0],'waiting_for_client')
        self.recent();notifications.wake('212600000001');await notifications.drain()
        self.send.assert_awaited_once()

    async def test_failure_is_retryable_not_reported_as_sent(self):
        self.recent();self.send.side_effect=RuntimeError('failed')
        with db.connect() as con:notifications.enqueue(con,1,'212600000001','Admin asks for document')
        await notifications.drain()
        with db.connect() as con:
            row=con.execute('SELECT * FROM whatsapp_notifications').fetchone()
            self.assertEqual(row['state'],'pending');self.assertEqual(row['attempts'],1);self.assertIsNone(row['sent_at'])

    async def test_approved_template_is_used_outside_window(self):
        with db.connect() as con:notifications.enqueue(con,1,'212600000001','Admin document request')
        template=AsyncMock()
        with patch.object(config,'WHATSAPP_DOCUMENT_TEMPLATE','document_update'),patch.object(notifications,'send_template',template):await notifications.drain()
        template.assert_awaited_once();self.send.assert_not_awaited()
        self.assertEqual(template.call_args.args[3],['1','Admin document request'])

    async def test_checklist_is_explicitly_an_example_and_contains_request_id(self):
        text=message(42)
        self.assertIn('#42',text);self.assertIn('كمثال',text);self.assertIn('ماشي وثائق مفروضة',text)
