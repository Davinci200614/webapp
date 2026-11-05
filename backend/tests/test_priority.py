import unittest
from datetime import datetime
from app.priority import machine_compatibility_for, priority_for

class PriorityTests(unittest.TestCase):
    def test_explicit_and_verified_urgency_outweigh_normal_request(self):
        now = datetime(2026, 11, 4)
        created = '2026-11-04 00:00:00'
        normal_score, _ = priority_for({'urgency_level': 'normal'}, created, now)
        urgent_score, _ = priority_for({'urgency_level': 'urgent'}, created, now)
        critical_score, _ = priority_for(
            {'urgency_level': 'critical', 'verified_by': 'reviewer'}, created, now
        )

        self.assertGreater(urgent_score, normal_score)
        self.assertGreater(critical_score, urgent_score)

    def test_unverified_urgency_has_no_verification_bonus(self):
        created = '2026-11-04 00:00:00'
        unverified, _ = priority_for({'urgency_level': 'urgent'}, created, datetime(2026, 11, 4))
        verified, reason = priority_for(
            {'urgency_level': 'urgent', 'verified_by': 'reviewer'}, created, datetime(2026, 11, 4)
        )

        self.assertEqual(verified - unverified, 10)
        self.assertIn('validée', reason)

    def test_machine_fit_requires_availability_type_and_locality(self):
        machines = [
            {'id': 1, 'name': 'Local tractor', 'machine_type': ' Tractor ', 'location': 'Safi', 'available': 1},
            {'id': 2, 'name': 'Remote tractor', 'machine_type': 'tractor', 'location': 'Meknes', 'available': 1},
            {'id': 3, 'name': 'Unavailable local tractor', 'machine_type': 'tractor', 'location': 'Safi', 'available': 0},
            {'id': 4, 'name': 'Local trailer', 'machine_type': 'transport', 'location': 'Safi', 'available': 1},
            {'id': 5, 'name': 'Unavailable irrigation pump', 'machine_type': 'irrigation', 'location': 'Safi', 'available': 0},
        ]

        fit, _, matches = machine_compatibility_for({'machine_type': 'tractor', 'location': 'safi'}, machines)
        remote_fit, _, remote_matches = machine_compatibility_for(
            {'machine_type': 'tractor', 'location': 'Fes'}, machines
        )
        missing_fit, _, no_matches = machine_compatibility_for(
            {'machine_type': 'irrigation', 'location': 'Safi'}, machines
        )

        self.assertEqual(fit, 'local')
        self.assertEqual([machine['id'] for machine in matches], [1])
        self.assertEqual(remote_fit, 'transport-review')
        self.assertEqual({machine['id'] for machine in remote_matches}, {1, 2})
        self.assertEqual(missing_fit, 'unavailable')
        self.assertEqual(no_matches, [])

    def test_reserved_machines_and_non_overlapping_dates_are_excluded(self):
        machines = [
            {'id': 1, 'machine_type': 'tractor', 'location': 'Safi', 'available': 1,
             'reserved_for_own_use': 0, 'available_from': '2026-11-01', 'available_to': '2026-11-20'},
            {'id': 2, 'machine_type': 'tractor', 'location': 'Safi', 'available': 1,
             'reserved_for_own_use': 1},
        ]

        fit, _, matches = machine_compatibility_for(
            {'machine_type': 'tractor', 'location': 'Safi', 'preferred_date': '2026-11-15'}, machines
        )
        outside_window, _, no_matches = machine_compatibility_for(
            {'machine_type': 'tractor', 'location': 'Safi', 'preferred_date': '2026-11-25'}, machines
        )
        date_review, _, review_matches = machine_compatibility_for(
            {'machine_type': 'tractor', 'location': 'Safi'}, machines[:1]
        )

        self.assertEqual(fit, 'local')
        self.assertEqual([machine['id'] for machine in matches], [1])
        self.assertEqual(outside_window, 'unavailable')
        self.assertEqual(no_matches, [])
        self.assertEqual(date_review, 'date-review')
        self.assertEqual([machine['id'] for machine in review_matches], [1])

    def test_local_machine_fit_improves_priority_above_unchecked_transport(self):
        created = '2026-11-04 00:00:00'
        now = datetime(2026, 11, 4)
        local, _ = priority_for({'urgency_level': 'normal'}, created, now, machine_fit='local')
        transport_review, _ = priority_for(
            {'urgency_level': 'normal'}, created, now, machine_fit='transport-review'
        )

        self.assertEqual(local - transport_review, 10)



class WindowPriorityTests(unittest.TestCase):
    def test_urgent_window_overlap_and_bonus(self):
        machine={'id':1,'machine_type':'tractor','location':'Meknes','available':1,'available_from':'2099-01-10','available_to':'2099-01-20'}
        payload={'machine_type':'tracteur','location':'مكناس','urgent_window_start':'2099-01-15','urgent_window_end':'2099-01-25'}
        self.assertEqual(machine_compatibility_for(payload,[machine])[0],'local')
        payload['urgent_window_start']='2099-02-01';payload['urgent_window_end']='2099-02-10'
        self.assertEqual(machine_compatibility_for(payload,[machine])[0],'unavailable')
        now=datetime(2026,11,5)
        with_window,_=priority_for(payload,now.isoformat(),now)
        without_window,_=priority_for({},now.isoformat(),now)
        self.assertEqual(with_window-without_window,5)
