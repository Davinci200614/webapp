import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from app import config,conversation,db,service
from app.ai import AIError
from app.understanding import Facts,Understanding
from app.reply_writer import write_reply
from app.integrations.errors import IntegrationError

class ConversationalReplyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        settings=patch.multiple(config,DB_PATH=str(Path(temp.name)/'db'),CONVERSATION_ROUTING='model_first',CONVERSATION_REPLY_STYLE='model')
        settings.start();self.addCleanup(settings.stop);db.init_db()
        self.nlu=AsyncMock(return_value=Understanding(task='search_workers',facts=Facts(location='سلا')))
        self.writer=AsyncMock(return_value='فهمتك، باغي تلقى عمال. ما بان حتى إعلان هنا دابا؛ بغيتي نوجدوا عرض عمل؟')
        self.send=AsyncMock()
        for obj,name,value in [(conversation,'understand',self.nlu),(conversation,'write_reply',self.writer),(service,'send_text',self.send),(service,'send_interactive',self.send)]:
            p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
        self.count=0

    async def turn(self,text):
        self.count+=1
        await service.handle_message({'id':str(self.count),'from':'owner','type':'text','text':{'body':text}})
        with db.connect() as con:
            return con.execute("SELECT text FROM conversation_turns WHERE message_id=? AND role='assistant'",(str(self.count),)).fetchone()[0]

    async def test_model_words_actual_no_result_and_updates_transport_history(self):
        reply=await self.turn('كنقلب على عمال فسلا')
        self.writer.assert_awaited_once()
        self.assertIn('ما لقينا',self.writer.call_args.args[1])
        self.assertEqual(reply,self.writer.return_value)
        with db.connect() as con:
            payload=json.loads(con.execute('SELECT payload FROM dialogue_outgoing WHERE message_id=?',(str(self.count),)).fetchone()[0])
            self.assertEqual(payload['body']['text'],reply)
            self.assertEqual(len(payload['action']['buttons']),2)
            self.assertEqual(con.execute('SELECT count(*) FROM requests').fetchone()[0],0)

    async def test_sale_jadida_followup_keeps_worker_search_despite_ambiguous_model(self):
        await self.turn('كنقلب على عمال فسلا')
        self.nlu.return_value=Understanding(action='clarify')
        await self.turn('أو فسلا جديدة ؟')
        with db.connect() as con:
            context=conversation.context_data(con,'owner')
        self.assertEqual(context['last_search']['kind'],'worker')
        self.assertEqual(context['last_search']['location'],'سلا الجديدة')
        self.assertFalse(context.get('choose_publish',False))

    async def test_document_question_has_no_stale_offer_buttons(self):
        await self.turn('كنقلب على عمال فسلا')
        self.writer.return_value='لا، ما خاصك حتى وثيقة باش تقلب على عمال دابا. إلا الإدارة احتاجت شي وثيقة لطلبك غادي تطلبها منك.'
        reply=await self.turn('خصني نصيفط أيتها وثيقة دبا ؟')
        self.assertEqual(reply,self.writer.return_value)
        with db.connect() as con:
            self.assertIsNone(con.execute('SELECT 1 FROM dialogue_outgoing WHERE message_id=?',(str(self.count),)).fetchone())
            self.assertFalse(conversation.context_data(con,'owner').get('choices'))

    async def test_writer_timeout_preserves_verified_answer(self):
        self.writer.side_effect=TimeoutError()
        reply=await self.turn('كنقلب على عمال فسلا')
        self.assertIn('ما لقينا',reply)

    async def test_identical_no_results_for_different_places_is_not_loop(self):
        with patch.object(config,'CONVERSATION_REPLY_STYLE','template'):
            for place in ['سلا','سلا جديدة','فاس']:
                self.nlu.return_value=Understanding(task='search_workers',facts=Facts(location=place))
                reply=await self.turn('كنقلب على عمال ف '+place)
                self.assertNotIn('ما تقدمناش',reply)

class ReplyTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_grounded_prompt_and_structured_output_use_configured_provider(self):
        client=AsyncMock(return_value={'reply':'واخا، فاش من مدينة باغي تقلب؟'})
        with patch.multiple(config,CONVERSATION_PROVIDER='openai',CONVERSATION_MODEL='test-model'),patch('app.integrations.openai.OpenAIClient.generate_json',client):
            reply=await write_reply('بغيت عمال','فاش من مدينة؟',{'last_search':{'kind':'worker'}})
        self.assertEqual(reply,'واخا، فاش من مدينة باغي تقلب؟')
        self.assertEqual(client.call_args.kwargs['model'],'test-model')
        self.assertIn('verified_answer',client.call_args.args[0])
        self.assertIn('Never invent',client.call_args.kwargs['instructions'])
