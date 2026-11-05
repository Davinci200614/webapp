import unittest
from scripts.ngrok_url import find_url


class NgrokURLTests(unittest.TestCase):
    def tunnel(self, addr, public='https://example.ngrok.app'):
        return {'config': {'addr': addr}, 'public_url': public}

    def test_local_target_formats(self):
        for addr in ('8000', 'localhost:8000', 'http://localhost:8000', 'http://127.0.0.1:8000', 'http://[::1]:8000'):
            with self.subTest(addr=addr):
                self.assertEqual(find_url([self.tunnel(addr)]), 'https://example.ngrok.app')

    def test_other_targets_and_non_https_are_not_reused(self):
        for addr in ('9000', 'http://other-host:8000', 'localhost:bad'):
            self.assertIsNone(find_url([self.tunnel(addr)]))
        self.assertIsNone(find_url([self.tunnel('8000', 'http://example.ngrok.app')]))

    def test_selects_matching_tunnel_among_other_services(self):
        self.assertEqual(find_url([self.tunnel('9000'), self.tunnel('8000')]), 'https://example.ngrok.app')
