import os
import re
import psycopg
from psycopg.rows import dict_row

class RowWrapper(dict):
    def __init__(self, d, tuple_vals=None):
        super().__init__(d)
        self._tuple_vals = tuple_vals or tuple(d.values())
    def __getitem__(self, item):
        if isinstance(item, int):
            return self._tuple_vals[item]
        return super().__getitem__(item)

class PostgresCursorWrapper:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, query, params=None):
        # Ignore PRAGMA queries
        if query.strip().upper().startswith("PRAGMA"):
            return self
        # Convert ? to %s
        converted_query = re.sub(r'\?', '%s', query)
        if params is not None:
            self._cur.execute(converted_query, params)
        else:
            self._cur.execute(converted_query)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return RowWrapper(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        return [RowWrapper(r) for r in rows]

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor(row_factory=dict_row))

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

def main():
    url = "postgresql://neondb_owner:npg_j8nlwN4PaWIb@ep-steep-frost-akscnpak-pooler.c-3.us-west-2.aws.neon.tech/neondb?sslmode=require"
    raw_conn = psycopg.connect(url)
    conn = PostgresConnectionWrapper(raw_conn)
    
    # 1. Test execute with ? placeholder
    cur = conn.execute("SELECT id, name, email FROM users WHERE lower(email) = lower(?)", ("aman.2710.singh.1947@gmail.com",))
    row = cur.fetchone()
    assert row is not None
    assert row["email"] == "aman.2710.singh.1947@gmail.com"
    assert row[0] == row["id"]
    assert dict(row)["name"] == "aman singh"
    print("Test 1 Passed: fetchone with ? placeholder and RowWrapper")
    
    # 2. Test fetchall
    cur = conn.execute("SELECT id, title, priority FROM complaints WHERE priority = ?", ("High",))
    rows = cur.fetchall()
    assert len(rows) > 0
    print(f"Test 2 Passed: fetchall returned {len(rows)} high priority complaints")
    
    # 3. Test PRAGMA ignore
    conn.execute("PRAGMA journal_mode=WAL;")
    print("Test 3 Passed: PRAGMA ignored gracefully")
    
    conn.close()
    print("ALL POSTGRES WRAPPER TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
