"""Primary AI routing, deterministic outage fallback, and explicit consent."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from app import config,conversation,db,service
from app.ai import AIError
from app.understanding import Understanding,Facts

class ModelFirstTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        settings=patch.multiple(config,DB_PATH=str(Path(temp.name)/'test.db'),CONVERSATION_CORE='v2',CONVERSATION_ROUTING='model_first',CONVERSATION_REPLY_STYLE='template')
        settings.start();self.addCleanup(settings.stop);db.init_db()
        self.model=AsyncMock()
        for obj,name,value in [(conversation,'understand',self.model),(service,'send_text',AsyncMock()),(service,'send_interactive',AsyncMock())]:
            p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
        self.counter=0

    async def turn(self,text):
        self.counter+=1
        await service.handle_message({'id':str(self.counter),'from':'owner','type':'text','text':{'body':text}})

    async def test_each_conversational_message_calls_model_with_context(self):
        self.model.side_effect=[
            Understanding(task='machine',facts=Facts(machine_type='tractor')),
            Understanding(task='machine',facts=Facts(operation='plowing')),
            Understanding(task='machine',facts=Facts(area_hectares=20)),
            Understanding(task='machine',facts=Facts(location='دكالة')),
            Understanding(task='machine',facts=Facts(preferred_date='2099-01-01')),
        ]
        for text in ['tractor','labour','20','خويا كاينة فواحد الأرض فدكالة','2099-01-01']:
            await self.turn(text)
        self.assertEqual(self.model.await_count,5)
        self.assertEqual(self.model.call_args_list[2].args[1]['active_task'],'machine')
        self.assertEqual(self.model.call_args_list[3].args[1]['draft']['area_hectares'],20)
        with db.connect() as con:
            routes=[r['route'] for r in con.execute('SELECT route FROM dialogue_audit')]
            self.assertEqual(routes,['model']*5)
            self.assertEqual(con.execute('SELECT count(*) FROM requests').fetchone()[0],0)
        await self.turn('oui')
        self.assertEqual(self.model.await_count,5)
        with db.connect() as con:
            request=con.execute('SELECT * FROM requests').fetchone()
            self.assertEqual(request['status'],'pending_review')
            self.assertEqual(json.loads(request['payload'])['location'],'دكالة')

    async def test_provider_failure_uses_rules_and_logs_fallback(self):
        self.model.side_effect=AIError('conversation_timeout')
        await self.turn('tractor')
        self.model.assert_awaited_once()
        with db.connect() as con:
            audit=con.execute('SELECT * FROM dialogue_audit').fetchone()
            self.assertEqual(audit['route'],'fallback')
            self.assertEqual(audit['error_code'],'conversation_timeout')
            self.assertEqual(json.loads(con.execute('SELECT payload FROM conversations').fetchone()[0])['machine_type'],'tractor')

    async def test_model_cannot_confirm_a_request_from_mixed_text(self):
        self.model.return_value=Understanding(task='machine',action='confirm',facts=Facts(machine_type='tractor',operation='plowing',area_hectares=2,location='Meknes',preferred_date='2099-01-01'))
        await self.turn('yes but change my details')
        self.model.assert_awaited_once()
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM requests').fetchone()[0],0)

    async def test_document_policy_question_answers_without_model_and_preserves_draft(self):
        self.model.side_effect=AIError('conversation_timeout')
        with db.connect() as con:
            con.execute("INSERT INTO farmers(phone) VALUES ('owner')")
            con.execute("INSERT INTO conversations(farmer_phone,payload,last_question_field) VALUES ('owner',?,'location')",(json.dumps({'intent':'request_machine','machine_type':'tractor','area_hectares':20}),))
            con.execute("INSERT INTO dialogue_sessions(phone,task) VALUES ('owner','machine')")
        await self.turn('واش خصني شي وثيقة ؟')
        self.model.assert_not_awaited()
        with db.connect() as con:
            reply=con.execute("SELECT text FROM conversation_turns WHERE role='assistant'").fetchone()[0]
            self.assertIn('PDF',reply)
            self.assertIn('الإدارة',reply)
            self.assertEqual(json.loads(con.execute('SELECT payload FROM conversations').fetchone()[0])['area_hectares'],20)
            self.assertEqual(con.execute('SELECT task FROM dialogue_sessions').fetchone()[0],'machine')
            self.assertEqual(con.execute('SELECT route FROM dialogue_audit').fetchone()[0],'policy')

    async def test_timeout_on_question_preserves_complete_request_summary(self):
        data={'intent':'request_machine','machine_type':'tractor','operation':'plowing','area_hectares':20,'location':'Meknes','preferred_date':'2099-01-01'}
        with db.connect() as con:
            con.execute("INSERT INTO farmers(phone) VALUES ('owner')")
            con.execute("INSERT INTO conversations(farmer_phone,payload) VALUES ('owner',?)",(json.dumps(data),))
            con.execute("INSERT INTO dialogue_sessions(phone,task) VALUES ('owner','machine')")
        self.model.side_effect=AIError('conversation_timeout')
        await self.turn('واش نقدر نسولك على هاد الطلب؟')
        with db.connect() as con:
            reply=con.execute("SELECT text FROM conversation_turns WHERE role='assistant'").fetchone()[0]
            self.assertIn('Meknes',reply)
            self.assertNotIn('مرحبا! قول ليا شنو محتاج',reply)
