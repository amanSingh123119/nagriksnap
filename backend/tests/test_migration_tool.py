import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'migrate_sqlite_to_postgres.py'
spec = importlib.util.spec_from_file_location('migration_tool', SCRIPT)
migration_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration_tool)


class MigrationToolTests(unittest.TestCase):
    def test_type_mapping(self):
        self.assertEqual(migration_tool.map_type('INTEGER', pk=True), 'BIGINT')
        self.assertEqual(migration_tool.map_type('REAL'), 'DOUBLE PRECISION')
        self.assertEqual(migration_tool.map_type('BLOB'), 'BYTEA')
        self.assertEqual(migration_tool.map_type('TEXT'), 'TEXT')

    def test_inventory_contains_schema_and_counts_not_row_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'source.db'
            import sqlite3
            conn = sqlite3.connect(db)
            conn.execute('CREATE TABLE parent (id INTEGER PRIMARY KEY, label TEXT NOT NULL)')
            conn.execute('CREATE TABLE child (id TEXT PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))')
            conn.execute("INSERT INTO parent(label) VALUES ('private-example')")
            conn.execute("INSERT INTO child VALUES ('c1', 1)")
            conn.commit()
            conn.close()
            inventory = migration_tool.inspect_schema(db)
            migration_tool.enrich_indexes(db, inventory)
            self.assertEqual({t['name']: t['rows'] for t in inventory['tables']}, {'child': 1, 'parent': 1})
            serialized = str(inventory)
            self.assertNotIn('private-example', serialized)
            self.assertIn('parent_id', serialized)


if __name__ == '__main__':
    unittest.main()
