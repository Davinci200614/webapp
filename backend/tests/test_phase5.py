import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import connect, init_db
from app.main import app
from app.priority import machine_compatibility_for


class Phase5ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "target.db"
        init_db(self.path)
        with connect(self.path) as db:
            db.execute("INSERT INTO farmers(phone) VALUES (?)", ("212600000000",))
            db.execute(
                """INSERT INTO requests(farmer_phone,payload,status)
                   VALUES (?,?,?)""",
                (
                    "212600000000",
                    json.dumps(
                        {
                            "intent": "request_machine",
                            "machine_type": "tractor",
                            "operation": "ploughing",
                            "area_hectares": 10,
                            "location": "Meknes",
                            "preferred_date": "2026-11-05",
                            "urgency_level": "urgent",
                        }
                    ),
                    "pending_review",
                ),
            )
            db.execute(
                """INSERT INTO requests(farmer_phone,payload,status)
                   VALUES (?,?,?)""",
                (
                    "212600000000",
                    json.dumps({"machine_type": "tractor"}),
                    "draft",
                ),
            )
        self.patches = patch.multiple(
            "app.config",
            DB_PATH=str(self.path),
            OPERATOR_API_KEY="operator-secret",
            ADMIN_API_KEY="admin-secret",
            MUTATIONS_ENABLED=True,
        )
        self.patches.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.patches.stop()
        self.directory.cleanup()

    def test_openapi_and_request_listing_include_priority_compatibility(self):
        response = self.client.get("/api/requests?status=pending_review", headers={"Authorization":"Bearer operator-secret"})
        self.assertEqual(response.status_code, 200)
        item = response.json()[0]
        self.assertEqual(item["machine_fit"], "unavailable")
        self.assertIn("priority_score", item)
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)

    def test_machine_mutations_require_auth_and_validate_fields(self):
        body = {"name": "Tractor A", "machine_type": "tractor", "available_from": "2026-12-01",
                "available_to": "2026-11-01"}
        self.assertEqual(self.client.post("/api/machines", json=body).status_code, 401)
        response = self.client.post(
            "/api/machines", json=body, headers={"Authorization": "Bearer admin-secret"}
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            self.client.post(
                "/api/machines",
                json={"name": "Tractor A", "machine_type": "tractor"},
                headers={"Authorization": "Bearer operator-secret"},
            ).status_code,
            403,
        )
        created = self.client.post(
            "/api/machines",
            json={"name": "Tractor A", "machine_type": "tractor", "location": "Meknes"},
            headers={"Authorization": "Bearer admin-secret"},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            self.client.patch(
                f"/api/machines/{created.json()['id']}",
                json={"available": False},
                headers={"Authorization": "Bearer admin-secret"},
            ).status_code,
            200,
        )

    def test_status_lifecycle_draft_and_invalid_transitions(self):
        headers = {"Authorization": "Bearer operator-secret"}
        draft = self.client.patch("/api/requests/2/status", json={"status": "approved"}, headers=headers)
        self.assertEqual(draft.status_code, 409)
        approved = self.client.patch("/api/requests/1/status", json={"status": "approved"}, headers=headers)
        self.assertEqual(approved.status_code, 200)
        invalid = self.client.patch("/api/requests/1/status", json={"status": "pending_review"}, headers=headers)
        self.assertEqual(invalid.status_code, 409)

    def test_urgency_verification_and_role_errors(self):
        self.assertEqual(
            self.client.patch(
                "/api/requests/1/urgency-verification",
                json={"reviewer": "operator"},
            ).status_code,
            401,
        )
        verified = self.client.patch(
            "/api/requests/1/urgency-verification",
            json={"reviewer": "operator"},
            headers={"Authorization": "Bearer operator-secret"},
        )
        self.assertEqual(verified.status_code, 200)
        with connect(self.path) as db:
            payload = json.loads(db.execute("SELECT payload FROM requests WHERE id=1").fetchone()[0])
        self.assertEqual(payload["verified_by"], "operator")

    def test_mutation_feature_flag_disables_writes(self):
        with patch("app.config.MUTATIONS_ENABLED", False):
            response = self.client.post(
                "/api/machines",
                json={"name": "Tractor B", "machine_type": "tractor"},
                headers={"Authorization": "Bearer admin-secret"},
            )
        self.assertEqual(response.status_code, 503)

    def test_machine_compatibility_categories(self):
        machines = [
            {"id": 1, "machine_type": "tractor", "location": "Meknes", "available": 1,
             "reserved_for_own_use": 0, "available_from": None, "available_to": None},
            {"id": 2, "machine_type": "tractor", "location": "Fes", "available": 1,
             "reserved_for_own_use": 0, "available_from": "2026-12-01", "available_to": "2026-12-31"},
            {"id": 3, "machine_type": "combine", "location": "Meknes", "available": 1,
             "reserved_for_own_use": 0, "available_from": None, "available_to": None},
        ]
        self.assertEqual(
            machine_compatibility_for({"machine_type": "tractor", "location": "Meknes"}, machines)[0],
            "local",
        )
        self.assertEqual(
            machine_compatibility_for(
                {"machine_type": "tractor", "location": "Rabat", "preferred_date": "2026-11-05"},
                machines,
            )[0],
            "transport-review",
        )
        self.assertEqual(
            machine_compatibility_for({"machine_type": "tractor", "location": "Fes"}, machines)[0],
            "date-review",
        )
        self.assertEqual(
            machine_compatibility_for({"machine_type": "harvester"}, machines)[0],
            "unavailable",
        )
        self.assertEqual(
            machine_compatibility_for({}, machines)[0],
            "not_specified",
        )
