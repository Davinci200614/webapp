import unittest
from app.contacts import valid_contact


class ContactTests(unittest.TestCase):
    def test_mixed_script_email_requires_correction(self):
        self.assertIsNone(valid_contact('حميد2000ويج@gmail.com'))
        self.assertIsNone(valid_contact('حميدhamid@gmail.com'))

    def test_latin_email_inside_darija_is_preserved(self):
        self.assertEqual(valid_contact('الإيميل ديالي hamid2000@gmail.com'), 'hamid2000@gmail.com')
