import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from app import diagnostics
from scripts import check_webhook


class WebhookDiagnosticsTests(unittest.TestCase):
    def test_console_events_are_visible_and_do_not_include_arbitrary_fields(self):
        diagnostics.configure_logging()
        count=len(diagnostics.log.handlers)
        diagnostics.configure_logging()
        self.assertEqual(len(diagnostics.log.handlers),count)
        with self.assertLogs('nouba.diagnostics',level='INFO') as captured:
            diagnostics.event('webhook.received',outcome='received',access_token='PRIVATE_TEST_VALUE',phone='PRIVATE_PHONE')
        output=' '.join(captured.output)
        self.assertIn('webhook.received',output)
        self.assertNotIn('PRIVATE_TEST_VALUE',output)
        self.assertNotIn('PRIVATE_PHONE',output)

    def test_tunnel_inspection_prints_only_routing_details(self):
        result={'tunnels':[{'public_url':'https://example.ngrok-free.app','config':{'addr':'http://localhost:8000'},'authtoken':'PRIVATE_TEST_VALUE'}]}
        with patch.object(check_webhook,'fetch_json',return_value=result),redirect_stdout(io.StringIO()) as output:
            check_webhook.inspect_ngrok()
        self.assertIn('example.ngrok-free.app',output.getvalue())
        self.assertIn('8000 (correct)',output.getvalue())
        self.assertNotIn('PRIVATE_TEST_VALUE',output.getvalue())

    def test_public_probe_identifies_new_backend_and_rejects_credentials_in_url(self):
        with patch.object(check_webhook,'fetch_json',return_value={'whatsapp_number':''}) as fetch,redirect_stdout(io.StringIO()) as output:
            check_webhook.inspect_public('https://example.ngrok-free.app/webhook/whatsapp')
        fetch.assert_called_once_with('https://example.ngrok-free.app/api/public/config')
        self.assertIn('integrated webapp backend',output.getvalue())
        with self.assertRaises(ValueError):check_webhook.inspect_public('https://user:secret@example.com/')
