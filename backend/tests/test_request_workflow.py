import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import config,db
from app.main import app

class RequestWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        patches=patch.multiple(config,DB_PATH=str(Path(temp.name)/'app.db'),ADMIN_API_KEY='admin-test',OPERATOR_API_KEY='operator-test',MUTATIONS_ENABLED=True)
        patches.start();self.addCleanup(patches.stop);db.init_db()
        self.client=TestClient(app);self.addCleanup(self.client.close)
        self.admin={'Authorization':'Bearer admin-test'}

    def create(self,**changes):
        payload=dict(name='Farmer',phone='212600000001',resource_kind='machine',machine_type='tractor',operation='Labour',location='Fes',preferred_date='2099-01-01')
        payload.update(changes)
        response=self.client.post('/api/applications',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        result=response.json()
        return result['id'],{'X-Request-Token':result['tracking_code']}

    def approve(self,id):
        return self.client.patch(f'/api/requests/{id}/status',headers=self.admin,json={'status':'approved'})

    def track(self,id,headers):
        return self.client.get(f'/api/applications/{id}',headers=headers).json()

    def test_documents_and_information_require_admin_review_and_private_tracking(self):
        id,headers=self.create()
        self.assertEqual(self.client.get(f'/api/applications/{id}').status_code,404)
        other,other_headers=self.create()
        self.assertEqual(self.client.get(f'/api/applications/{id}',headers=other_headers).status_code,404)
        response=self.client.post(f'/api/applications/{id}/documents',headers={**headers,'X-Filename':'proof.pdf'},content=b'%PDF-1.7\nproof')
        self.assertEqual(response.status_code,201,response.text);document=response.json()['id']
        self.assertEqual(self.approve(id).status_code,409)
        self.assertEqual(self.client.get(f'/api/request-documents/{document}',headers={'Authorization':'Bearer operator-test'}).status_code,403)
        self.assertEqual(self.client.get(f'/api/request-documents/{document}',headers=self.admin).content,b'%PDF-1.7\nproof')
        self.assertEqual(self.client.patch(f'/api/request-documents/{document}',headers=self.admin,json={'assessment':'accepted','note':'Checked with issuer'}).status_code,200)
        self.assertEqual(self.client.post(f'/api/requests/{id}/more-information',headers=self.admin,json={'note':'Please provide your land reference'}).status_code,200)
        self.assertEqual(self.approve(id).status_code,409)
        self.assertEqual(self.track(id,headers)['review_state'],'needs_information')
        self.assertEqual(self.client.post(f'/api/applications/{id}/information',headers=headers,json={'information':'Reference ABC'}).status_code,200)
        self.assertEqual(self.approve(id).status_code,200)
        data=self.track(id,headers)
        self.assertEqual(data['allocation_state'],'waiting');self.assertNotIn('tracking_hash',data)
        self.assertEqual(self.client.post(f'/api/applications/{id}/documents',headers=headers,content=b'%PDF-closed').status_code,409)
        self.assertEqual(self.client.patch(f'/api/requests/{other}/status',headers={'Authorization':'Bearer operator-test'},json={'status':'approved'}).status_code,403)

    def test_priority_dispatch_no_double_allocation_and_release(self):
        low,low_headers=self.create()
        high,high_headers=self.create(urgency_level='critical')
        self.assertEqual(self.approve(low).status_code,200)
        self.assertEqual(self.approve(high).status_code,200)
        machine=self.client.post('/api/machines',headers=self.admin,json={'name':'Tractor 1','machine_type':'tractor','location':'Fes'})
        self.assertEqual(machine.status_code,201,machine.text)
        self.assertEqual(self.track(high,high_headers)['allocation_state'],'allocated')
        self.assertEqual(self.track(low,low_headers)['allocation_state'],'waiting')
        self.assertEqual(self.client.get('/api/machines').json()[0]['is_allocated'],1)
        result=self.client.patch(f'/api/requests/{high}/status',headers=self.admin,json={'status':'completed'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.track(low,low_headers)['allocation']['resource_id'],machine.json()['id'])
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM request_allocations WHERE active=1').fetchone()[0],1)

    def test_worker_matching_and_invalid_uploads(self):
        with db.connect() as con:
            con.execute("INSERT INTO farmers(phone) VALUES ('212611111111')")
            con.execute("INSERT INTO employment_listings(owner_phone,kind,name,location,work,details,contact) VALUES ('212611111111','worker','Hamid','Fes','Labour','Available','phone')")
        id,headers=self.create(resource_kind='worker',machine_type='')
        self.assertEqual(self.client.post(f'/api/applications/{id}/documents',headers=headers,content=b'<html>not a document</html>').status_code,415)
        self.assertEqual(self.client.post(f'/api/applications/{id}/documents',headers=headers,content=b'%PDF-'+b'x'*(5*1024*1024)).status_code,413)
        self.assertEqual(self.approve(id).status_code,200)
        self.assertEqual(self.track(id,headers)['allocation']['resource_name'],'Hamid')

    def test_demo_and_remote_resources_are_not_dispatched(self):
        with db.connect() as con:
            con.execute("INSERT INTO machines(name,machine_type,location,is_demo) VALUES ('Demo','tractor','Fes',1)")
            con.execute("INSERT INTO machines(name,machine_type,location) VALUES ('Remote','tractor','Meknes')")
        id,headers=self.create()
        self.assertEqual(self.approve(id).status_code,200)
        self.assertEqual(self.track(id,headers)['allocation_state'],'waiting')

    def test_rejected_document_can_be_replaced_before_review(self):
        id,headers=self.create()
        uploaded=self.client.post(f'/api/applications/{id}/documents',headers=headers,content=b'%PDF-1.7 old').json()['id']
        self.client.patch(f'/api/request-documents/{uploaded}',headers=self.admin,json={'assessment':'rejected','note':'Unreadable'})
        self.assertEqual(self.approve(id).status_code,409)
        self.assertEqual(self.client.delete(f'/api/applications/{id}/documents/{uploaded}',headers={'X-Request-Token':'wrong'}).status_code,404)
        self.assertEqual(self.client.delete(f'/api/applications/{id}/documents/{uploaded}',headers=headers).status_code,200)
        replacement=self.client.post(f'/api/applications/{id}/documents',headers=headers,content=b'%PDF-1.7 clear').json()['id']
        self.client.patch(f'/api/request-documents/{replacement}',headers=self.admin,json={'assessment':'accepted'})
        self.assertEqual(self.client.delete(f'/api/applications/{id}/documents/{replacement}',headers=headers).status_code,409)
        self.assertEqual(self.approve(id).status_code,200)

    def test_upgrade_from_version_four_preserves_existing_request(self):
        import sqlite3
        old=Path(config.DB_PATH).with_name('old.db')
        with sqlite3.connect(old) as con:
            for migration in sorted(db.MIGRATIONS_DIR.glob('*.sql'))[:4]:
                con.executescript(migration.read_text())
            con.execute('PRAGMA user_version=4')
            con.execute("INSERT INTO farmers(phone) VALUES ('old-farmer')")
            con.execute("INSERT INTO requests(farmer_phone,payload,status) VALUES ('old-farmer','{}','pending_review')")
        self.assertEqual(db.init_db(old),6)
        with db.connect(old) as con:
            row=con.execute('SELECT * FROM requests').fetchone()
            self.assertEqual(row['farmer_phone'],'old-farmer')
            self.assertEqual(row['allocation_state'],'none')
            self.assertIsNone(row['tracking_hash'])
