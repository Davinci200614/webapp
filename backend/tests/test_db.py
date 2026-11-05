import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db import connect, init_db, schema_tables
from scripts.import_legacy import import_legacy


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_empty_database_gets_both_domain_schemas_and_constraints(self):
        database = self.root / "webapp.db"
        self.assertEqual(init_db(database), 4)
        tables = schema_tables(database)
        self.assertTrue(
            {
                "farmers",
                "messages",
                "requests",
                "machines",
                "catalog_terms",
                "dialogue_drafts",
                "employment_listings",
            }.issubset(tables)
        )
        with sqlite3.connect(database) as connection:
            connection.execute(
                "INSERT INTO farmers(phone) VALUES (?)", ("212600000000",)
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO machines(name,machine_type,available_from,available_to) "
                    "VALUES (?,?,?,?)",
                    ("Tractor", "tractor", "2026-01-02", "2026-01-01"),
                )

    def test_machine_and_employment_constraints_reject_invalid_values(self):
        database = self.root / "constraints.db"
        init_db(database)
        with connect(database) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO machines(name,machine_type,hourly_rate) VALUES (?,?,?)",
                    ("", "tractor", -1),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO employment_listings"
                    "(owner_phone,kind,name,location,work,details,contact) "
                    "VALUES (?,?,?,?,?,?,?)",
                    ("unknown", "invalid", "A", "Fes", "driver", "details", "contact"),
                )

    def test_duplicate_messages_and_employment_listings_are_rejected(self):
        database = self.root / "uniqueness.db"
        init_db(database)
        with connect(database) as connection:
            connection.execute("INSERT INTO farmers(phone) VALUES (?)", ("212600000000",))
            connection.execute(
                "INSERT INTO messages(id,farmer_phone,kind) VALUES (?,?,?)",
                ("message-1", "212600000000", "text"),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO messages(id,farmer_phone,kind) VALUES (?,?,?)",
                    ("message-1", "212600000000", "text"),
                )
            connection.execute(
                "INSERT INTO employment_listings"
                "(owner_phone,kind,name,location,work,details,contact) "
                "VALUES (?,?,?,?,?,?,?)",
                ("212600000000", "worker", "A", "Fes", "driver", "details", "contact"),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO employment_listings"
                    "(owner_phone,kind,name,location,work,details,contact) "
                    "VALUES (?,?,?,?,?,?,?)",
                    ("212600000000", "worker", "B", "Fes", "driver", "details", "contact"),
                )

    def test_draft_state_can_be_reopened_after_a_new_connection(self):
        database = self.root / "continuity.db"
        init_db(database)
        with connect(database) as connection:
            connection.execute("INSERT INTO farmers(phone) VALUES (?)", ("212600000000",))
            connection.execute(
                "INSERT INTO conversations(farmer_phone,payload,last_question_field) "
                "VALUES (?,?,?)",
                ("212600000000", '{"machine_type":"tractor"}', "location"),
            )
        with connect(database) as connection:
            row = connection.execute(
                "SELECT payload,last_question_field FROM conversations WHERE farmer_phone=?",
                ("212600000000",),
            ).fetchone()
        self.assertEqual(json.loads(row["payload"])["machine_type"], "tractor")
        self.assertEqual(row["last_question_field"], "location")

    def test_import_from_machinati_shape_is_one_way_and_backup_first(self):
        source = self.root / "machinati.db"
        target = self.root / "target.db"
        with sqlite3.connect(source) as connection:
            connection.executescript(
                """
                CREATE TABLE farmers(phone TEXT PRIMARY KEY, created_at TEXT);
                CREATE TABLE requests(
                    id INTEGER PRIMARY KEY, farmer_phone TEXT, payload TEXT,
                    status TEXT, created_at TEXT, updated_at TEXT
                );
                INSERT INTO farmers VALUES ('212600000000', CURRENT_TIMESTAMP);
                INSERT INTO requests VALUES
                    (7, '212600000000', '{"machine_type":"tractor"}',
                     'pending_review', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """
            )
        init_db(target)
        counts = import_legacy(source, target, dry_run=True)
        self.assertEqual(counts["requests"], 1)
        self.assertFalse((target.with_name("target.db.backup")).exists())

        counts = import_legacy(source, target, dry_run=False)
        self.assertEqual(counts["requests"], 1)
        self.assertTrue((target.with_name("target.db.backup")).exists())
        with sqlite3.connect(target) as connection:
            row = connection.execute("SELECT id,payload FROM requests").fetchone()
            self.assertEqual(row[0], 7)
            self.assertEqual(json.loads(row[1])["machine_type"], "tractor")

    def test_import_from_nouba_schema_preserves_dialogue_and_listing_rows(self):
        source = self.root / "nouba.db"
        target = self.root / "target.db"
        with sqlite3.connect(source) as connection:
            connection.executescript(
                """
                CREATE TABLE farmers(phone TEXT PRIMARY KEY, created_at TEXT);
                CREATE TABLE dialogue_drafts(
                    phone TEXT, task TEXT, payload TEXT, pending TEXT,
                    PRIMARY KEY(phone,task)
                );
                CREATE TABLE employment_listings(
                    id INTEGER PRIMARY KEY, owner_phone TEXT, kind TEXT, name TEXT,
                    location TEXT, work TEXT, details TEXT, contact TEXT,
                    status TEXT, created_at TEXT
                );
                INSERT INTO farmers VALUES ('212611111111', CURRENT_TIMESTAMP);
                INSERT INTO dialogue_drafts VALUES
                    ('212611111111','machine','{}','location');
                INSERT INTO employment_listings VALUES
                    (3,'212611111111','worker','A','Fes','driver','details',
                     'contact','active',CURRENT_TIMESTAMP);
                """
            )
        counts = import_legacy(source, target, dry_run=False)
        self.assertEqual(counts["dialogue_drafts"], 1)
        self.assertEqual(counts["employment_listings"], 1)
        with sqlite3.connect(target) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM dialogue_drafts").fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT name FROM employment_listings WHERE id=3"
                ).fetchone()[0],
                "A",
            )
