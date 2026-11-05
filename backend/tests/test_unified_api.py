import asyncio
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import AsyncMock,patch
from fastapi.testclient import TestClient
from app import config,db,service,conversation,understanding
from app.auth import _session_role,_password_hash
from app.main import app
from app.ai import AIError

class ApiCoverageTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  p=patch.multiple(config,DB_PATH=str(Path(self.temp.name)/'target.db'),ADMIN_API_KEY='admin-test',OPERATOR_API_KEY='operator-test',INSPECTOR_ENABLED=True)
  p.start();self.addCleanup(p.stop);db.init_db()
  self.client=TestClient(app);self.addCleanup(self.client.close)
 def test_private_reads_inspector_and_public_projection(self):
  with db.connect() as con:
   con.execute("INSERT INTO farmers(phone) VALUES ('private-number')")
   con.execute("INSERT INTO requests(farmer_phone,payload,status) VALUES ('private-number','{}','pending_review')")
   con.execute("INSERT INTO employment_listings(owner_phone,kind,name,location,work,details,contact) VALUES ('private-number','worker','Hamid','Fes','driver','available','hamid@example.test')")
  self.assertEqual(self.client.get('/api/requests').status_code,401)
  self.assertEqual(self.client.get('/api/debug/snapshot').status_code,401)
  self.assertEqual(self.client.get('/api/debug/snapshot',headers={'Authorization':'Bearer operator-test'}).status_code,403)
  data=self.client.get('/api/employment').json()
  self.assertEqual(data[0]['contact'],'hamid@example.test');self.assertNotIn('owner_phone',data[0])
  self.assertEqual(self.client.get('/api/debug/snapshot',headers={'Authorization':'Bearer admin-test'}).status_code,200)
  with patch.object(config,'INSPECTOR_ENABLED',False):
   self.assertEqual(self.client.get('/api/debug/snapshot',headers={'Authorization':'Bearer admin-test'}).status_code,403)
 def test_expired_iso_session_with_real_token_hash_is_rejected(self):
  token='expired-token'
  with db.connect() as con:
   con.execute("INSERT INTO operators(email,password_hash,role) VALUES ('operator@example.test',?,'operator')",(_password_hash('test-password-value'),))
   # Use an actual hashed token and the same ISO format as login.
   expiry=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
   con.execute('INSERT INTO operator_sessions(token_hash,operator_id,expires_at) VALUES (?,1,?)',(hashlib.sha256(token.encode()).hexdigest(),expiry))
  self.assertIsNone(_session_role(token))
 def test_inventory_full_edit_rejects_null_and_employment_moderation(self):
  headers={'Authorization':'Bearer admin-test'}
  created=self.client.post('/api/machines',headers=headers,json={'name':'Tractor','machine_type':'tractor','location':'Fes','hourly_rate':150,'owner_type':'partner','available_from':'2099-01-01','available_to':'2099-12-31'})
  self.assertEqual(created.status_code,201)
  mid=created.json()['id']
  self.assertEqual(self.client.patch(f'/api/machines/{mid}',headers=headers,json={'available':None}).status_code,422)
  self.assertEqual(self.client.patch(f'/api/machines/{mid}',headers=headers,json={'hourly_rate':200,'reserved_for_own_use':True}).json()['hourly_rate'],200)
 def test_inventory_alias_does_not_create_a_second_canonical_type(self):
  from app.catalog import terms
  from app.priority import machine_compatibility_for
  with db.connect() as con:
   con.execute("INSERT INTO machines(name,machine_type,location) VALUES ('Combine','combine_harvester','Meknes')")
   entries=terms(con)
   machines=[dict(r) for r in con.execute('SELECT * FROM machines')]
  self.assertEqual(machine_compatibility_for({'machine_type':'حصادة','location':'مكناس'},machines,entries)[0],'local')
 def test_spa_routes_and_static_assets(self):
  for route in ['/','/cooperative','/operations','/requests','/machines','/employment','/inspect','/privacy','/terms','/data-deletion']:
   result=self.client.get(route)
   # Backend API-only installs may legitimately have no compiled frontend yet.
   built=(Path(__file__).resolve().parents[2]/'frontend'/'dist'/'index.html').is_file()
   self.assertEqual(result.status_code,200 if built else 404)
   if result.status_code==200:self.assertIn('<div id="root">',result.text)
  self.assertEqual(self.client.get('/unknown-page').status_code,404)
  built=Path(__file__).resolve().parents[2]/'frontend'/'dist'/'assets'/'machinati'
  if built.is_dir():
   for page in ['catalogue','cooperative','operations']:
    response=self.client.get(f'/assets/machinati/{page}.html')
    self.assertEqual(response.status_code,200)
    self.assertIn('window.machinatiReady',response.text)
   self.assertEqual(self.client.get('/assets/machinati/bridge.js').status_code,200)


class AdditionalConversationTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  p=patch.object(config,'DB_PATH',str(Path(self.temp.name)/'target.db'));p.start();self.addCleanup(p.stop);db.init_db()
 async def test_bare_area_location_and_relative_date_need_no_model(self):
  with patch.object(config,'CONVERSATION_ROUTING','rules_first'),patch.object(service,'send_text',AsyncMock()),patch.object(service,'send_interactive',AsyncMock()),patch.object(conversation,'understand',AsyncMock(side_effect=AIError('unexpected'))) as model:
   for i,text in enumerate(['tractor','labour','10','Meknes','demain','oui']):
    await service.handle_message({'id':str(i),'from':'owner','type':'text','text':{'body':text}})
  with db.connect() as con:
   rows=con.execute('SELECT payload FROM requests').fetchall()
   self.assertEqual(len(rows),1)
   payload=json.loads(rows[0]['payload']);self.assertEqual(payload['area_hectares'],10);self.assertEqual(payload['location'],'Meknes')
  model.assert_not_awaited()
 async def test_voice_transcript_is_stored_and_enters_controller(self):
  with patch.object(service,'download_media',AsyncMock(return_value=b'OggS-test')) as download,patch.object(service,'transcribe',AsyncMock(return_value='menu')),patch.object(service,'send_interactive',AsyncMock()) as send:
   await service.handle_message({'id':'voice','from':'owner','type':'audio','audio':{'id':'media','mime_type':'audio/ogg'}})
  download.assert_awaited_once_with('media');send.assert_awaited_once()
  with db.connect() as con:self.assertEqual(con.execute("SELECT text FROM messages WHERE id='voice'").fetchone()[0],'menu')
 async def test_configured_understanding_fallback_is_used(self):
  result=understanding.Understanding(task='search_jobs')
  with patch.multiple(config,CONVERSATION_PROVIDER='gemini',LLM_FALLBACK_PROVIDER='ollama'),patch.object(understanding,'_understand',AsyncMock(side_effect=[AIError('conversation_timeout'),result])) as call:
   self.assertEqual(await understanding.understand('message',{}),result)
   self.assertEqual(call.call_args.args[2],'ollama')

class SignedEndToEndTests(unittest.TestCase):
 def test_signed_whatsapp_to_priority_queue_and_admin_review(self):
  import hmac
  with tempfile.TemporaryDirectory() as temp,patch.multiple(config,DB_PATH=str(Path(temp)/'flow.db'),META_APP_SECRET='test-secret',OPERATOR_API_KEY='operator-test',ADMIN_API_KEY='admin-test',CONVERSATION_ROUTING='rules_first'):
   db.init_db()
   with db.connect() as con:
    con.execute("INSERT INTO machines(name,machine_type,location) VALUES ('Tracteur A','tracteur','مكناس')")
   with patch.object(service,'send_text',AsyncMock()),patch.object(service,'send_interactive',AsyncMock()),patch.object(conversation,'understand',AsyncMock(side_effect=AIError('unexpected-model'))) as model:
    with TestClient(app) as client:
     for i,text in enumerate(['tractor','labour','10','Meknes','demain','oui']):
      message={'id':f'flow-{i}','from':'212600000000','type':'text','text':{'body':text}}
      raw=json.dumps({'entry':[{'changes':[{'value':{'messages':[message]}}]}]}).encode()
      signature=hmac.new(b'test-secret',raw,hashlib.sha256).hexdigest()
      headers={'x-hub-signature-256':'sha256='+signature}
      self.assertEqual(client.post('/webhook/whatsapp',content=raw,headers=headers).status_code,200)
     self.assertEqual(client.post('/webhook/whatsapp',content=raw,headers=headers).status_code,200)
     self.assertEqual(client.get('/api/requests').status_code,401)
     auth={'Authorization':'Bearer operator-test'}
     records=client.get('/api/requests',headers=auth).json()
     self.assertEqual(len(records),1);request=records[0]
     self.assertEqual(request['status'],'pending_review');self.assertEqual(request['machine_fit'],'local')
     self.assertEqual(request['matching_machines'][0]['name'],'Tracteur A')
     auth={'Authorization':'Bearer admin-test'}
     self.assertEqual(client.patch(f"/api/requests/{request['id']}/status?status=approved",headers=auth).status_code,200)
     self.assertEqual(client.patch(f"/api/requests/{request['id']}/status",headers=auth,json={'status':'completed'}).status_code,200)
   model.assert_not_awaited()
