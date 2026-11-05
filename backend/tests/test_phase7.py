import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import _password_hash
from app.db import connect, init_db, schema_tables
from app.main import app


class Phase7Tests(unittest.TestCase):
    def test_password_login_session_and_logout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.db"
            init_db(path)
            with connect(path) as db:
                db.execute(
                    "INSERT INTO operators(email,password_hash,role) VALUES (?,?,?)",
                    ("admin@example.com", _password_hash("correct horse battery staple"), "admin"),
                )
            with patch("app.config.DB_PATH", str(path)), patch(
                "app.auth.config.DB_PATH", str(path)
            ):
                with TestClient(app) as client:
                    login = client.post(
                        "/api/auth/login",
                        json={"email": "ADMIN@example.com", "password": "correct horse battery staple"},
                    )
                    self.assertEqual(login.status_code, 200)
                    token = login.json()["access_token"]
                    identity = client.get(
                        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
                    )
                    self.assertEqual(identity.json()["role"], "admin")
                    self.assertEqual(
                        client.post(
                            "/api/auth/logout",
                            headers={"Authorization": f"Bearer {token}"},
                        ).status_code,
                        200,
                    )
                    self.assertEqual(
                        client.get(
                            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
                        ).status_code,
                        401,
                    )

    def test_restore_schema_includes_auth_tables_and_foreign_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target.db"
            self.assertEqual(init_db(path), 4)
            self.assertTrue({"operators", "operator_sessions"} <= schema_tables(path))
            with connect(path) as db:
                self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_expired_session_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.db"
            init_db(path)
            with connect(path) as db:
                db.execute(
                    "INSERT INTO operators(email,password_hash,role) VALUES (?,?,?)",
                    ("operator@example.com", _password_hash("correct horse battery staple"), "operator"),
                )
                operator_id = db.execute("SELECT id FROM operators").fetchone()[0]
                db.execute(
                    "INSERT INTO operator_sessions(token_hash,operator_id,expires_at) VALUES (?,?,datetime('now','-1 hour'))",
                    ("expired", operator_id),
                )
            with patch("app.auth.config.DB_PATH", str(path)):
                from app.auth import _session_role
                self.assertIsNone(_session_role("expired"))


class BootstrapTests(unittest.TestCase):
    def test_invalid_bootstrap_does_not_stop_app_or_create_account(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'bootstrap.db')
            with patch.multiple('app.config', DB_PATH=path, AUTH_BOOTSTRAP_EMAIL='admin@example.test', AUTH_BOOTSTRAP_PASSWORD='short', ADMIN_API_KEY='', OPERATOR_API_KEY=''):
                with self.assertLogs('app.auth', level='WARNING') as logs:
                    with TestClient(app) as client:
                        self.assertEqual(client.get('/health').status_code, 200)
                        self.assertEqual(client.get('/api/requests').status_code, 401)
                with connect(path) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM operators').fetchone()[0], 0)
                self.assertNotIn('admin@example.test', str(logs.output))
                self.assertNotIn("'short'", str(logs.output))

    def test_valid_bootstrap_normalizes_email_and_preserves_existing_password(self):
        from app.auth import provision_bootstrap, _verify_password
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'bootstrap.db')
            init_db(path)
            with patch.multiple('app.config', DB_PATH=path, AUTH_BOOTSTRAP_EMAIL=' ADMIN@example.test ', AUTH_BOOTSTRAP_PASSWORD='initial-password-123'):
                provision_bootstrap()
                with patch('app.config.AUTH_BOOTSTRAP_PASSWORD', 'replacement-password-456'):
                    provision_bootstrap()
                with connect(path) as db:
                    rows = db.execute('SELECT * FROM operators').fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['email'], 'admin@example.test')
                self.assertTrue(_verify_password('initial-password-123', rows[0]['password_hash']))
