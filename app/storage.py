import sys

# Platform detection for Pyodide (web) vs desktop

def is_web():
    return sys.platform == "emscripten"

if is_web():
    from js import window

    class BrowserStorage:
        def __init__(self):
            self.store = window.localStorage

        def get(self, key):
            return self.store.getItem(key)

        def set(self, key, value):
            self.store.setItem(key, value)

        def delete(self, key):
            self.store.removeItem(key)

        def keys(self):
            return [self.store.key(i) for i in range(self.store.length)]

    Storage = BrowserStorage
else:
    import sqlite3
    from app.config import DB_PATH

    class SQLiteStorage:
        def __init__(self, db_path):
            self.db_path = db_path
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self._ensure_table()
            try:
                print(f"[STORAGE] SQLiteStorage initialized at: {self.db_path}")
            except Exception:
                pass

        def _ensure_table(self):
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)"
            )
            self.conn.commit()

        def get(self, key):
            cur = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row else None

        def set(self, key, value):
            self.conn.execute(
                "INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, value)
            )
            self.conn.commit()
            try:
                print(f"[STORAGE] Saved key: {key}")
            except Exception:
                pass

        def delete(self, key):
            self.conn.execute("DELETE FROM kv WHERE key=?", (key,))
            self.conn.commit()

        def keys(self):
            cur = self.conn.execute("SELECT key FROM kv")
            return [row[0] for row in cur.fetchall()]

    Storage = lambda: SQLiteStorage(DB_PATH)
