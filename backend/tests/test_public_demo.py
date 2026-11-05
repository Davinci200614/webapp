import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import config,db
from app.main import app

class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        settings=patch.multiple(config,DB_PATH=str(Path(temp.name)/'db'),PUBLIC_DEMO_MODE=True,MUTATIONS_ENABLED=True)
        settings.start();self.addCleanup(settings.stop);db.init_db()
        self.client=TestClient(app);self.addCleanup(self.client.close)

    def test_public_demo_opens_admin_apis_without_credentials(self):
        self.assertTrue(self.client.get('/api/public/config').json()['public_demo_mode'])
        self.assertEqual(self.client.get('/api/auth/me').json()['role'],'admin')
        self.assertEqual(self.client.get('/api/requests').status_code,200)
        response=self.client.post('/api/machines',json={'name':'Demo tractor','machine_type':'tractor'})
        self.assertEqual(response.status_code,201,response.text)

    def test_disabling_demo_restores_login_requirement(self):
        with patch.object(config,'PUBLIC_DEMO_MODE',False):
            self.assertFalse(self.client.get('/api/public/config').json()['public_demo_mode'])
            self.assertEqual(self.client.get('/api/requests').status_code,401)
            self.assertEqual(self.client.post('/api/machines',json={'name':'Tractor','machine_type':'tractor'}).status_code,401)
