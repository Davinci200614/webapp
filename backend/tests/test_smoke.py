import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class ApplicationSmokeTests(unittest.TestCase):
    def test_application_imports_and_health_endpoint_starts(self):
        from app.main import app

        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_optional_provider_credentials_can_be_missing(self):
        # Import settings in a fresh process: the current process may already
        # have loaded a real .env. Never render credentials in assertion output.
        environment = dict(os.environ)
        for key in ('OPENAI_API_KEY', 'GEMINI_API_KEY', 'GEMINI_MODEL',
                    'META_ACCESS_TOKEN', 'OLLAMA_MODEL'):
            environment[key] = ''
        result = subprocess.run(
            [sys.executable, '-c',
             "from app import config; "
             "assert all(getattr(config, key) == '' for key in "
             "('OPENAI_API_KEY','GEMINI_API_KEY','GEMINI_MODEL','META_ACCESS_TOKEN','OLLAMA_MODEL'))"],
            env=environment, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, 'Optional-provider configuration import failed')

    def test_application_startup_initializes_the_target_database(self):
        from app.main import app

        with TestClient(app) as client:
            self.assertEqual(client.get("/health").status_code, 200)

        from app import config
        from app.db import schema_tables

        self.assertIn("farmers", schema_tables(config.DB_PATH))


if __name__ == "__main__":
    unittest.main()
