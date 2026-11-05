import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,AsyncMock
from app import config,db,service
from app.whatsapp_documents import document_reply,information_reply,status_reply

class WhatsAppDocumentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        patches=patch.multiple(config,DB_PATH=str(Path(temp.name)/'test.db'),MUTATIONS_ENABLED=True)
        patches.start();self.addCleanup(patches.stop);db.init_db()
        with db.connect() as con:
            con.execute("INSERT INTO farmers(phone) VALUES ('+212600000001')")
            con.execute("INSERT INTO requests(farmer_phone,payload,status) VALUES ('+212600000001','{}','pending_review')")

    async def test_document_attaches_to_senders_request_once(self):
        message={'from':'212600000001','id':'document-message','type':'document','document':{'id':'media-id','filename':'proof.pdf','caption':'#1'}}
        with patch.object(service,'download_media',AsyncMock(return_value=b'%PDF-1.7 proof')) as download,patch.object(service,'send_text',AsyncMock()),patch.object(service,'send_interactive',AsyncMock()),patch.object(service.controller,'respond',AsyncMock()) as ai,patch.object(service,'transcribe',AsyncMock()) as transcribe:
            await service.handle_message(message)
            await service.handle_message(message)
        download.assert_awaited_once()
        ai.assert_not_awaited()
        transcribe.assert_not_awaited()
        with db.connect() as con:
            docs=con.execute('SELECT * FROM request_documents').fetchall()
            self.assertEqual(len(docs),1)
            self.assertEqual(docs[0]['request_id'],1)
            self.assertEqual(docs[0]['assessment'],'unreviewed')

    async def test_other_sender_and_ambiguous_request_cannot_receive_attachment(self):
        download=AsyncMock(return_value=b'%PDF-1.7')
        msg={'id':'message','type':'document','document':{'id':'media-id','caption':'#1'}}
        await document_reply(msg,'212699999999',download)
        download.assert_not_awaited()
        with db.connect() as con:
            con.execute("INSERT INTO requests(farmer_phone,payload,status) VALUES ('+212600000001','{}','pending_review')")
        msg['document']['caption']=''
        await document_reply(msg,'212600000001',download)
        download.assert_not_awaited()

    async def test_information_and_status_use_sender_identity(self):
        with db.connect() as con:
            con.execute("UPDATE requests SET review_state='needs_information',review_note='Please send land document' WHERE id=1")
        self.assertIn('Please send land document',status_reply('212600000001','status'))
        self.assertIsNone(information_reply('212699999999','#1 my land reference'))
        self.assertIsNotNone(information_reply('212600000001','#1 my land reference'))
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT review_state FROM requests').fetchone()[0],'pending')
            self.assertEqual(con.execute('SELECT note FROM request_reviews').fetchone()[0],'my land reference')

    async def test_invalid_file_is_not_saved(self):
        msg={'id':'message','type':'image','image':{'id':'media-id','caption':'#1'}}
        await document_reply(msg,'212600000001',AsyncMock(return_value=b'invalid file'))
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM request_documents').fetchone()[0],0)
