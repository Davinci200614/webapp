import json
import unittest
from unittest.mock import AsyncMock, patch
import httpx
from app import ai, config, understanding
from app.integrations.errors import IntegrationError
from app.integrations.openai import OpenAIClient, strict_schema


def response_json(value):
    return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}


class OpenAITransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_responses_uses_strict_schema_and_no_remote_state(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(200,json=response_json({'task':'machine','facts':{'area_hectares':2}}))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with patch.object(config,'OPENAI_API_KEY','test-openai-key'):
                result=await OpenAIClient(http).generate_json('message',instructions='intent only',schema=understanding.Understanding.model_json_schema())
        self.assertEqual(result['facts']['area_hectares'],2)
        payload=json.loads(calls[0].content)
        self.assertEqual(calls[0].url.path,'/v1/responses')
        self.assertEqual(calls[0].headers['authorization'],'Bearer test-openai-key')
        self.assertFalse(payload['store'])
        schema=payload['text']['format']['schema']
        self.assertTrue(payload['text']['format']['strict'])
        self.assertEqual(set(schema['required']),set(schema['properties']))
        facts=schema['$defs']['Facts']
        self.assertEqual(set(facts['required']),set(facts['properties']))
        self.assertFalse(facts['additionalProperties'])
        self.assertNotIn('default',facts['properties']['location'])

    async def test_transcription_upload_preserves_ogg_and_original_language_prompt(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(200,json={'text':'بغيت تراكتور pour demain'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client=OpenAIClient(http)
            with patch.object(config,'OPENAI_API_KEY','test-key'):
                text=await client.transcribe(b'OggS-test','audio/ogg')
        self.assertEqual(text,'بغيت تراكتور pour demain')
        self.assertEqual(calls[0].url.path,'/v1/audio/transcriptions')
        self.assertIn(b'filename="voice.ogg"',calls[0].content)
        self.assertIn(b'OggS-test',calls[0].content)
        self.assertIn(b'Do not translate',calls[0].content)

    async def test_http_errors_are_safe_and_missing_key_never_sends(self):
        for status,code in [(401,'openai_auth_error'),(429,'openai_rate_limited'),(404,'openai_model_unavailable'),(400,'openai_invalid_request'),(500,'openai_unavailable')]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(status,text='secret-provider-payload'))) as http:
                with patch.object(config,'OPENAI_API_KEY','secret-key'),self.assertRaises(IntegrationError) as caught:
                    await OpenAIClient(http).generate_json('private message',instructions='test',schema={})
                self.assertEqual(caught.exception.code,code)
                self.assertNotIn('secret',str(caught.exception))
        client=AsyncMock()
        with patch.object(config,'OPENAI_API_KEY',''),self.assertRaises(IntegrationError):
            await OpenAIClient(client).generate_json('message',instructions='test',schema={})
        client.post.assert_not_awaited()

    async def test_refusal_incomplete_and_invalid_output_do_not_become_facts(self):
        for body,code in [({'status':'incomplete'},'openai_incomplete_response'),
                          ({'status':'completed','output':[{'type':'message','content':[{'type':'refusal','refusal':'declined'}]}]},'openai_refusal'),
                          (response_json([]),'openai_invalid_json')]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=body))) as http:
                with patch.object(config,'OPENAI_API_KEY','test-key'),self.assertRaises(IntegrationError) as caught:
                    await OpenAIClient(http).generate_json('message',instructions='test',schema={})
                self.assertEqual(caught.exception.code,code)

    async def test_timeout_and_empty_transcript_are_safe(self):
        def stalled(request): raise httpx.ReadTimeout('secret-data')
        async with httpx.AsyncClient(transport=httpx.MockTransport(stalled)) as http:
            with patch.object(config,'OPENAI_API_KEY','test-key'),self.assertRaises(IntegrationError) as caught:
                await OpenAIClient(http).transcribe(b'OggS-test')
            self.assertEqual(caught.exception.code,'openai_timeout')
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'text':' '}))) as http:
            with patch.object(config,'OPENAI_API_KEY','test-key'),self.assertRaises(IntegrationError) as caught:
                await OpenAIClient(http).transcribe(b'OggS-test')
            self.assertEqual(caught.exception.code,'transcription_unclear')


class OpenAIWiringTests(unittest.IsolatedAsyncioTestCase):
    async def test_understanding_routes_to_openai_and_validates_locally(self):
        with patch.multiple(config,CONVERSATION_PROVIDER='openai',LLM_FALLBACK_PROVIDER=''),patch('app.integrations.openai.OpenAIClient.generate_json',AsyncMock(return_value={'task':'machine','facts':{'area_hectares':2}})) as call:
            result=await understanding.understand('جوج هكتارات',{})
        self.assertEqual(result.facts.area_hectares,2)
        self.assertEqual(call.call_args.kwargs['model'],config.OPENAI_MODEL)
        with patch.multiple(config,CONVERSATION_PROVIDER='openai',LLM_FALLBACK_PROVIDER=''),patch('app.integrations.openai.OpenAIClient.generate_json',AsyncMock(return_value={'facts':{'area_hectares':-2}})),self.assertRaises(ai.AIError):
            await understanding.understand('message',{})

    async def test_stt_facade_routes_to_openai_and_normalizes_mime(self):
        with patch.object(config,'STT_PROVIDER','openai'),patch('app.integrations.openai.OpenAIClient.transcribe',AsyncMock(return_value='سلام')) as call:
            self.assertEqual(await ai.transcribe(b'OggS-test','audio/ogg; codecs=opus'),'سلام')
        call.assert_awaited_once_with(b'OggS-test','audio/ogg')

    async def test_openai_extraction_and_auto_selection(self):
        from app.llm import provider
        with patch.multiple(config,CONVERSATION_PROVIDER='auto',OPENAI_API_KEY='test-key',GEMINI_API_KEY='also-present'):
            self.assertEqual(understanding.selected_provider(),'openai')
        with patch('app.integrations.openai.OpenAIClient.generate_json',AsyncMock(return_value={'intent':'machinery_request','machine_type':'tractor'})):
            self.assertEqual((await provider('openai').extract('tractor',{})).machine_type,'tractor')

class EnvironmentCheckTests(unittest.TestCase):
    def test_openai_only_configuration_does_not_require_gemini_or_ollama(self):
        from scripts.check_config import check
        with patch.multiple(config,CONVERSATION_PROVIDER='openai',OPENAI_API_KEY='test-key',OPENAI_MODEL='gpt-4.1-mini',OPENAI_STT_MODEL='gpt-4o-mini-transcribe',STT_PROVIDER='openai',META_VERIFY_TOKEN='verify',META_APP_SECRET='secret',META_ACCESS_TOKEN='token',META_PHONE_NUMBER_ID='1234',WHATSAPP_CONTACT_NUMBER='212600000000',GEMINI_API_KEY='',GEMINI_MODEL='',OLLAMA_MODEL=''):
            self.assertEqual(check('whatsapp-voice',has_operator=True),[])

    def test_dashboard_requires_no_provider_keys(self):
        from scripts.check_config import check
        with patch.multiple(config,OPENAI_API_KEY='',GEMINI_API_KEY='',META_ACCESS_TOKEN=''):
            self.assertEqual(check('dashboard',has_operator=True),[])

class BotOnlyConfigurationTests(unittest.TestCase):
    def test_bot_does_not_require_dashboard_account_or_public_handoff_number(self):
        from scripts.check_config import check
        with patch.multiple(config,CONVERSATION_PROVIDER='openai',OPENAI_API_KEY='test-key',STT_PROVIDER='openai',META_VERIFY_TOKEN='verify',META_APP_SECRET='secret',META_ACCESS_TOKEN='token',META_PHONE_NUMBER_ID='1234',WHATSAPP_CONTACT_NUMBER='',AUTH_BOOTSTRAP_EMAIL='',AUTH_BOOTSTRAP_PASSWORD=''):
            self.assertEqual(check('whatsapp-voice'),[])
            self.assertTrue(check('dashboard'))
