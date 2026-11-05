"""Unified transport and durability regressions; no live provider calls."""
import asyncio
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app import config, db, inbox, service, conversation
from app.main import app

class UnifiedFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        p=patch.object(config,'DB_PATH',str(Path(self.temp.name)/'target.db'))
        p.start(); self.addCleanup(p.stop)
        style=patch.object(config,'CONVERSATION_REPLY_STYLE','template');style.start();self.addCleanup(style.stop)
        db.init_db()

    async def test_durable_inbox_survives_enqueue_and_deduplicates(self):
        message={'id':'one','from':'212600000000','type':'text','text':{'body':'menu'}}
        inbox.enqueue([message,message])
        with patch.object(service,'send_interactive',AsyncMock()),patch.object(service,'send_text',AsyncMock()):
            await inbox.drain()
            await inbox.drain()
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM webhook_inbox').fetchone()[0],1)
            self.assertEqual(con.execute('SELECT state FROM webhook_inbox').fetchone()[0],'done')
            self.assertEqual(con.execute('SELECT count(*) FROM messages').fetchone()[0],1)

    async def test_interactive_reply_retry_preserves_payload_and_arms_confirmation(self):
        from app.understanding import Understanding, Facts
        fields=Facts(machine_type='tractor',operation='plowing',area_hectares=2,location='Meknes',preferred_date='2099-11-05')
        sent=AsyncMock(side_effect=[RuntimeError('send failed'),{}])
        message={'id':'summary','from':'212600000000','type':'text','text':{'body':'request with explicit fields and date'}}
        with patch.object(conversation,'understand',AsyncMock(return_value=Understanding(task='machine',facts=fields))),patch.object(service,'send_interactive',sent):
            with self.assertRaises(RuntimeError): await service.handle_message(message)
            await service.handle_message(message)
        self.assertEqual(sent.await_count,2)
        self.assertEqual(sent.call_args_list[0],sent.call_args_list[1])
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT armed FROM dialogue_confirmations').fetchone()[0],1)

    async def test_failed_message_blocks_same_phone_but_not_other_phone(self):
        inbox.enqueue([{'id':'bad','from':'one'},{'id':'later','from':'one'},{'id':'other','from':'two'}])
        calls=[]
        async def handle(message):
            calls.append(message['id'])
            if message['id']=='bad':raise RuntimeError('failed')
            with db.connect() as con:
                con.execute('INSERT OR IGNORE INTO farmers(phone) VALUES (?)',(message['from'],))
                con.execute("INSERT INTO messages(id,farmer_phone,kind,status) VALUES (?,?,'text','processed')",(message['id'],message['from']))
        with patch.object(inbox,'handle_message',handle): await inbox.drain()
        self.assertEqual(calls,['bad','other'])

class WebhookTests(unittest.TestCase):
    def test_signature_and_durable_acceptance(self):
        with tempfile.TemporaryDirectory() as temp,patch.multiple(config,DB_PATH=str(Path(temp)/'db'),META_APP_SECRET='secret',META_VERIFY_TOKEN='verify'):
            with TestClient(app) as client:
                self.assertEqual(client.get('/webhook/whatsapp',params={'hub.mode':'subscribe','hub.verify_token':'verify','hub.challenge':'42'}).text,'42')
                body=json.dumps({'entry':[]}).encode()
                sig=hmac.new(b'secret',body,hashlib.sha256).hexdigest()
                self.assertEqual(client.post('/webhook/whatsapp',content=body,headers={'x-hub-signature-256':'sha256='+sig}).status_code,200)
                self.assertEqual(client.post('/webhook/whatsapp',content=body).status_code,403)

class InboxConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    setUp = UnifiedFlowTests.setUp
    async def test_different_phones_do_not_wait_for_each_other(self):
        inbox.enqueue([{'id':'slow','from':'one'},{'id':'fast','from':'two'}])
        started=asyncio.Event();finished=asyncio.Event()
        async def handle(message):
            if message['id']=='slow':
                started.set()
                await asyncio.wait_for(finished.wait(),timeout=1)
            else:
                await started.wait()
                finished.set()
            with db.connect() as con:
                con.execute('INSERT INTO farmers(phone) VALUES (?)',(message['from'],))
                con.execute("INSERT INTO messages(id,farmer_phone,kind,status) VALUES (?,?,'text','processed')",(message['id'],message['from']))
        with patch.object(inbox,'handle_message',handle): await inbox.drain()
        with db.connect() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM webhook_inbox WHERE state='done'").fetchone()[0],2)
