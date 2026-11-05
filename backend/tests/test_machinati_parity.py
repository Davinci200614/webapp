"""Frozen outputs from the original MACHINATI algorithm, no runtime source dependency."""
import json
from datetime import datetime
from pathlib import Path
import unittest
from app.priority import priority_for,machine_compatibility_for

ALIASES={'match':'local','transport_review':'transport-review','date_review':'date-review'}
class MachinatiParityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.reference=json.loads((Path(__file__).parent/'fixtures'/'machinati_priority.json').read_text())
 def test_original_priority_weights_and_explanations(self):
  for case in self.reference['scores']:
   with self.subTest(case=case):
    self.assertEqual(priority_for(case['payload'],case['created_at'],datetime.fromisoformat(self.reference['now']),machine_fit=ALIASES.get(case['fit'],case['fit'])),(case['score'],case['reason']))
 def test_original_inventory_date_locality_and_owner_use_matching(self):
  for case in self.reference['matches']:
   with self.subTest(case=case):
    fit,reason,machines=machine_compatibility_for(case['payload'],case['machines'])
    self.assertEqual((fit,reason,[m['id'] for m in machines]),(ALIASES.get(case['fit'],case['fit']),case['reason'],case['ids']))
